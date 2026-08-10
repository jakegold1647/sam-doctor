"""Deterministic, evidence-first diagnostic rules for deployment logs."""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from html import escape

from . import __version__
from .redaction import redact

RULE_REQUEST_URL = (
    "https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml"
)

# An empty log is not an unrecognized failure. Reporting "no supported pattern
# found" for one implies the tool read a failure it did not understand, when it
# read nothing at all. This wording deliberately omits the rule-request prompt:
# there is no excerpt to send.
EMPTY_INPUT_NOTE = (
    "{source} is empty, so there was nothing to diagnose.\n"
    "This usually means the step that writes the log failed before producing "
    "output, or the log was captured from the wrong command.\n"
    "Check the step that produces the log, then re-run the diagnosis."
)


def _request_packet_command(source_name: str) -> str:
    """Suggest the safe follow-up command without echoing sensitive names."""

    if source_name == "<stdin>":
        input_name = "-"
    else:
        safe_source = redact(source_name)
        # A simple filename/path is useful as a copy-paste hint. If redaction or
        # shell-significant characters make that unsafe, keep the prompt generic.
        input_name = (
            safe_source
            if re.fullmatch(r"[A-Za-z0-9._/\\-]+", safe_source)
            else "<path-to-log>"
        )
    return f"sam-doctor request-packet {input_name}"


@dataclass(frozen=True)
class Finding:
    """A matched failure pattern and safe next actions."""

    rule_id: str
    title: str
    confidence: str
    explanation: str
    verification: tuple[str, ...]
    documentation_url: str
    evidence: tuple[str, ...]
    line_number: int


@dataclass(frozen=True)
class Rule:
    # Short, stable identifier such as `iam.deny.explicit`. Titles and
    # explanations may be reworded as evidence improves; the id is the safe
    # integration key downstream tools should match on instead. See
    # docs/stability.md.
    id: str
    title: str
    confidence: str
    patterns: tuple[str, ...]
    explanation: str
    verification: tuple[str, ...]
    documentation_url: str
    # Whole-log patterns: when any of them matches anywhere in the input, this
    # rule is skipped because a more specific rule produces the actionable
    # finding for that log. Patterns are evaluated case-insensitively; use an
    # inline (?s:...) group when a pattern must span lines.
    suppressed_by: tuple[str, ...] = ()
    # Per-line patterns: a line matching any of these never counts as evidence
    # for this rule, even when a primary pattern also matches it.
    excluded_line_patterns: tuple[str, ...] = ()
    # When set, the finding's explanation is extended with a denial context
    # parsed from the (already redacted) evidence: the denied action, whether a
    # principal and resource were named, and which policy layer the error
    # wording attributes the denial to.
    parse_denial_context: bool = False
    # When set, the finding's explanation is prefixed with the nested status
    # reason parsed from the (already redacted) evidence: the quoted resource
    # handler message and the resource type, when the log includes them. The
    # nested reason leads because it names the actual failure; the
    # stabilization wording around it is only the wrapper.
    parse_stabilization_context: bool = False


# The action name (e.g. `iam:CreateRole`) is service metadata, not an account
# identifier, so it is safe to surface after redaction has replaced ARNs and
# account ids in the evidence line.
_DENIED_ACTION = re.compile(
    r"not authorized to perform:?\s*([A-Za-z0-9-]+:[A-Za-z0-9*]+)"
)
_DENIED_PRINCIPAL = re.compile(r"User:\s*\[REDACTED_ARN\]", re.IGNORECASE)
_DENIED_RESOURCE = re.compile(r"on resource:?\s*(\[REDACTED_ARN\]|\*)", re.IGNORECASE)
_EXPLICIT_DENY_SCP = re.compile(
    r"explicit deny in a service control policy", re.IGNORECASE
)
_EXPLICIT_DENY = re.compile(r"(?:with|due to) an explicit deny", re.IGNORECASE)
_IMPLICIT_DENY_LAYER = re.compile(
    r"because no ([a-z][a-z -]*?)\s*polic(?:y|ies) allows", re.IGNORECASE
)


def _denial_context_note(evidence: tuple[str, ...]) -> str:
    """Describe the parsed denial from redacted evidence, or an empty string."""

    for line in evidence:
        action_match = _DENIED_ACTION.search(line)
        scp = _EXPLICIT_DENY_SCP.search(line)
        explicit = scp or _EXPLICIT_DENY.search(line)
        implicit = _IMPLICIT_DENY_LAYER.search(line)
        if not (action_match or explicit or implicit):
            continue
        parts = []
        if action_match:
            parts.append(f"denied action `{action_match.group(1)}`")
        if _DENIED_PRINCIPAL.search(line):
            parts.append("for the caller identity shown (redacted) in the evidence")
        resource_match = _DENIED_RESOURCE.search(line)
        if resource_match:
            target = (
                "all resources (`*`)"
                if resource_match.group(1) == "*"
                else "the specific resource shown (redacted) in the evidence"
            )
            parts.append(f"on {target}")
        if scp:
            parts.append(
                "blocked by an explicit deny in a service control policy "
                "(set at the AWS Organizations level, not in this account)"
            )
        elif explicit:
            parts.append("blocked by an explicit deny statement")
        elif implicit:
            layer = implicit.group(1).strip()
            parts.append(f"an implicit deny: no {layer} policy allows it")
        return "Denial context parsed from the evidence: " + "; ".join(parts) + "."
    return ""


_HANDLER_MESSAGE = re.compile(
    r'Resource handler returned message:\s*"([^"]+)"', re.IGNORECASE
)
_RESOURCE_TYPE = re.compile(r"\b((?:AWS|Custom)::[A-Za-z0-9]+(?:::[A-Za-z0-9]+)?)\b")

# Resource families with a known slow or externally-gated stabilization path.
# The note routes to the family-specific check; anything else gets the generic
# guidance in the rule's verification steps.
_SLOW_RESOURCE_HINTS = (
    (
        "AWS::CertificateManager::",
        "ACM certificates stay pending until their DNS or email validation completes",
    ),
    (
        "AWS::CloudFront::",
        "CloudFront distributions propagate globally and routinely take tens of minutes",
    ),
    ("AWS::RDS::", "RDS instances and clusters have long provisioning windows"),
    (
        "Custom::",
        (
            "a custom resource stabilizes only when its handler signals completion, "
            "so check the handler function's own logs"
        ),
    ),
)


def _stabilization_context_note(evidence: tuple[str, ...]) -> str:
    """Surface the nested status reason from redacted evidence, or an empty string."""

    for line in evidence:
        message_match = _HANDLER_MESSAGE.search(line)
        type_match = _RESOURCE_TYPE.search(line)
        if not (message_match or type_match):
            continue
        parts = []
        if message_match:
            parts.append(
                "the service handler reported: "
                f'"{message_match.group(1).strip()}" - inspect that reason before '
                "the stabilization timeout itself"
            )
        if type_match:
            resource_type = type_match.group(1)
            parts.append(f"resource type `{resource_type}`")
            for prefix, hint in _SLOW_RESOURCE_HINTS:
                if resource_type.startswith(prefix):
                    parts.append(hint)
                    break
        return (
            "Underlying status reason parsed from the evidence: "
            + "; ".join(parts)
            + "."
        )
    return ""


_AWS_SERVICE_PREFIX_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_TAG_MUTATION_ACTION_PATTERN = (
    r"(?:(?:Tag|Untag)[a-z0-9]+|(?:Create|Delete)Tags|"
    r"AddTagsToResource|RemoveTagsFromResource)"
)
_TAG_ACTION_DENIAL_PATTERN = (
    rf"not authorized to perform:?\s*{_AWS_SERVICE_PREFIX_PATTERN}:"
    rf"{_TAG_MUTATION_ACTION_PATTERN}(?![a-z0-9*])"
)

_LAMBDA_ENV_KMS_FAILURE_PATTERNS = (
    (
        r"Lambda was unable to configure (?:access to )?your environment variables"
        r".{0,800}KMS Exception:\s*"
        r"(?:AccessDenied|Disabled|KMSInvalidState|InvalidArn|NotFound)Exception\b"
    ),
    (
        r"KMS Exception:\s*AccessDeniedException\b.{0,240}"
        r"ciphertext refers to a customer master key that does not exist,\s*"
        r"does not exist in this region,\s*or you are not allowed to access\.?"
    ),
)

_SSM_RESOLUTION_FAILURE_PATTERNS = (
    (
        r"Parameters:[ \t]*\[ssm(?:-secure)?:[^\r\n\]]{1,200}\]"
        r"[ \t]*cannot be found\b"
    ),
    r"SSM parameter[ \t]+\S{1,200}[ \t]+not found\b",
)

_CODEBUILD_CODECONNECTIONS_FAILURE_PATTERN = (
    r"User is not authorized to access connection\b.*"
    r"Service:\s*AWSCodeBuild\b.*"
    r"Error Code:\s*OAuthProviderException\b"
)

_S3_ABORT_MULTIPART_TAG_FILTER_PATTERN = (
    r"AbortIncompleteMultipartUpload cannot be specified with Tags"
)


_RULES = (
    Rule(
        id="github.oidc.token-request-denied",
        title="The GitHub Actions job cannot request an OIDC token",
        confidence="high",
        patterns=(
            r"Unable to get ID Token.*id-token:\s*write",
            r"id-token:\s*write.*(?:permission|required|missing)",
            # What the runtime actually prints. The two patterns above expect the
            # log to mention `id-token: write` - which is the fix, not the error.
            # @actions/core says "Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env
            # variable" and nothing else, because without the permission the
            # runner never injects that variable. Found in four unrelated public
            # repositories while measuring this catalog against real logs; the
            # flagship OIDC rule was matching a string real logs do not contain.
            r"Unable to get ACTIONS_ID_TOKEN_REQUEST_(?:URL|TOKEN)",
            r"ACTIONS_ID_TOKEN_REQUEST_(?:URL|TOKEN) env variable",
        ),
        explanation=(
            "The workflow does not have the permission required to request a GitHub "
            "OIDC token. AWS role trust settings cannot help until the deployment job "
            "can obtain a token."
        ),
        verification=(
            "Add `id-token: write` to the permissions of the workflow or deployment job.",
            "Confirm no reusable-workflow or job-level permissions block overrides that setting.",
            "Rerun the job and then evaluate the AWS trust-policy conditions if STS still rejects the token.",
        ),
        documentation_url="https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws",
    ),
    Rule(
        id="github.oidc.assume-role-rejected",
        title="GitHub Actions cannot assume the configured AWS role through OIDC",
        confidence="high",
        patterns=(
            # The colon is optional because AWS does not always print it.
            # `configure-aws-credentials` reports "Could not assume role with OIDC:
            # Not authorized to perform sts:AssumeRoleWithWebIdentity" - no colon
            # after `perform` - and that wording appeared in three unrelated public
            # repositories, none of which this rule matched. `not authorized` also
            # joins the leading alternation below, because in that sentence it
            # precedes the action name rather than following it.
            r"Not authorized to perform:?\s*sts:AssumeRoleWithWebIdentity",
            r"(?:failed|error|denied|unable|not authorized).{0,80}AssumeRoleWithWebIdentity",
            r"AssumeRoleWithWebIdentity.{0,80}(?:failed|error|denied|not authorized)",
        ),
        explanation=(
            "The workflow reached AWS STS but the role trust relationship did not "
            "accept the GitHub-issued OIDC token. The usual cause is a missing "
            "`id-token: write` permission, an incorrect token audience, or a `sub` "
            "condition that does not match the repository, branch, or GitHub Environment."
        ),
        verification=(
            "Confirm the workflow or job permissions include `id-token: write`.",
            "Check that the role trust policy accepts `token.actions.githubusercontent.com:aud` equal to `sts.amazonaws.com`.",
            "Compare the trust policy's `sub` condition with the exact branch or GitHub Environment that ran the job; newer repositories can include immutable owner and repository IDs in that claim.",
        ),
        documentation_url="https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws",
    ),
    Rule(
        id="github.oidc.audience-mismatch",
        title="GitHub OIDC token audience does not match AWS STS",
        confidence="high",
        patterns=(r"Incorrect token audience", r"audience.*sts\.amazonaws\.com"),
        explanation=(
            "AWS rejected the token audience. GitHub Actions OIDC deployments to AWS "
            "normally require the audience to be `sts.amazonaws.com`."
        ),
        verification=(
            "Check the `audience` setting passed to the credentials action, if one is configured.",
            "Confirm the IAM trust policy checks the audience expected by AWS STS.",
        ),
        documentation_url="https://github.com/aws-actions/configure-aws-credentials#oidc-configuration",
    ),
    Rule(
        id="github.oidc.provider-missing",
        title="The target AWS account is missing the GitHub Actions OIDC provider",
        confidence="high",
        patterns=(
            r"No OpenIDConnect provider found in your account",
            r"OpenIDConnect provider.*token\.actions\.githubusercontent\.com.*not found",
        ),
        explanation=(
            "AWS could not find the GitHub Actions OIDC identity provider in the account "
            "where the role is configured. A valid workflow token cannot assume the role "
            "until that provider and the role's federated principal agree."
        ),
        verification=(
            "Confirm the deployment is targeting the intended AWS account and role ARN.",
            "Verify that the account has an IAM OIDC provider for `token.actions.githubusercontent.com`.",
            "Check that the role trust policy names that provider ARN as its federated principal.",
        ),
        documentation_url="https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws",
    ),
    Rule(
        id="lambda.ecr-image.access-denied",
        title="Lambda cannot access the configured ECR image",
        confidence="high",
        patterns=(
            r"Lambda does not have permission to access the ECR image",
            r"(?:Lambda|function).{0,80}(?:permission|access).{0,80}(?:ECR|container) image",
        ),
        explanation=(
            "Lambda could not retrieve the container image from ECR during deployment. "
            "This usually points to a missing repository policy, a removed permission, "
            "or a cross-account configuration that no longer grants image access."
        ),
        verification=(
            "Confirm the function uses `PackageType: Image` and identify the exact ECR repository and image tag or digest.",
            "Check the ECR repository policy and the deployment configuration for the function's account and Region.",
            "For cross-account images, verify both the consuming account's identity policy and the owning account's repository policy allow the required image retrieval actions.",
        ),
        documentation_url="https://docs.aws.amazon.com/lambda/latest/dg/images-create.html",
    ),
    Rule(
        id="codebuild.codeconnections.access-denied",
        title="CodeBuild cannot use the configured CodeConnections connection",
        confidence="high",
        patterns=(_CODEBUILD_CODECONNECTIONS_FAILURE_PATTERN,),
        explanation=(
            "CloudFormation reached AWS CodeBuild, but CodeBuild rejected the "
            "configured CodeConnections source connection while creating the project. "
            "The usual causes are a project service role missing the connection-read "
            "actions, a connection that is not available to this account or Region, "
            "or an IAM policy attachment that was not in effect before the project "
            "was created."
        ),
        verification=(
            "Identify the CodeBuild project service role and the connection ARN in the transformed template or project source settings.",
            "Read the service role's inline and attached policies and confirm the source mode is allowed: CodeConnections sources commonly need `codeconnections:GetConnection` and `codeconnections:GetConnectionToken`; add `codeconnections:UseConnection` when the configured service path requires it.",
            "Check the connection status and provider in the target account and Region with `aws codeconnections get-connection --connection-arn <connection-arn>` (read-only).",
            "If the role policy and CodeBuild project are created in one stack, make the project depend on the policy attachment and retry after IAM propagation; do not widen the deployment role as a substitute for the project role.",
        ),
        documentation_url="https://docs.aws.amazon.com/codebuild/latest/userguide/connections-github-app.html",
    ),
    Rule(
        id="ecr.auth.login-failed",
        title="The CI runner could not authenticate to ECR to push the image",
        confidence="high",
        patterns=(
            r"no basic auth credentials",
            r"Your authorization token has expired\.?\s*Reauthenticate",
            r"not authorized to perform:\s*ecr:GetAuthorizationToken",
        ),
        explanation=(
            "The machine running the deployment could not authenticate to ECR "
            "before or while pushing the function image. This happens earlier "
            "than any Lambda image-pull problem: the runner never logged in to "
            "the registry, its 12-hour ECR authorization token expired mid-job, "
            "or the deployment identity lacks `ecr:GetAuthorizationToken`."
        ),
        verification=(
            "Run `aws ecr get-login-password | docker login` (or the `aws-actions/amazon-ecr-login` action) in the job before the push step.",
            "For jobs that can run longer than 12 hours, re-authenticate before the push instead of reusing the login from the start of the job.",
            "Grant the deployment identity `ecr:GetAuthorizationToken` (its resource is always `*`) plus the repository-scoped push actions on the exact repository in the error.",
        ),
        documentation_url="https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html",
    ),
    Rule(
        id="iam.deny.explicit",
        title="An explicit deny blocked a deployment action",
        confidence="high",
        patterns=(r"(?:with|due to) an explicit deny",),
        explanation=(
            "AWS evaluated the request and found a Deny statement that matched it. "
            "An explicit deny always wins: adding or broadening Allow policies "
            "cannot fix this. The deny lives in one of the policy layers that "
            "apply to the caller - a service control policy from the AWS "
            "Organizations management account (the error says so when it is the "
            "cause), or a Deny in an identity, resource, permissions-boundary, "
            "or session policy."
        ),
        verification=(
            "Record the exact action, caller, and resource from the error, and run `aws sts get-caller-identity` in the same environment to confirm which identity actually made the call.",
            "If the message names a service control policy, inspect SCPs from the AWS Organizations management account; the deny cannot be seen or changed from the member account.",
            'Otherwise search for matching `"Effect": "Deny"` statements across the caller\'s identity policies, permissions boundary, session policy, and the target\'s resource policy, and confirm the layer with the IAM Policy Simulator.',
            "Look up the request in CloudTrail (by request ID from the error when present) to see the full denied request context.",
            "Fix by amending the specific Deny (add a condition or exception for the deployment identity); do not broaden Allow policies, and never attach AdministratorAccess to work around a deny.",
        ),
        documentation_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html",
        excluded_line_patterns=(
            r"AssumeRoleWithWebIdentity",
            r"ECR image",
            r"ecr:GetAuthorizationToken",
            # A denied Tag*/Untag* action is claimed by the tagging rule, which
            # names the tag action and the create action it belongs with. Per
            # line, not whole log: a non-tag denial elsewhere in the same log
            # still reports here.
            _TAG_ACTION_DENIAL_PATTERN,
        ),
        parse_denial_context=True,
    ),
    Rule(
        id="iam.deny.implicit",
        title="A deployment action was denied because no policy allows it",
        confidence="high",
        patterns=(r"because no [a-z -]*polic(?:y|ies) allows",),
        explanation=(
            "AWS denied the action because no applicable policy grants it - an "
            "implicit deny. The error wording names the policy layer AWS "
            "expected the permission in (identity-based, resource-based, or "
            "session policy). The fix is a least-privilege Allow for exactly "
            "the denied action and resource in that layer, not a broader role."
        ),
        verification=(
            "Run `aws sts get-caller-identity` in the failing environment to confirm the request used the identity you expected (a wrong profile often looks like a missing permission).",
            "Grant the exact denied action on the exact resource in the policy layer the error names: the deploy role's identity policy, or the resource policy of the named bucket, key, or queue.",
            "Confirm the change with the IAM Policy Simulator before re-running the deployment.",
            "If it is unclear which policy applies, look up the denied event in CloudTrail (by request ID when the error includes one).",
            "Keep the grant least-privilege; never attach AdministratorAccess to make a deployment pass.",
        ),
        documentation_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html",
        excluded_line_patterns=(
            r"AssumeRoleWithWebIdentity",
            r"ECR image",
            r"ecr:GetAuthorizationToken",
            # See the note on the explicit-deny rule above: tag-action denials
            # belong to the tagging rule, per line rather than per log.
            _TAG_ACTION_DENIAL_PATTERN,
        ),
        parse_denial_context=True,
    ),
    Rule(
        id="iam.access-denied.generic",
        title="AWS denied an API action required by the deployment",
        confidence="medium",
        patterns=(r"AccessDenied(?:Exception)?", r"is not authorized to perform:"),
        explanation=(
            "The active AWS identity was denied an action. The visible error may be "
            "caused by an identity policy, permissions boundary, resource policy, "
            "service control policy, or the role/session policy."
        ),
        verification=(
            "Record the exact action, resource, and caller ARN from the error before changing a policy.",
            "Use the IAM Policy Simulator or CloudTrail to determine which policy layer denied the request.",
            "Apply the smallest permission change that permits the intended deployment action.",
        ),
        documentation_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html",
        # The ECR-image and layer-artifact findings identify the denied access
        # path directly, so the generic denial adds noise for those logs.
        suppressed_by=(
            r"Lambda does not have permission to access the ECR image",
            r"(?s:access has been denied by S3.*permission.*GetObject)",
            r"permission to GetObject for.*bucket",
        ),
        # STS OIDC failures are authorization failures, but the OIDC rule
        # provides a more precise and actionable explanation than the generic
        # IAM finding.
        excluded_line_patterns=(
            r"AssumeRoleWithWebIdentity",
            r"ECR image",
            r"ecr:GetAuthorizationToken",
            # Lines with explicit-deny or no-policy-allows wording are claimed
            # by the two higher-confidence denial rules above; keeping them out
            # here (per line, not whole log) lets this rule still report bare
            # AccessDenied lines elsewhere in the same log.
            r"(?:with|due to) an explicit deny",
            r"because no [a-z -]*polic(?:y|ies) allows",
            # The artifact-bucket rule below names the bucket, the direction,
            # and the S3-specific checks, so those lines belong to it. Only the
            # tool-level wording is excluded: an IAM-worded denial keeps its
            # own findings.
            r"S3 error: Access ?Denied",
            r"(?:Error|Failed) uploading to \S+.{0,200}Access ?Denied",
            # The tagging rule names the tag action and the create action it
            # should be granted with, so those lines belong to it.
            _TAG_ACTION_DENIAL_PATTERN,
            # A KMS denial inside a Lambda env-var failure needs the key policy
            # and the key's state reviewed, not the IAM policy simulator, so
            # sending it to the generic denial actively misdirects the reader.
            *_LAMBDA_ENV_KMS_FAILURE_PATTERNS,
        ),
        parse_denial_context=True,
    ),
    Rule(
        id="iam.tag.action-denied",
        title="AWS denied a tagging action required by the deployment",
        confidence="medium",
        patterns=(
            _TAG_ACTION_DENIAL_PATTERN,
            r"TagPolicyViolation",
        ),
        explanation=(
            "The denied IAM action mutates tags. During a create or update, "
            "CloudFormation and AWS services often apply tags in the same "
            "operation, so a missing paired `TagResource` or `CreateTags` grant "
            "can fail the resource operation. Direct retag and untag calls "
            "produce the same diagnosis. An AWS Organizations tag policy or a "
            "CloudFormation hook can reject the tag set from a layer the member "
            "account cannot see."
        ),
        verification=(
            "Record the exact tagging action, resource, and caller named in the error before changing any policy.",
            "If the called operation was a create or update, grant its paired tagging action: for example `application-autoscaling:TagResource` with `RegisterScalableTarget`, `iam:TagRole` with `CreateRole`, or EC2 `CreateTags` for create-time tags. For a direct retag or untag call, grant only the exact denied mutation.",
            "Scope the permission to the affected resource and, where the service supports them, constrain allowed keys with `aws:RequestTag/${TagKey}` and `aws:TagKeys` conditions.",
            "If an Organizations tag policy or a CloudFormation hook rejected the tag set, identify the layer that enforced it and resolve it with that layer's owner - do not remove a tag policy or hook to make a deployment pass.",
            "Confirm the grant with the IAM Policy Simulator, or look the denied call up in CloudTrail when the error carries a request ID.",
        ),
        documentation_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/id_tags.html",
        parse_denial_context=True,
    ),
    Rule(
        id="cloudformation.tag.key-validation-failed",
        title="A tag key or value was rejected by validation",
        confidence="medium",
        patterns=(
            r"validation error.{0,120}?'tags\.\d{1,3}\.member\.(?:key|value)'",
            r"'tags\.\d{1,3}\.member\.(?:key|value)'\s*failed to satisfy constraint",
            r"[Tt]ag key.{0,60}?(?:reserved|cannot begin with|must not begin with).{0,20}?aws:",
        ),
        explanation=(
            "A tag key or value was rejected before the resource was touched, so "
            "this is a template problem rather than a permissions one. The usual "
            "causes are a key using the reserved `aws:` prefix, which is "
            "reserved for AWS-generated tags and cannot be set, or a key or "
            "value that breaks the allowed character set or length. The index in "
            "`tags.N.member.key` points at which tag in the submitted set failed."
        ),
        verification=(
            "Read the index in the error (`tags.N.member.key`) and find the matching tag in the template or `samconfig.toml` tag list.",
            "Rename any key using the reserved `aws:` prefix; that prefix is reserved for AWS and cannot be applied by a deployment.",
            "Check the key and value against the tag restrictions - length limits and the allowed character set - and re-run the deployment.",
        ),
        documentation_url="https://docs.aws.amazon.com/general/latest/gr/aws_tagging.html",
    ),
    Rule(
        id="s3.artifact-bucket.access-denied",
        title="The deployment bucket denied access to the packaged artifacts",
        confidence="high",
        patterns=(
            r"S3 error: Access ?Denied",
            r"AccessDenied.{0,160}when calling the (?:PutObject|GetObject|HeadObject|CreateMultipartUpload|UploadPart) operation",
            r"(?:Error|Failed) uploading to \S+.{0,200}Access ?Denied",
        ),
        explanation=(
            "S3 refused access to the deployment's artifact bucket. The two "
            "directions fail for different reasons and need different fixes. "
            "Upload (the SAM CLI writing the packaged template and code zips) "
            "shows as a denied `PutObject`/`CreateMultipartUpload` while "
            "uploading to the named bucket: the deploy identity lacks "
            "`s3:PutObject`, a bucket policy or Block Public Access setting "
            "denies it, or `s3_bucket` in `samconfig.toml` points at a bucket "
            "in another Region or another account. Readback (CloudFormation "
            "fetching what was uploaded) shows as `S3 error: Access Denied` "
            "while the change set is created: the CloudFormation execution "
            "identity - not the CLI's - lacks `s3:GetObject` on the key, or "
            "the bucket is SSE-KMS encrypted and that identity has no "
            "permission on the key. This is a bucket or key access problem, "
            "not an invalid bucket name and not a name collision."
        ),
        verification=(
            "Note which direction failed - a denied `PutObject` is the CLI uploading, `S3 error: Access Denied` during change-set creation is CloudFormation reading back - and confirm the caller with `aws sts get-caller-identity`.",
            "Run `aws s3api head-object --bucket <deploy-bucket> --key <key>` (read-only): success means the upload landed and the readback identity is the one being denied.",
            "Run `aws s3api get-bucket-location --bucket <deploy-bucket>` and compare it with the deployment Region; a wrong-Region `s3_bucket` in `samconfig.toml` surfaces as a denial.",
            "Run `aws s3api get-bucket-encryption --bucket <deploy-bucket>`: if it uses SSE-KMS, the denied identity also needs `kms:Decrypt` (and `kms:GenerateDataKey` to upload) on that key.",
            "Confirm who owns the bucket before changing any policy - for a cross-account bucket, pass `--expected-bucket-owner` when checking, and fix the bucket policy in the owning account rather than broadening the deploy role.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html",
        # A Lambda layer artifact denial has its own finding with layer-specific
        # guidance; the S3 object API wording overlaps, so let that rule win.
        suppressed_by=(
            r"(?s:access has been denied by S3.*permission.*GetObject)",
            r"permission to GetObject for.*bucket",
        ),
        # An IAM-worded denial ("... is not authorized to perform: s3:PutObject
        # ... because no identity-based policy allows ...") already gets a
        # finding that names the policy layer and the exact action, which is
        # more actionable than the bucket-level guidance here. Excluding those
        # lines per line, not per log, keeps this rule available for tool-level
        # S3 denials elsewhere in the same log.
        excluded_line_patterns=(r"is not authorized to perform:",),
    ),
    Rule(
        id="aws.credentials.expired",
        title="The AWS credentials used by the deployment have expired",
        confidence="high",
        patterns=(
            r"ExpiredToken(?:Exception)?",
            r"security token included in the request is expired",
            r"Signature expired:.*is now earlier than",
        ),
        explanation=(
            "AWS rejected the request because the temporary credentials were no "
            "longer valid when it arrived. This is a credential-lifetime or "
            "clock problem, not a permissions or template problem: the session "
            "expired (cached SSO login, long-lived shell, short OIDC session "
            "duration), or the machine's clock is far enough off that the "
            "request signature is treated as stale."
        ),
        verification=(
            "Refresh the credentials for the environment that failed: re-run `aws sso login`, rotate the CI secret, or re-assume the role; for OIDC deployments check the role's maximum session duration.",
            "For a `Signature expired ... is now earlier than` message, compare the two timestamps in the error: a gap of more than a few minutes means the runner's clock is skewed, so sync it (NTP) rather than rotating credentials.",
            "Confirm the deployment picks up the refreshed credentials (no stale AWS_* environment variables or cached profiles) before retrying.",
        ),
        documentation_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html",
    ),
    Rule(
        id="aws.credentials.invalid",
        title="The deployment ran with invalid or wrong-account AWS credentials",
        confidence="high",
        patterns=(
            r"security token included in the request is invalid",
            r"UnrecognizedClientException",
        ),
        explanation=(
            "The request never passed authentication: the security token is "
            "invalid, or the access key belongs to no known account. This is "
            "not the same failure as expired credentials - AWS rejected the "
            "token itself rather than a token that was once valid. Common "
            "causes are stale `AWS_*` environment variables overriding the "
            "intended profile, credentials for the wrong account, or a "
            "region configured under only one `samconfig.toml` section."
        ),
        verification=(
            "Run `aws configure list` in the failing environment to see which source (environment variable, profile, or IAM role) supplied each credential value.",
            "Check for `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or `AWS_SESSION_TOKEN` environment variables overriding the intended profile.",
            "Once credentials are corrected, confirm the account with `aws sts get-caller-identity`.",
        ),
        documentation_url="https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html",
        # The expired-credentials rule owns `is expired`/`ExpiredToken`; defer
        # to it when a log carries both symptoms so the more precise finding
        # wins instead of both firing for the same underlying credential.
        suppressed_by=(
            r"ExpiredToken(?:Exception)?",
            r"security token included in the request is expired",
        ),
    ),
    Rule(
        id="cloudformation.api.throttled",
        title="CloudFormation throttled the deployment's API calls",
        confidence="medium",
        patterns=(
            r"An error occurred \(Throttling\)",
            r"\bRate exceeded\b",
        ),
        explanation=(
            "AWS rejected API calls because the account exceeded a request rate "
            "limit in this Region. This is a transient capacity condition, not a "
            "template or permission problem; the same deployment can succeed on "
            "retry once the call rate drops."
        ),
        verification=(
            "Retry the deployment after a pause; if this recurs, add backoff or retries around the deploy step instead of changing the template.",
            "Reduce the number of parallel stack operations from CI (matrix jobs, monorepo fan-out) targeting the same account and Region.",
            "Check for other automation (drift detection, scheduled deployments, dashboards polling DescribeStacks) hammering CloudFormation in the same account and Region, and request a quota increase only if the steady-state rate is genuinely higher.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-limits.html",
    ),
    Rule(
        id="sam.template.invalid-property",
        title="A SAM template property is not valid for its resource type",
        confidence="high",
        patterns=(
            r"property\s+\S+:\s+not defined for resource of type AWS::Serverless::",
        ),
        explanation=(
            "SAM rejected a property key that is not defined for the resource type. "
            "This is commonly a misspelling, punctuation error in the key, or a property "
            "copied from a different SAM or CloudFormation resource."
        ),
        verification=(
            "Compare the exact property key in the template with the reference for the resource type named in the error.",
            "Check for punctuation accidentally included in a YAML or JSON property name before changing related API configuration.",
            "Run `sam validate` after correcting the template shape.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-api.html",
    ),
    Rule(
        id="sam.template.schema-validation-failed",
        title="The template failed SAM or CloudFormation schema validation",
        confidence="high",
        patterns=(
            r"InvalidSamDocumentException",
            r"InvalidResourceException",
            r"Encountered unsupported property",
            r"property\s+\S+\s+not defined for resource of type",
        ),
        explanation=(
            "SAM or CloudFormation rejected the template before creating any "
            "resource: the document failed schema validation, or a resource "
            "type does not recognize one of its properties. This is commonly "
            "an indentation mistake, a property nested at the wrong level, or "
            "a missing `Transform: AWS::Serverless-2016-10-31` line."
        ),
        verification=(
            "Run `sam validate --lint` locally and in CI before deploying.",
            "Compare the resource id and property path named in the error with the reference for that resource type.",
            "Confirm the template still has its `Transform: AWS::Serverless-2016-10-31` line when it declares SAM resource types.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-validate.html",
        suppressed_by=(
            r"property\s+\S+:\s+not defined for resource of type AWS::Serverless::",
        ),
    ),
    Rule(
        id="cloudformation.template.getatt-parameters-invalid",
        title="Fn::GetAtt parameters are malformed",
        confidence="high",
        patterns=(
            r"every Fn::GetAtt object requires two non-empty parameters",
        ),
        explanation=(
            "CloudFormation rejected the template before changing any resources "
            "because one `Fn::GetAtt` expression does not contain exactly two "
            "non-empty parts: a logical resource id and an attribute name. The "
            "error does not identify which occurrence is malformed."
        ),
        verification=(
            "Search the exact submitted or synthesized template for every `Fn::GetAtt` and `!GetAtt` occurrence.",
            "Write the long form as `Fn::GetAtt: [LogicalResourceId, AttributeName]` or the short form as `!GetAtt LogicalResourceId.AttributeName`.",
            "Validate the corrected template before creating the change set again; for SAM, run `sam validate --lint` against the template you deploy.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html",
    ),
    Rule(
        id="iam.trust-policy.resource-field-invalid",
        title="An IAM role trust policy contains a permissions-only Resource field",
        confidence="high",
        patterns=(r"Has prohibited field Resource",),
        explanation=(
            "IAM rejected the role trust policy because it contains a `Resource` field. "
            "A role trust policy defines who may assume the role; permissions on AWS "
            "resources belong in an identity policy attached to that role."
        ),
        verification=(
            "Inspect the role's `AssumeRolePolicyDocument` and remove `Resource` or `NotResource` elements from that trust policy.",
            "Keep the trusted principal and `sts:AssumeRole` action in the trust policy.",
            "Move service permissions to the role's `Policies` or `ManagedPolicyArns`, then review the least-privilege scope.",
        ),
        documentation_url="https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-reference-policy-checks.html",
    ),
    Rule(
        id="lambda.code-signing.image-incompatible",
        title="Lambda code signing is incompatible with a container-image function",
        confidence="high",
        patterns=(
            r"Code signing is not supported for functions created with container images",
        ),
        explanation=(
            "Lambda does not support a code signing configuration for a function packaged "
            "as a container image. The template must use a supported packaging and signing "
            "combination."
        ),
        verification=(
            "Confirm whether the function uses `PackageType: Image` or an image URI.",
            "Remove the code signing configuration for an image-packaged function, or switch to a signed ZIP deployment package if code signing is required.",
            "Review the function's deployment and integrity requirements before changing package type.",
        ),
        documentation_url="https://docs.aws.amazon.com/lambda/latest/dg/configuration-codesigning-create.html",
    ),
    Rule(
        id="s3.bucket-name.invalid",
        title="An S3 bucket name failed AWS validation",
        confidence="high",
        patterns=(
            r"Error Code:\s*InvalidBucketName",
            r"The specified bucket is not valid",
        ),
        explanation=(
            "S3 rejected the bucket name before deployment could continue. The configured "
            "or generated name violates S3 naming rules; this is distinct from a bucket "
            "that already exists or a missing permission."
        ),
        verification=(
            "Inspect the configured deployment bucket and any environment-derived suffix used to construct its name.",
            "Check for uppercase letters, underscores, invalid length, adjacent periods, an IP-address-like form, or invalid leading and trailing characters.",
            "Use a unique, lowercase bucket name that satisfies the documented S3 naming rules.",
        ),
        documentation_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html",
    ),
    Rule(
        id="s3.bucket-name.already-taken",
        title="An S3 bucket name in the template is already taken",
        confidence="high",
        patterns=(
            r"BucketAlreadyExists",
            r"BucketAlreadyOwnedByYou",
            # Newer CloudFormation resource handlers wrap the same collision in
            # prose and report the generic `HandlerErrorCode: AlreadyExists`.
            # That code is shared by every resource type, so it is never matched
            # on its own - only this S3-specific sentence is.
            #
            # That sentence was described here and never actually added, so the
            # wrapped form went undiagnosed: a real log reading `"my-app-logs
            # already exists (Service: S3, Status Code: 409)" (HandlerErrorCode:
            # AlreadyExists)` produced no finding at all. `Service: S3` is what
            # keeps it specific - the handler code alone would claim a Lambda or a
            # table that already exists as a bucket-name collision.
            r"already exists\s*\(Service:\s*S3\b",
            r"The requested bucket name is not available",
        ),
        explanation=(
            "S3 bucket names are globally unique across every AWS account, so the "
            "explicit `BucketName` the stack asked for could not be created. "
            "`BucketAlreadyExists` means some other account already holds the name; "
            "`BucketAlreadyOwnedByYou` means this account already has the bucket, "
            "usually left behind by a deleted or renamed stack. Newer resource "
            "handlers report the same collision as \"The requested bucket name is "
            "not available\" with `HandlerErrorCode: AlreadyExists`. This is a name "
            "collision, not an invalid name and not a missing permission."
        ),
        verification=(
            "Read the failed `AWS::S3::Bucket` event and record the exact bucket name the stack requested.",
            "For `BucketAlreadyExists`, pick a name that is unique globally - add an account or environment suffix - or omit `BucketName` entirely and let CloudFormation generate one.",
            "For `BucketAlreadyOwnedByYou`, confirm the leftover bucket with `aws s3api head-bucket --bucket <name>` (read-only) and check its contents before reusing the name; import the existing bucket into the stack or rename, and do not delete a bucket you have not inspected.",
        ),
        documentation_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html",
    ),
    Rule(
        id="s3.lifecycle.abort-multipart-tag-filter",
        title="An S3 lifecycle abort rule cannot use a tag filter",
        confidence="high",
        patterns=(_S3_ABORT_MULTIPART_TAG_FILTER_PATTERN,),
        explanation=(
            "S3 rejected a lifecycle rule because `AbortIncompleteMultipartUpload` "
            "cannot be combined with a tag-based filter. Incomplete multipart uploads "
            "do not carry object tags yet, so S3 cannot evaluate that filter for the "
            "abort action."
        ),
        verification=(
            "Find the lifecycle rule on the affected bucket and separate the multipart-abort action from any tag-filtered expiration or transition rule.",
            "Keep the abort rule unfiltered or scope it with an object-key prefix; use a separate rule for tag-based object actions.",
            "Read the current configuration before editing it with `aws s3api get-bucket-lifecycle-configuration --bucket <bucket>` (read-only).",
        ),
        documentation_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-configuration-examples.html",
    ),
    Rule(
        id="cloudformation.lambda-layer.artifact-unreadable",
        title="CloudFormation cannot read a Lambda layer artifact from S3",
        confidence="high",
        patterns=(
            r"access has been denied by S3.*permission.*GetObject",
            r"permission to GetObject for.*bucket",
        ),
        explanation=(
            "The deployment could not retrieve the S3 object used for a Lambda layer. "
            "The deployment or CloudFormation execution identity needs access to the exact "
            "artifact, and encryption controls can impose an additional requirement."
        ),
        verification=(
            "Identify the identity that CloudFormation uses for the stack operation and the exact layer archive object ARN.",
            "Allow `s3:GetObject` for that object while checking bucket-policy denies and cross-account ownership.",
            "If the artifact uses a customer-managed KMS key, verify the identity also has the required decrypt permission.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-lambda-layerversion-content.html",
    ),
    Rule(
        id="sam.build.docker-required",
        title="SAM build requires Docker for containerized builds",
        confidence="high",
        patterns=(
            r"Cannot connect to the Docker daemon",
            # `Error response from daemon` is deliberately NOT matched here. The
            # daemon producing a response is proof it is running, so treating it
            # as evidence of an unreachable daemon inverts the meaning - a pull
            # denial, a missing tag, a full disk and a platform mismatch were all
            # reported as "Docker is unavailable", each with the wrong fix. The
            # two rules below claim the cases worth naming; anything else is left
            # unmatched on purpose, because "no supported pattern found" with a
            # rule-request prompt costs less than a confident wrong answer.
            r"Error:\s*Docker is unavailable or not running",
            r"Building image for .* requires Docker\.",
            r"sam build --use-container.*(?:cannot execute|executable file not found|not found|is not recognized|command not found)",
            r"is the docker daemon running\?",
            r"is docker running\?",
            r"No such file or directory.*docker\.sock",
            r"sh: docker: not found",
        ),
        explanation=(
            "The build job reached a containerized SAM build path and could not reach "
            "a usable Docker daemon. Container builds require Docker even for transient "
            "validation steps in CI."
        ),
        verification=(
            "Run `docker version` on the failing runner and confirm Docker is started.",
            "If using a self-hosted runner, check permissions for `docker.sock` and that the Docker service is running.",
            "If Docker is not available in your environment, disable containerized build paths (`sam build` without `--use-container`) and retry.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html#sam-cli-command-reference-sam-build-use-container",
    ),
    Rule(
        id="docker.registry.image-unavailable",
        title="The build could not pull a container image from the registry",
        confidence="high",
        patterns=(
            r"pull access denied for \S+",
            r"repository does not exist or may require ['\"]?docker login",
            r"manifest for \S+ not found",
            r"manifest unknown",
        ),
        explanation=(
            "Docker reached the registry and was refused, or asked for a tag the "
            "registry does not have. The daemon is running - it returned this "
            "error - so this is not a Docker-availability problem. Registries "
            "answer an unauthenticated request for a private image and a request "
            "for a missing image almost identically, which is why the message "
            "mentions both possibilities: either the runner is not logged in to "
            "that registry, or the image and tag really are absent (a tag that "
            "was never pushed, or one built for a different architecture)."
        ),
        verification=(
            "Pull the exact image and tag from the failing runner to reproduce it outside SAM: `docker pull <image>:<tag>`.",
            "For a private registry, log in first in the same job - `aws ecr get-login-password | docker login --username AWS --password-stdin <registry>` for ECR, or the equivalent action - and confirm the login step runs before the build.",
            "Confirm the tag exists: `aws ecr describe-images --repository-name <repo> --image-ids imageTag=<tag>`, or the registry's own listing.",
            "Check the image's architecture matches the function: an arm64-only image requested for an x86_64 build reports as a missing manifest.",
        ),
        documentation_url="https://docs.aws.amazon.com/AmazonECR/latest/userguide/registry_auth.html",
        # No suppression against the ECR-login rule on purpose. The two patterns
        # cannot match the same line, and a job that fails to authenticate for a
        # push can separately be refused a pull - reporting both is right, and
        # suppressing for the whole log would drop one of two real failures.
    ),
    Rule(
        id="build.host.disk-full",
        title="The build host ran out of disk space",
        confidence="high",
        patterns=(
            r"no space left on device",
            r"\bENOSPC\b",
        ),
        explanation=(
            "The build wrote until the filesystem was full. On a hosted CI runner "
            "this is usually not the project's own output: a container build "
            "keeps every intermediate layer, dependency caches accumulate across "
            "steps, and the runner image itself already occupies much of the "
            "disk. The failure often surfaces in an unrelated-looking step - "
            "whichever one happened to need the next block - so the step that "
            "reports it is not necessarily the step at fault."
        ),
        verification=(
            "Print the disk state at the point of failure to confirm it and see what is consuming it: `df -h` and `docker system df`.",
            "Reclaim space in the job before the build step: `docker system prune -af` and remove any large caches restored earlier in the workflow.",
            "On GitHub-hosted runners, free the preinstalled toolchains you do not use (the several gigabytes under `/usr/share/dotnet`, `/usr/local/lib/android`, `/opt/ghc`) before building.",
            "If the build genuinely needs more room than the runner has, move it to a larger runner rather than pruning further.",
        ),
        documentation_url="https://docs.docker.com/engine/manage-resources/pruning/",
    ),
    Rule(
        id="lambda.package.size-limit-exceeded",
        title="The Lambda deployment package exceeds a per-function size limit",
        confidence="high",
        patterns=(
            r"Unzipped size must be smaller than",
            r"Request must be smaller than .* bytes",
        ),
        explanation=(
            "The function's code package - whether measured zipped or after unzipping - "
            "exceeds one of AWS Lambda's per-function size limits, so CreateFunction/"
            "UpdateFunctionCode failed. This is a per-function packaging limit, not the "
            "regional code-storage quota."
        ),
        verification=(
            "Measure the built artifact size locally before deploying to catch this before AWS does.",
            (
                "List the largest files inside the zip to find what's bloating the package "
                "(e.g. `unzip -l function.zip | sort -k1 -n -r | head`)."
            ),
            (
                "Move shared dependencies into a Lambda layer, trim dev/test-only dependencies "
                "from the deployment package, or switch to a container image (up to 10 GB) if the "
                "package is genuinely large."
            ),
        ),
        documentation_url="https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html",
        excluded_line_patterns=(
            r"CodeStorageExceededException",
            r"Code storage limit exceeded",
        ),
    ),
    Rule(
        id="apigateway.deployment.no-methods",
        title="API Gateway deployment started before the API had any methods",
        confidence="high",
        patterns=(r"The REST API does(?:n't| not) contain any methods",),
        explanation=(
            "API Gateway rejected the deployment because no methods existed when the "
            "deployment resource was created. This often happens when a SAM-generated "
            "deployment is combined with a manually declared `AWS::ApiGateway::Deployment`."
        ),
        verification=(
            "Check whether the template declares a manual `AWS::ApiGateway::Deployment` alongside `AWS::Serverless::Api`.",
            "Prefer SAM's generated API deployment, or add `DependsOn` entries for every required API method when managing deployments manually.",
            "Review the transformed template and the affected API Gateway methods before redeploying.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-apigateway-deployment.html",
    ),
    Rule(
        id="cloudformation.resource.stabilization-timeout",
        title="A resource was accepted by its service but never reached a stable state",
        confidence="high",
        patterns=(
            r"did not stabilize",
            r"HandlerErrorCode:\s*NotStabilized",
            r"Exceeded attempts to wait",
        ),
        explanation=(
            "The service accepted CloudFormation's create or update call, but the "
            "resource never reached its steady state within the wait window, so "
            "CloudFormation gave up and failed the operation. The stabilization "
            "wording is only the wrapper: the real cause is the nested status "
            "reason from the service handler when the log includes one, a "
            "resource that is genuinely slow to provision, or a handler that "
            "never signals completion."
        ),
        verification=(
            "Find the quoted message inside `Resource handler returned message` (or the resource's own event in the service console) and treat that nested reason as the failure to fix; only fall back to the guidance below when there is none.",
            "For slow-by-design resources - ACM certificates waiting on DNS validation, CloudFront distributions, RDS instances - confirm the external dependency (validation records, quotas) and retry; the same template often succeeds once the dependency clears.",
            "For custom resources and third-party handlers, check the handler function's own logs for the invocation: a handler that crashed or never sent its response leaves CloudFormation waiting until the timeout.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html",
        parse_stabilization_context=True,
    ),
    Rule(
        id="cloudformation.nested-stack.propagation-failed",
        title="A nested (embedded) stack failed - the root cause is in the child stack's events",
        confidence="high",
        patterns=(
            r"Embedded stack .* was not successfully (?:created|updated)",
            r"Embedded stack .*The following resource\(s\) failed to (?:create|update):",
        ),
        explanation=(
            "The parent stack's message only says an embedded stack failed - that is "
            "a symptom, not the cause. The real root cause lives in the child stack's "
            "own event stream, and CloudFormation can delete the child stack (and its "
            "events) as part of rollback before anyone reads them."
        ),
        verification=(
            (
                "Capture the child stack's events before rollback deletes them, or "
                "redeploy with `--disable-rollback` to keep the stack around while debugging."
            ),
            (
                "Run `aws cloudformation describe-stack-events --stack-name "
                "<child-stack-arn>` with the full nested stack ARN from this "
                "message - it still works once deletion has started."
            ),
            (
                "Find the child stack's first `CREATE_FAILED` or `UPDATE_FAILED` "
                "resource event and fix that; only edit the parent template after that."
            ),
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-nested-stacks.html",
    ),
    Rule(
        id="cloudformation.resource.create-update-failed",
        title="CloudFormation resource creation or update failed",
        confidence="high",
        patterns=(r"\bCREATE_FAILED\b", r"\bUPDATE_FAILED\b"),
        explanation=(
            "A CloudFormation resource failed before the stack rollback completed. "
            "Its status reason is usually the most direct evidence for the root cause."
        ),
        verification=(
            "Identify the failed logical resource ID and preserve its exact status reason.",
            "Check the underlying service event or API error named in that status reason.",
            "Fix the resource-level cause before retrying the stack operation.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/view-stack-events.html",
        # These reasons arrive on their own line, below the CREATE_FAILED event
        # they explain, so excluding the reason line would leave the event line
        # still matching and report one failure twice. They have to suppress
        # the whole rule, which does mean an unrelated failure in the same log
        # goes unreported - the lesser of the two evils here.
        suppressed_by=(
            r"(?s:access has been denied by S3.*permission.*GetObject)",
            r"Code signing is not supported for functions created with container images",
            r"Lambda does not have permission to access the ECR image",
        ),
        # Every other overlap puts the reason on the CREATE_FAILED line itself,
        # so excluding that line lets the specific rule explain its resource
        # while this rule keeps reporting the stack's other failures. Stacks
        # rarely fail exactly one resource, and dropping the rest of them from
        # the report is the opposite of useful.
        excluded_line_patterns=(
            r"Has prohibited field Resource",
            r"Error Code:\s*InvalidBucketName",
            r"The specified bucket is not valid",
            r"BucketAlreadyExists",
            r"BucketAlreadyOwnedByYou",
            r"The REST API does(?:n't| not) contain any methods",
            r"did not stabilize",
            r"HandlerErrorCode:\s*NotStabilized",
            r"Exceeded attempts to wait",
            r"cannot be (?:updated|deleted) as it is in use by",
            r"CodeStorageExceededException",
            r"Code storage limit exceeded",
            r"ReservedConcurrentExecutions for function decreases account's UnreservedConcurrentExecution below its minimum value",
            r"Embedded stack .* was not successfully (?:created|updated)",
            _CODEBUILD_CODECONNECTIONS_FAILURE_PATTERN,
            _S3_ABORT_MULTIPART_TAG_FILTER_PATTERN,
            # The KMS env-var rule explains the same event and names the key
            # checks; CloudFormation prints both on one line here.
            *_LAMBDA_ENV_KMS_FAILURE_PATTERNS,
        ),
    ),
    Rule(
        id="lambda.env-vars.kms-key-inaccessible",
        title="Lambda could not use the KMS key for its environment variables",
        confidence="high",
        patterns=_LAMBDA_ENV_KMS_FAILURE_PATTERNS,
        explanation=(
            "Lambda encrypts environment variables with a customer-managed KMS "
            "key, and it could not use the configured key. The wrapper error is "
            "a Lambda `InvalidParameterValueException`, which reads like a bad "
            "template value - the real cause is the `KMS Exception:` inside it. "
            "Three causes account for nearly all of these, and they need "
            "different fixes: the key policy or grants do not let the "
            "deploying principal, Lambda service, or function execution role "
            "use the key (`AccessDeniedException`); the key is "
            "disabled or pending deletion, which fails even when every policy "
            "is correct (`DisabledException`, `KMSInvalidStateException`); or "
            "the key ARN is malformed, or names another Region or account "
            "(`InvalidArnException`, `NotFoundException`), which no permission "
            "change can fix."
        ),
        verification=(
            "Read the exception name after `KMS Exception:` first - it separates a policy problem from a key-state problem from a bad ARN.",
            "Confirm the key exists and check its state in the function's own Region: `aws kms describe-key --key-id <key-arn>`, then read `KeyState` (a `Disabled` or `PendingDeletion` key fails this way regardless of policy).",
            "Review the key policy and grants for both the deploying principal and the function's execution role; do not begin by broadly changing IAM identity policies.",
            "Confirm `kms:CreateGrant`, `kms:Encrypt`, and `kms:DescribeKey` for the deployment and Lambda grant path, plus `kms:Decrypt` wherever the execution role actually decrypts values.",
            "If the ARN is malformed or points at another Region, correct `KmsKeyArn` in the template - a Lambda function can only use a key in its own Region. For a cross-account key, confirm the owning account's key policy and any existing grant permit the deployment path.",
            "After correcting the key policy, key state, or ARN, re-save or re-encrypt the function's environment configuration and redeploy it.",
        ),
        documentation_url="https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html",
    ),
    Rule(
        id="lambda.code-storage.limit-exceeded",
        title="AWS Lambda code storage limit exceeded",
        confidence="high",
        patterns=(
            r"CodeStorageExceededException",
            r"Code storage limit exceeded",
        ),
        explanation=(
            "AWS Lambda reached the regional code storage limit (default 75 GB) for your account. "
            "This total includes all present and past deployed function code, layers, and saved function versions across the region."
        ),
        verification=(
            "Check total or current storage usage using `aws lambda get-account-settings`.",
            "List unused or old function versions using `aws lambda list-versions-by-function`.",
            "Delete unnecessary versions with `aws lambda delete-function --qualifier <version>` or set up automated lifecycle cleanup.",
        ),
        documentation_url="https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html",
    ),
    Rule(
        id="lambda.concurrency.reserved-below-minimum",
        title="Reserved concurrency would drop the account below its minimum unreserved value",
        confidence="high",
        patterns=(
            r"ReservedConcurrentExecutions for function decreases account's UnreservedConcurrentExecution below its minimum value",
        ),
        explanation=(
            "The account's total concurrency limit minus every function's "
            "`ReservedConcurrentExecutions` must leave at least the account "
            "minimum (usually 100) unreserved for functions that reserve "
            "nothing. This is an account-level ceiling, not a template-syntax "
            "or permissions problem - it is especially common on a fresh "
            "account, where the concurrency limit can still be at the 1,000 "
            "default, or lower in a new or burst-limited account, sometimes "
            "as low as 10-50, where no reservation is possible at all."
        ),
        verification=(
            "Run `aws lambda get-account-settings` (read-only) to see the account's concurrency limit and its current unreserved value.",
            "Sum `ReservedConcurrentExecutions` across every function in the account, not just the one in this template, to see how much is already committed.",
            "Either lower or remove the reservation in the template, or request a concurrency quota increase for the account and retry.",
        ),
        documentation_url="https://docs.aws.amazon.com/lambda/latest/dg/lambda-concurrency.html",
    ),
    Rule(
        id="cloudformation.stack.operation-in-progress",
        title="Another CloudFormation operation is already in progress on the stack",
        confidence="high",
        patterns=(
            r"is in (?:CREATE|UPDATE|DELETE)_IN_PROGRESS state and (?:can not|cannot) be updated",
            r"OperationInProgressException",
        ),
        explanation=(
            "CloudFormation rejected the deployment because another operation is "
            "still running on the same stack - a concurrent CI run, a teammate's "
            "deploy, or a console operation. The new operation cannot start until "
            "the in-flight one finishes."
        ),
        verification=(
            "Check for a concurrent deployment against the same stack and let it finish before retrying.",
            "Run `aws cloudformation describe-stack-events --stack-name <stack>` (read-only) to see the in-flight operation and how far it has progressed.",
            "Serialize CI deploys to the same stack with a GitHub Actions `concurrency` group keyed by stack name.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html",
    ),
    Rule(
        id="cloudformation.stack.failed-recreate-required",
        title="A failed initial stack must be recreated before it can be deployed again",
        confidence="high",
        patterns=(
            r"ROLLBACK_COMPLETE.*(?:can not|cannot) be updated",
            r"is in ROLLBACK_COMPLETE state.*(?:can not|cannot) be updated",
        ),
        explanation=(
            "CloudFormation cannot update a stack that finished rolling back after an "
            "initial create failure. The original failed resource must be understood and "
            "fixed before a new stack operation can succeed."
        ),
        verification=(
            "Find the first earlier `CREATE_FAILED` resource event and fix that underlying cause first.",
            "For an initial deployment with no stable prior stack, delete the failed stack after reviewing its resources, then deploy again with the same name.",
            "Do not delete or retain resources blindly; confirm the stack state and intended cleanup path in CloudFormation first.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-continueupdaterollback.html",
    ),
    Rule(
        id="cloudformation.stack.update-rollback-failed",
        title="Stack rollback itself failed and must be continued or skipped",
        confidence="high",
        patterns=(
            r"UPDATE_ROLLBACK_FAILED.*(?:can not|cannot) be updated",
            r"is in UPDATE_ROLLBACK_FAILED state.*(?:can not|cannot) be updated",
        ),
        explanation=(
            "CloudFormation tried to roll back a failed update, but the rollback itself "
            "failed and the stack is stuck in UPDATE_ROLLBACK_FAILED. No new operation can "
            "start until the rollback is continued past, or explicitly skips, the resource "
            "that would not roll back."
        ),
        verification=(
            "Find the resource event that caused the rollback to fail in `aws cloudformation describe-stack-events`.",
            "Run `aws cloudformation continue-update-rollback --stack-name <stack>`, adding `--resources-to-skip <resource>` only for resources confirmed unable to roll back.",
            "Confirm the stack reaches UPDATE_ROLLBACK_COMPLETE before retrying the deploy.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html#troubleshooting-errors-update-rollback-failed",
    ),
    Rule(
        id="cloudformation.stack.rollback-complete",
        title="CloudFormation stack entered rollback after an earlier resource failure",
        confidence="medium",
        patterns=(
            r"ROLLBACK_IN_PROGRESS",
            r"ROLLBACK_FAILED",
            r"ROLLBACK_COMPLETE",
            r"UPDATE_ROLLBACK",
        ),
        explanation=(
            "Rollback is a downstream stack state. The most useful evidence is usually "
            "the first failed resource event that appears before the rollback entries."
        ),
        verification=(
            "Inspect stack events in chronological order and locate the first `CREATE_FAILED` or `UPDATE_FAILED` resource.",
            "If the stack is in `ROLLBACK_FAILED`, inspect the failed cleanup event and resolve that blocker before retrying the rollback or deletion.",
            "Preserve the exact resource status reason before retrying the deployment.",
            "Use a change set or isolated stack when testing a fix, where practical.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/determine-root-cause-for-stack-failures.html",
        # An immutable initial-create rollback state, a failed rollback that
        # needs continuing/skipping, and a role-deletion blocker each have a
        # more precise dedicated finding.
        suppressed_by=(
            r"ROLLBACK_COMPLETE.*(?:can not|cannot) be updated",
            r"UPDATE_ROLLBACK_FAILED.*(?:can not|cannot) be updated",
            r"following resource\(s\) failed to delete",
            r"failed to delete.*AWS::IAM::Role",
            r"Unable to delete.*AWS::IAM::Role",
            r"Embedded stack .* was not successfully (?:created|updated)",
        ),
    ),
    Rule(
        id="cloudformation.rollback.iam-role-delete-failed",
        title="CloudFormation rollback could not delete an IAM role",
        confidence="medium",
        patterns=(
            r"The following resource\(s\) failed to delete:.*Role",
            r"failed to delete.*IAM Role",
            r"Unable to delete.*AWS::IAM::Role",
        ),
        explanation=(
            "CloudFormation could not remove an IAM role during rollback or deletion. "
            "The rollback may stop even after the root failure is fixed, blocking clean "
            "retries until the dependency is released."
        ),
        verification=(
            "Find the IAM role and inspect its attached managed policies, inline policies, "
            + "and role attachments (including instance profiles).",
            "Temporarily detach blockers or confirm deletion permissions, then retry rollback "
            + "or delete the stack with resources retained as required.",
            "Re-run deployment only after the stack can transition cleanly past the rollback phase.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-deleting-stack.html",
    ),
    Rule(
        id="cloudformation.stack.termination-protection",
        title="Stack deletion is blocked by termination protection",
        confidence="high",
        patterns=(r"cannot be deleted while TerminationProtection is enabled",),
        explanation=(
            "CloudFormation refused the delete because termination protection is "
            "enabled on the stack. Someone turned that protection on deliberately, "
            "so the refusal is a safeguard rather than a failure."
        ),
        verification=(
            "Confirm the stack name, account, and Region match the stack you intend to remove.",
            "Find out why termination protection was enabled before removing it; the stack may be shared or load-bearing.",
            "Only after confirming the stack is safe to remove, disable protection (`aws cloudformation update-termination-protection --no-enable-termination-protection`) and retry the delete.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-protect-stacks.html",
    ),
    Rule(
        id="cloudformation.stack.delete-failed",
        title="CloudFormation could not delete one or more stack resources",
        confidence="medium",
        patterns=(r"\bDELETE_FAILED\b",),
        explanation=(
            "A stack or resource deletion failed. The status reason usually names "
            "the blocker directly: a non-empty S3 bucket, a network interface "
            "still attached to a Lambda function, a nested stack with its own "
            "failure, or a resource another stack depends on."
        ),
        verification=(
            "Identify the blocking resource and preserve its exact status reason before changing anything.",
            "Resolve the blocker deliberately - empty the bucket, wait for or detach the network interface, fix the nested stack - rather than force-deleting anything.",
            "If a resource should survive the stack, retry with `aws cloudformation delete-stack --retain-resources` for that logical ID after the blocker is understood.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html",
        # A role deletion blocker keeps its dedicated, more actionable finding,
        # and an in-use export refusal is a dependency safeguard with its own
        # migration path rather than a resource-deletion failure.
        suppressed_by=(
            r"The following resource\(s\) failed to delete:.*Role\b",
            r"failed to delete.*IAM Role",
            r"Unable to delete.*AWS::IAM::Role",
            r"cannot be (?:updated|deleted) as it is in use by",
        ),
    ),
    Rule(
        id="cloudformation.export.in-use",
        title="A stack export cannot change while another stack imports it",
        confidence="high",
        patterns=(
            r"Export\s+\S+\s+cannot be (?:updated|deleted) as it is in use by",
            r"Cannot (?:update|delete) (?:an )?export\s+\S+\s+as it is in use",
        ),
        explanation=(
            "CloudFormation refused to change or remove an exported output "
            "because at least one other stack imports it with `Fn::ImportValue`. "
            "This is a dependency safeguard, not a failure in the exporting "
            "stack: consumers pin the export's name and value until they stop "
            "importing it."
        ),
        verification=(
            "List every consumer with `aws cloudformation list-imports --export-name <name>` and record which stacks pin the export.",
            "Migrate in stages: add a new export alongside the old one, update each consumer stack to import the new name, then remove the old export once `list-imports` shows no consumers.",
            "Do not delete or force-update the consumer stacks as a shortcut - they are load-bearing for whoever owns them; coordinate the migration with those owners instead.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-exports.html",
    ),
    Rule(
        id="cloudformation.capabilities.required",
        title="CloudFormation needs an explicit capability acknowledgement",
        confidence="high",
        patterns=(
            r"InsufficientCapabilities(?:Exception)?",
            r"Requires capabilities\s*:\s*\[?CAPABILITY_(?:IAM|NAMED_IAM|AUTO_EXPAND)",
        ),
        explanation=(
            "CloudFormation rejected the change set because the deployment did not "
            "explicitly acknowledge a capability required by the template. The error "
            "identifies the capability that must be reviewed before retrying."
        ),
        verification=(
            "Read the capability named in the error and inspect the relevant template resources before changing deployment settings.",
            "For IAM resources, configure `CAPABILITY_IAM`; use `CAPABILITY_NAMED_IAM` when the template gives IAM resources custom names.",
            "For nested applications, configure `CAPABILITY_AUTO_EXPAND`, then review the expanded application and proposed change set.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html",
    ),
    Rule(
        id="cloudformation.template.quota-exceeded",
        title="The template exceeds a CloudFormation size or count quota",
        confidence="medium",
        patterns=(
            r"Value at 'template(?:Body|URL)' failed to satisfy constraint: Member must have length less than or equal to",
            r"Template format error: Number of \S+ .{0,40}is greater than maximum allowed",
            r"Template (?:body )?may not exceed [\d,]+ bytes",
        ),
        explanation=(
            "CloudFormation rejected the template itself, before evaluating any "
            "resource, because it is past a service quota: the template body is "
            "larger than the limit for how it was submitted (51,200 bytes inline, "
            "460,800 bytes from S3), or it declares more resources, parameters, or "
            "outputs than a stack may hold. No template change other than shrinking "
            "or splitting it will get past this."
        ),
        verification=(
            "Measure the rendered template before deploying - `wc -c .aws-sam/build/template.yaml` - and compare it with the byte limit named in the error.",
            "Submit the template through S3 rather than inline: `sam deploy --resolve-s3` (or an explicit `--s3-bucket`) raises the ceiling to 460,800 bytes, and `aws cloudformation validate-template --template-url <s3-url>` confirms it read-only.",
            "For a count quota, read the number the error reports and move part of the stack into nested stacks or a separate stack; the CloudFormation quotas page lists the current per-stack maximums.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-limits.html",
    ),
    Rule(
        id="sam.deploy.bucket-config-conflict",
        title="SAM deployment configured both a managed and explicit S3 bucket",
        confidence="high",
        patterns=(r"Cannot use both --resolve-s3 and --s3-bucket parameters",),
        explanation=(
            "The deployment selected two mutually exclusive artifact-bucket mechanisms. "
            "SAM cannot both resolve a managed S3 bucket and use an explicit `--s3-bucket` "
            "in the same command."
        ),
        verification=(
            "Inspect the selected `samconfig.toml` environment and the workflow's `sam deploy` arguments together.",
            "For a pipeline that passes `--s3-bucket`, disable `resolve_s3` in that deployment configuration.",
            "Alternatively, remove the explicit bucket and let SAM resolve its managed bucket; keep exactly one mechanism.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html",
    ),
    Rule(
        id="sam.build.esbuild-missing",
        title="SAM build cannot find the configured esbuild dependency",
        confidence="high",
        patterns=(
            r"NodejsNpmEsbuildBuilder:EsbuildBundle.*(?:Cannot|can not) find esbuild",
            r"Esbuild Failed:\s*(?:Cannot|can not) find esbuild",
        ),
        explanation=(
            "A function configured with `BuildMethod: esbuild` reached SAM's esbuild "
            "builder, but the bundler was not available in the project or runner "
            "environment used for the build."
        ),
        verification=(
            "Declare a compatible `esbuild` version in the function project's development dependencies and commit its lockfile.",
            "Run the matching package-manager install step before `sam build` in CI.",
            "Confirm the workflow builds the same directory that contains the function's `package.json`.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/building-typescript.html",
    ),
    Rule(
        id="sam.build.python-dependency-resolution-failed",
        title="SAM Python dependency resolution failed",
        confidence="high",
        patterns=(
            # The trailing " - " matters: SAM prints
            # `Running PythonPipBuilder:ResolveDependencies` as ordinary progress
            # on every successful Python build, and only the failure carries a
            # continuation (`Error: PythonPipBuilder:ResolveDependencies - {...}`).
            # Matching the bare token reported a high-confidence dependency
            # failure for a clean build.
            r"PythonPipBuilder:ResolveDependencies\s+-",
            r"Could not find a version that satisfies the requirement",
        ),
        explanation=(
            "SAM could not resolve one or more Python dependencies during "
            "build. The failure usually comes from a pinned package/version that "
            "is not available for the build environment."
        ),
        verification=(
            "Check the package and pin in the function dependency file and confirm it is available for the target architecture and Python version.",
            "Reproduce with a local `pip install` using the same build-time Python version to confirm the missing/invalid requirement.",
            "Align constraints with a build-compatible version or wheel source and retry.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html",
        suppressed_by=(r"Binary validation failed",),
    ),
    Rule(
        id="sam.build.python-runtime-mismatch",
        title="SAM Python runtime binary is incompatible with the build runtime",
        confidence="high",
        patterns=(
            r"PythonPipBuilder:Validation - Binary validation failed for python",
            r"Python executable.*not found",
            r"Your build environment.*runtime.*python",
            r"The runtime python[0-9.]+ binary was not found",
            r"Do you have python for runtime",
        ),
        explanation=(
            "SAM reached Python binary validation and confirmed the builder did not "
            "have a matching interpreter for the SAM function runtime."
        ),
        verification=(
            "Compare the function runtime in the template (for example `python3.12`) to the local/interpreter runtime used by the build.",
            "Use a matching SAM build image or pinned runtime image that provides the required Python binary.",
            "If using native extensions, prefer `sam build --use-container` with a container that matches the SAM runtime.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html",
    ),
    Rule(
        id="sam.build.python-dependency-validation-failed",
        title="SAM Python dependency build validation failed",
        confidence="high",
        patterns=(r"Binary validation failed",),
        explanation=(
            "SAM reached the Python dependency validation path and failed before a "
            "build artifact was produced. Keep the fix specific to the highest-confidence "
            "scenario in the failure output."
        ),
        verification=(
            "Compare the Python runtime in the build environment with the runtime declared in the SAM template.",
            "Reproduce locally with `sam build --debug` to capture the full dependency failure and missing module output.",
            "Use lockfile-pinned dependencies and compatible wheels, then retry with a clean build environment.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html",
        suppressed_by=(
            r"PythonPipBuilder:Validation - Binary validation failed",
            r"Python executable.*not found",
            r"Could not find a version that satisfies the requirement",
        ),
    ),
    Rule(
        id="cloudformation.deploy.no-changes",
        title="The deployment failed only because there were no changes to deploy",
        confidence="high",
        patterns=(
            r"No changes to deploy\.?\s*Stack .{0,120}is up to date",
            r"The submitted information didn't contain changes",
            r"No updates are to be performed",
        ),
        explanation=(
            "The stack already matches the template, so CloudFormation produced an "
            "empty change set and the deploy command exited with an error. In a "
            "pipeline this is usually a configuration choice, not a real failure."
        ),
        verification=(
            "For automated pipelines, pass `--no-fail-on-empty-changeset` to `sam deploy` "
            + "(or set `fail_on_empty_changeset = false` in `samconfig.toml`); "
            + "`aws cloudformation deploy` supports the same flag.",
            "If this run was expected to change the stack, confirm the build step ran and "
            + "produced updated artifacts before the deploy step.",
            "Confirm the deploy targeted the intended stack name, region, and configuration environment.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html",
    ),
    Rule(
        id="sam.deploy.artifact-upload-failed",
        title="SAM could not upload a build artifact referenced by the template",
        confidence="high",
        patterns=(
            r"Unable to upload artifact .{0,120}referenced by (?:CodeUri|ContentUri|DefinitionUri)",
            r"Parameter (?:CodeUri|ContentUri|DefinitionUri) of resource .{0,120}refers to a file or folder that does not exist",
        ),
        explanation=(
            "A `CodeUri`, `ContentUri`, or `DefinitionUri` path in the template does "
            "not exist where the deploy ran. Usually `sam build` was never run, the "
            "deploy ran from a different directory than the build, or the source "
            "template was deployed instead of `.aws-sam/build/template.yaml`."
        ),
        verification=(
            "Run `sam build` first and deploy the built template it produces.",
            "Confirm the CI job checks out the repository and runs build and deploy in the same working directory.",
            "Verify the referenced path exists in the environment that runs the deploy, not only on the machine that authored the template.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html",
    ),
    Rule(
        id="sam.deploy.configuration-resolution-failed",
        title="AWS SAM deployment configuration or parameter resolution failed",
        confidence="medium",
        patterns=(
            r"Unable to locate credentials",
            r"Parameter.*must have values",
            r"Error: Failed to create changeset",
            r"sam deploy.{0,80}(?:failed|error|unable)",
        ),
        explanation=(
            "The deployment failed before or while CloudFormation created a change set. "
            "Confirm the selected SAM configuration environment, AWS identity, required "
            "parameters, and CloudFormation capabilities."
        ),
        verification=(
            "Run `sam validate --lint` locally and confirm the selected `samconfig.toml` environment.",
            "Verify that required parameter overrides and secrets are available to the deployment job.",
            "Review the complete change-set error before changing the template.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-deploy.html",
        # A capability failure can include a preceding generic change-set error
        # on another line. Prefer the narrower finding for the whole log.
        suppressed_by=(
            r"InsufficientCapabilities",
            r"Requires capabilities",
            r"Cannot use both --resolve-s3 and --s3-bucket",
            r"Esbuild Failed:\s*(?:Cannot|can not) find esbuild",
            # Needs the failure continuation for the same reason as the rule
            # itself: as a bare token this suppressed the whole rule whenever a
            # Python build had merely *run*, so a successful build followed by a
            # real change-set failure reported nothing about the change set.
            r"PythonPipBuilder:ResolveDependencies\s+-",
            r"property\s+\S+:\s+not defined for resource of type AWS::Serverless::",
            r"Error Code:\s*InvalidBucketName",
            r"The specified bucket is not valid",
            r"BucketAlreadyExists",
            r"BucketAlreadyOwnedByYou",
            r"ExpiredToken(?:Exception)?",
            r"security token included in the request is expired",
            r"Signature expired:.*is now earlier than",
            r"An error occurred \(Throttling\)",
            r"\bRate exceeded\b",
            r"No changes to deploy",
            r"The submitted information didn't contain changes",
            r"No updates are to be performed",
            r"is in (?:CREATE|UPDATE|DELETE)_IN_PROGRESS state and (?:can not|cannot) be updated",
            # The ROLLBACK_COMPLETE variant of the sentence above. CloudFormation
            # returns both inside the CreateChangeSet ValidationError, on the same
            # line as the generic wrapper this rule matches, so they cannot be
            # describing separate failures - and the recreate-required rule says
            # what to actually do, where this rule would only suggest checking
            # `samconfig.toml` and running `sam validate`.
            r"is in ROLLBACK_COMPLETE state and (?:can not|cannot) be updated",
            r"OperationInProgressException",
            r"Unable to upload artifact",
            r"refers to a file or folder that does not exist",
            r"Value at 'template(?:Body|URL)' failed to satisfy constraint: Member must have length less than or equal to",
            r"Template format error: Number of \S+ .{0,40}is greater than maximum allowed",
            r"Template (?:body )?may not exceed [\d,]+ bytes",
            # `S3 error: Access Denied` is reported by the same CreateChangeSet
            # call this rule reports generically, so the two cannot describe
            # different failures. The upload-direction patterns are deliberately
            # left out: an upload denial can precede an unrelated change-set
            # problem later in the same log.
            r"S3 error: Access ?Denied",
            # An unresolvable SSM reference is reported by the same
            # CreateChangeSet call this rule reports generically, on its own
            # line, so the two describe one failure. Whole-log suppression is
            # right here for the same reason it is right above.
            *_SSM_RESOLUTION_FAILURE_PATTERNS,
        ),
        # The intrinsic-function reason can share a line with the generic
        # change-set wrapper. Exclude only that line: a different change-set
        # failure elsewhere in the same log must keep reporting.
        excluded_line_patterns=(
            r"every Fn::GetAtt object requires two non-empty parameters",
        ),
    ),
    Rule(
        id="ssm.parameter.resolution-failed",
        title="An SSM parameter referenced by the template could not be resolved",
        confidence="high",
        patterns=_SSM_RESOLUTION_FAILURE_PATTERNS,
        explanation=(
            "A `{{resolve:ssm:...}}` or `{{resolve:ssm-secure:...}}` dynamic "
            "reference, or an SSM parameter type, could not be resolved. These "
            "resolve at change-set time, in the target account and Region, "
            "using the deployment's own credentials - so a parameter that "
            "exists locally, or in the account you develop in, proves nothing "
            "about the account being deployed to. The usual causes are a path "
            "that encodes an environment name that does not match the target "
            "(`/my-app/prod/...` deployed to staging), a new environment whose "
            "parameters were never seeded, a deployment pointed at a different "
            "Region than the parameter, or - for `ssm-secure` - a principal "
            "that can read the parameter but cannot decrypt it."
        ),
        verification=(
            "Look up the exact path from the error using the same credentials and Region the deployment used: `aws ssm get-parameter --name <name> --region <region>`.",
            "Compare the path against the target environment's naming: an environment segment left at another stage's value is the most common cause.",
            "If the environment is new, seed the parameter in the target account and Region before re-deploying - the template cannot create what it resolves.",
            "For `ssm-secure`, add `--with-decryption` to that lookup, and confirm the deploy principal has `ssm:GetParameters` plus `kms:Decrypt` on the key protecting the parameter.",
            "Confirm the deployment's Region matches where the parameter lives; a correct path in the wrong Region reports as missing.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/dynamic-references.html",
    ),
    Rule(
        id="sam.deploy.interactive-confirmation-required",
        title="SAM deployment prompted for interactive changeset confirmation",
        confidence="medium",
        # `Aborted!` alone is deliberately not matched. Many tools print it -
        # docker, pip, terraform, any script interrupted with Ctrl-C - and on its
        # own it is no evidence that an *interactive changeset prompt* was the
        # cause, which is what this rule tells the reader to fix with
        # `--no-confirm-changeset`. Primary patterns are matched per line, so the
        # word cannot be qualified by context here; the prompt itself is the
        # signal, and SAM prints it immediately above its own `Aborted!`.
        patterns=(r"Deploy this changeset\?\s*\[y/N\]:",),
        explanation=(
            "SAM stopped at an interactive confirm step and could not continue in a "
            "non-interactive pipeline."
        ),
        verification=(
            "Set `--no-confirm-changeset` (or `confirm_changeset: false`) for automated pipelines.",
            "Move manual approval to a GitHub environment or protected workflow gate instead of interactive prompt output.",
            "Re-run the deployment after removing the interactive confirmation path.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-git.html",
    ),
    Rule(
        id="apigateway.cors.preflight-conflict",
        title="API Gateway CORS preflight configuration conflicts with an existing OPTIONS method",
        confidence="medium",
        patterns=(
            r"duplicate.*OPTIONS",
            r"OPTIONS.*(?:already exists|duplicate)",
            # `error` and `failed` used to be in this alternation, and across an
            # 80-character window from the word CORS they matched ordinary
            # configuration output - "Configuring CORS ... - no errors" reported a
            # preflight conflict. They add almost nothing: a real conflict says so
            # in the words kept below, or is caught by the OPTIONS patterns.
            r"(?:CORS|preflight).{0,80}(?:conflict|duplicate|overlap)",
        ),
        explanation=(
            "SAM can generate CORS preflight handling. Defining an overlapping OPTIONS "
            "method or mixing manual and generated CORS configuration can create a conflict."
        ),
        verification=(
            "Check whether the API definition already declares an `OPTIONS` method for the affected path.",
            "Use either SAM-managed CORS or a fully manual preflight implementation for that route, not both.",
            "Verify the generated API definition before redeploying.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-api.html#sam-api-cors",
    ),
)

_MAX_EVIDENCE_LENGTH = 360


def supported_rules() -> tuple[Rule, ...]:
    """Return the diagnostic rule catalog without exposing mutable internals."""

    return _RULES


_ANSI_ESCAPE = re.compile(
    r"""
      \x1b\[ [0-9;:?]* [ -/]* [@-~]        # CSI: colour, bold, cursor movement
    | \x1b\] [^\x07\x1b]* (?:\x07|\x1b\\)  # OSC: window titles, hyperlinks
    | \x1b [@-Z\\-_]                       # two-character escapes
    """,
    re.VERBOSE,
)


def _strip_ansi(text: str) -> str:
    r"""Remove terminal escape sequences before anything tries to match text.

    The SAM CLI colours its own output and so do most build tools, so a log
    saved from a terminal or downloaded raw from a CI provider can read
    `\x1b[31mFAILED\x1b[0m` where a rule pattern expects `FAILED`. The colour
    sits inside the word, which is the worst place for it: the line still looks
    entirely normal to a human reading it, the pattern quietly does not match,
    and the finding is simply absent. Measured on the bundled CloudFormation
    sample, colouring the words a CI provider actually colours dropped one of
    its two findings.

    Timestamp prefixes, CRLF, lone carriage returns from progress bars, leading
    whitespace and non-breaking spaces were all checked at the same time and
    need no handling - patterns are searched within a line, so a prefix is
    harmless. Only the escapes broke matching.
    """

    return _ANSI_ESCAPE.sub("", text)


def _compact_evidence(line: str) -> str:
    """Normalize a log line and keep reports readable for noisy CI output."""

    line = " ".join(line.split())
    if len(line) <= _MAX_EVIDENCE_LENGTH:
        return line
    half = (_MAX_EVIDENCE_LENGTH - 9) // 2
    return f"{line[:half]} ... {line[-half:]}"


_CANDIDATE_PATTERN: re.Pattern[str] | None = None


def _candidate_pattern() -> re.Pattern[str]:
    """One alternation over every rule pattern, used to prefilter log lines.

    Noisy CI logs are overwhelmingly lines no rule can match; testing each line
    once against the combined pattern lets diagnose() run the per-rule logic on
    the handful of candidate lines instead of the whole log.
    """

    global _CANDIDATE_PATTERN
    if _CANDIDATE_PATTERN is None:
        _CANDIDATE_PATTERN = re.compile(
            "|".join(f"(?:{pattern})" for rule in _RULES for pattern in rule.patterns),
            re.IGNORECASE,
        )
    return _CANDIDATE_PATTERN


def _matching_evidence_with_lines(
    candidate_lines: list[tuple[int, str]],
    patterns: tuple[str, ...],
    excluded_patterns: tuple[str, ...] = (),
) -> tuple[tuple[int, str], ...]:
    matching_lines: list[tuple[int, str]] = []
    seen = set[str]()
    for line_number, line in candidate_lines:
        if any(
            re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns
        ) and not any(
            re.search(pattern, line, flags=re.IGNORECASE)
            for pattern in excluded_patterns
        ):
            compacted = _compact_evidence(redact(line.strip()))
            if compacted not in seen:
                matching_lines.append((line_number, compacted))
                seen.add(compacted)
        if len(matching_lines) >= 3:
            break
    return tuple(matching_lines)


# Generic error wording, used only when diagnose() finds no rule match. This
# is deliberately broader and noisier than any single rule pattern - it is a
# starting point for a human excerpt, not a diagnosis.
_LIKELY_ERROR_LINE = re.compile(
    r"(?i)\b(error|exception|fail(?:ed|ure)?|denied|not authorized|invalid|unable to|"
    r"cannot|traceback|panic|rejected|refused|throttl(?:ed|ing)|expired|blocked)\b"
)

_DEFAULT_EXCERPT_CONTEXT = 2
_DEFAULT_EXCERPT_MAX_LINES = 15


def likely_error_excerpt(
    text: str,
    context: int = _DEFAULT_EXCERPT_CONTEXT,
    max_lines: int = _DEFAULT_EXCERPT_MAX_LINES,
) -> tuple[tuple[int, str], ...]:
    """Return a short, redacted window around the first likely error line.

    This is a heuristic for unmatched logs, not a rule: it is meant to save a
    contributor from copying an entire log into a rule request when nothing
    in `diagnose()` matched. Returns an empty tuple when no line looks like an
    error at all.
    """

    lines = _strip_ansi(text).splitlines()
    for index, line in enumerate(lines):
        if not _LIKELY_ERROR_LINE.search(line):
            continue
        start = max(0, index - context)
        end = min(len(lines), index + context + 1, start + max_lines)
        return tuple(
            (line_number, redact(lines[line_number - 1].strip()))
            for line_number in range(start + 1, end + 1)
            if lines[line_number - 1].strip()
        )
    return ()


def diagnose(text: str) -> list[Finding]:
    """Return all deterministic findings supported by the supplied text.

    Findings keep the chronological order of their first matching log line: a
    deployment log is chronological evidence, and the earlier failure is the
    more useful one to inspect before downstream rollback messages.
    """

    # Before anything matches: escape sequences inside a word defeat every
    # pattern below, including the whole-log `suppressed_by` search.
    text = _strip_ansi(text)

    combined = _candidate_pattern()
    candidate_lines = [
        (line_number, line)
        for line_number, line in enumerate(text.splitlines(), start=1)
        if combined.search(line)
    ]
    matched_findings: list[tuple[int, int, Finding]] = []
    for rule_index, rule in enumerate(_RULES):
        line_matches = _matching_evidence_with_lines(
            candidate_lines, rule.patterns, rule.excluded_line_patterns
        )
        if not line_matches:
            continue
        if any(
            re.search(pattern, text, flags=re.IGNORECASE)
            for pattern in rule.suppressed_by
        ):
            continue
        evidence = tuple(line for _, line in line_matches)
        explanation = rule.explanation
        if rule.parse_denial_context:
            note = _denial_context_note(evidence)
            if note:
                explanation = f"{explanation}\n\n{note}"
        if rule.parse_stabilization_context:
            note = _stabilization_context_note(evidence)
            if note:
                # The nested reason leads: it names the actual failure, and the
                # generic stabilization explanation is only the wrapper.
                explanation = f"{note}\n\n{explanation}"
        matched_findings.append(
            (
                line_matches[0][0],
                rule_index,
                Finding(
                    rule_id=rule.id,
                    title=rule.title,
                    confidence=rule.confidence,
                    explanation=explanation,
                    verification=rule.verification,
                    documentation_url=rule.documentation_url,
                    evidence=evidence,
                    line_number=line_matches[0][0],
                ),
            )
        )
    return [finding for _, _, finding in sorted(matched_findings)]


def markdown_report(
    findings: list[Finding], source_name: str, *, input_is_empty: bool = False
) -> str:
    """Render a shareable report without including the full raw input."""

    lines = [
        "# SAM Doctor diagnostic report",
        "",
        f"**Source:** <code>{escape(redact(source_name))}</code>",
        "",
        "This report is generated from matched log patterns. Review the evidence and "
        + "commands before applying any change.",
        "",
    ]
    if input_is_empty:
        lines.extend(
            [
                "## Nothing to diagnose",
                "",
                "The input is empty. This usually means the step that writes the log "
                + "failed before producing output, or the log was captured from the "
                + "wrong command.",
                "",
                "### What to do next",
                "",
                "Check the step that produces the log, then re-run the diagnosis.",
            ]
        )
        return "\n".join(lines) + "\n"

    if not findings:
        lines.extend(
            [
                "## No supported pattern found",
                "",
                "The input did not match the current rule set. Preserve the first error "
                + "and relevant CloudFormation event details, then consult the linked AWS "
                + "documentation or an authorized support engineer.",
                "",
                "### What to do next",
                "",
                "Run `sam-doctor rules` to review current coverage. If this was a real "
                + f"failure, run `{_request_packet_command(source_name)}` to write a short, "
                + f"sanitized excerpt, review it, then share it in a [diagnostic rule request]({RULE_REQUEST_URL}).",
            ]
        )
        return "\n".join(lines) + "\n"

    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"## {index}. {finding.title}",
                "",
                f"**Confidence:** {finding.confidence}",
                "",
                finding.explanation,
                "",
                "### Evidence",
                f"- Matched on line: {finding.line_number}",
                *[
                    f"- <code>{escape(evidence)}</code>"
                    for evidence in finding.evidence
                ],
                "",
                "### Safe verification steps",
                *[f"- {step}" for step in finding.verification],
                "",
                f"### Documentation\n- {finding.documentation_url}",
                "",
            ]
        )
    return "\n".join(lines)


def terminal_report(
    findings: list[Finding], source_name: str, *, input_is_empty: bool = False
) -> str:
    """Render a concise report for direct terminal use."""

    if input_is_empty:
        return EMPTY_INPUT_NOTE.format(source=redact(source_name))

    if not findings:
        return (
            f"No supported diagnostic pattern found in {redact(source_name)}.\n"
            "Keep the first failure event and inspect the relevant AWS documentation.\n"
            "Run `sam-doctor rules` for current coverage; if this was a real failure, "
            f"run `{_request_packet_command(source_name)}` to write a short, sanitized "
            f"excerpt, review it, then share it at {RULE_REQUEST_URL}."
        )

    blocks = [
        f"SAM Doctor found {len(findings)} possible issue(s) in {redact(source_name)}."
    ]
    for index, finding in enumerate(findings, start=1):
        blocks.extend(
            [
                "",
                f"{index}. {finding.title} ({finding.confidence} confidence)",
                f"   Matched on line: {finding.line_number}",
                f"   {finding.explanation}",
                "   Evidence:",
                *[f"   - {line}" for line in finding.evidence],
                "   Verify:",
                *[f"   - {step}" for step in finding.verification],
                f"   Docs: {finding.documentation_url}",
            ]
        )
    return "\n".join(blocks)


def json_report(findings: list[Finding], source_name: str) -> str:
    """Render a stable, redacted report for scripts and CI annotations."""

    payload = {
        "sam_doctor_version": __version__,
        "source": redact(source_name),
        "finding_count": len(findings),
        "findings": [
            {
                "line_number": finding.line_number,
                "rule_id": finding.rule_id,
                "title": finding.title,
                "confidence": finding.confidence,
                "explanation": finding.explanation,
                "evidence": list(finding.evidence),
                "verification": list(finding.verification),
                "documentation_url": finding.documentation_url,
            }
            for finding in findings
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


# SARIF has three result levels; "low" exists in the confidence vocabulary
# even though no shipped rule uses it yet.
_SARIF_LEVELS = {"high": "error", "medium": "warning", "low": "note"}


def _sarif_artifact_uri(source_name: str) -> str:
    """A redacted source name as a forward-slash relative URI.

    SARIF's `artifactLocation.uri` is a URI reference, not a file path, and the
    difference is not cosmetic. A `#` in a filename starts a fragment, so
    `logs/#build.log` reaches a consumer as the path `logs/` with a fragment
    attached and the finding is attributed to the directory rather than the file.
    A space is not allowed in a URI at all, and a strict consumer may reject the
    whole document over one - which loses every finding in it, not just that one.

    Percent-encoding the path fixes both. Only `/` stays literal, so separators
    survive and everything else is encoded - including the colon after a Windows
    drive letter. That last one looks like over-encoding and is not: RFC 3986
    forbids a colon in the first segment of a relative-path reference precisely
    because it is ambiguous, and `C:/builds/deploy.log` really does parse with
    `C` as the scheme, which silently drops the drive letter from the path a
    consumer sees. `C%3A/builds/deploy.log` keeps it.
    """

    forward_slashed = redact(source_name).replace("\\", "/")
    return urllib.parse.quote(forward_slashed, safe="/")


def sarif_report(results: list[tuple[str, list[Finding]]]) -> str:
    """Render one SARIF 2.1.0 run for code-scanning uploads.

    Takes (source, findings) pairs so a single diagnose and a batch both
    produce one document: one run, one deduplicated rule table, results
    pointing at their own log files. Rule metadata is emitted only for rules
    that fired - the full catalog belongs to `sam-doctor rules`.
    """

    rule_indexes: dict[str, int] = {}
    rules: list[dict[str, object]] = []
    sarif_results: list[dict[str, object]] = []
    for source_name, findings in results:
        uri = _sarif_artifact_uri(source_name)
        for finding in findings:
            level = _SARIF_LEVELS.get(finding.confidence, "warning")
            if finding.rule_id not in rule_indexes:
                rule_indexes[finding.rule_id] = len(rules)
                rules.append(
                    {
                        "id": finding.rule_id,
                        "shortDescription": {"text": finding.title},
                        "helpUri": finding.documentation_url,
                        "defaultConfiguration": {"level": level},
                    }
                )
            sarif_results.append(
                {
                    "ruleId": finding.rule_id,
                    "ruleIndex": rule_indexes[finding.rule_id],
                    "level": level,
                    "message": {"text": f"{finding.title}. {finding.explanation}"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": uri},
                                "region": {"startLine": finding.line_number},
                            }
                        }
                    ],
                }
            )
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "sam-doctor",
                        "informationUri": "https://github.com/jakegold1647/sam-doctor",
                        "version": __version__,
                        "rules": rules,
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def rules_report(output_format: str) -> str:
    """Render the supported-rule catalog for prospective users and CI checks."""

    rules = supported_rules()
    if output_format == "json":
        payload = {
            "sam_doctor_version": __version__,
            "rule_count": len(rules),
            "rules": [
                {
                    "id": rule.id,
                    "title": rule.title,
                    "confidence": rule.confidence,
                    "documentation_url": rule.documentation_url,
                }
                for rule in rules
            ],
        }
        return json.dumps(payload, indent=2) + "\n"

    lines = [f"SAM Doctor {__version__} supports {len(rules)} diagnostic rule(s):", ""]
    for index, rule in enumerate(rules, start=1):
        lines.extend(
            [
                f"{index}. {rule.title} ({rule.confidence} confidence)",
                f"   Docs: {rule.documentation_url}",
            ]
        )
    return "\n".join(lines) + "\n"
