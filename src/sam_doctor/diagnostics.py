"""Deterministic, evidence-first diagnostic rules for deployment logs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape

from . import __version__
from .redaction import redact

_RULE_REQUEST_URL = (
    "https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml"
)


@dataclass(frozen=True)
class Finding:
    """A matched failure pattern and safe next actions."""

    title: str
    confidence: str
    explanation: str
    verification: tuple[str, ...]
    documentation_url: str
    evidence: tuple[str, ...]
    line_number: int


@dataclass(frozen=True)
class Rule:
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


_RULES = (
    Rule(
        title="The GitHub Actions job cannot request an OIDC token",
        confidence="high",
        patterns=(
            r"Unable to get ID Token.*id-token:\s*write",
            r"id-token:\s*write.*(?:permission|required|missing)",
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
        title="GitHub Actions cannot assume the configured AWS role through OIDC",
        confidence="high",
        patterns=(
            r"Not authorized to perform: sts:AssumeRoleWithWebIdentity",
            r"(?:failed|error|denied|unable).{0,80}AssumeRoleWithWebIdentity",
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
        ),
    ),
    Rule(
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
        title="Lambda code signing is incompatible with a container-image function",
        confidence="high",
        patterns=(r"Code signing is not supported for functions created with container images",),
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
        title="SAM build requires Docker for containerized builds",
        confidence="high",
        patterns=(
            r"Cannot connect to the Docker daemon",
            r"Error response from daemon",
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
        title="API Gateway deployment started before the API had any methods",
        confidence="high",
        patterns=(
            r"The REST API does(?:n't| not) contain any methods",
        ),
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
        # These service errors have more actionable, resource-specific findings.
        suppressed_by=(
            r"Has prohibited field Resource",
            r"Code signing is not supported for functions created with container images",
            r"Lambda does not have permission to access the ECR image",
            r"Error Code:\s*InvalidBucketName",
            r"The specified bucket is not valid",
            r"(?s:access has been denied by S3.*permission.*GetObject)",
            r"The REST API does(?:n't| not) contain any methods",
        ),
    ),
    Rule(
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
        # An immutable initial-create rollback state and a role-deletion
        # blocker each have a more precise dedicated finding.
        suppressed_by=(
            r"ROLLBACK_COMPLETE.*(?:can not|cannot) be updated",
            r"following resource\(s\) failed to delete",
            r"failed to delete.*AWS::IAM::Role",
            r"Unable to delete.*AWS::IAM::Role",
        ),
    ),
    Rule(
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
        # A role deletion blocker keeps its dedicated, more actionable finding.
        suppressed_by=(
            r"The following resource\(s\) failed to delete:.*Role\b",
            r"failed to delete.*IAM Role",
            r"Unable to delete.*AWS::IAM::Role",
        ),
    ),
    Rule(
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
        title="SAM deployment configured both a managed and explicit S3 bucket",
        confidence="high",
        patterns=(
            r"Cannot use both --resolve-s3 and --s3-bucket parameters",
        ),
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
        title="SAM Python dependency resolution failed",
        confidence="high",
        patterns=(
            r"PythonPipBuilder:ResolveDependencies",
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
        title="SAM Python dependency build validation failed",
        confidence="high",
        patterns=(
            r"Binary validation failed",
        ),
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
            r"PythonPipBuilder:ResolveDependencies",
            r"property\s+\S+:\s+not defined for resource of type AWS::Serverless::",
            r"Error Code:\s*InvalidBucketName",
            r"The specified bucket is not valid",
            r"ExpiredToken(?:Exception)?",
            r"security token included in the request is expired",
            r"Signature expired:.*is now earlier than",
            r"An error occurred \(Throttling\)",
            r"\bRate exceeded\b",
            r"No changes to deploy",
            r"The submitted information didn't contain changes",
            r"No updates are to be performed",
        ),
    ),
    Rule(
        title="SAM deployment prompted for interactive changeset confirmation",
        confidence="medium",
        patterns=(r"Deploy this changeset\?\s*\[y/N\]:", r"Aborted!"),
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
        title="API Gateway CORS preflight configuration conflicts with an existing OPTIONS method",
        confidence="medium",
        patterns=(
            r"duplicate.*OPTIONS",
            r"OPTIONS.*(?:already exists|duplicate)",
            r"(?:CORS|preflight).{0,80}(?:conflict|error|failed|duplicate|overlap)",
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
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns) and not any(
            re.search(pattern, line, flags=re.IGNORECASE) for pattern in excluded_patterns
        ):
            compacted = _compact_evidence(redact(line.strip()))
            if compacted not in seen:
                matching_lines.append((line_number, compacted))
                seen.add(compacted)
        if len(matching_lines) >= 3:
            break
    return tuple(matching_lines)


def diagnose(text: str) -> list[Finding]:
    """Return all deterministic findings supported by the supplied text.

    Findings keep the chronological order of their first matching log line: a
    deployment log is chronological evidence, and the earlier failure is the
    more useful one to inspect before downstream rollback messages.
    """

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
            re.search(pattern, text, flags=re.IGNORECASE) for pattern in rule.suppressed_by
        ):
            continue
        evidence = tuple(line for _, line in line_matches)
        matched_findings.append(
            (
                line_matches[0][0],
                rule_index,
                Finding(
                    title=rule.title,
                    confidence=rule.confidence,
                    explanation=rule.explanation,
                    verification=rule.verification,
                    documentation_url=rule.documentation_url,
                    evidence=evidence,
                    line_number=line_matches[0][0],
                ),
            )
        )
    return [finding for _, _, finding in sorted(matched_findings)]


def markdown_report(findings: list[Finding], source_name: str) -> str:
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
                + f"failure, share a short, sanitized excerpt in a [diagnostic rule request]({_RULE_REQUEST_URL}).",
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
                *[f"- <code>{escape(evidence)}</code>" for evidence in finding.evidence],
                "",
                "### Safe verification steps",
                *[f"- {step}" for step in finding.verification],
                "",
                f"### Documentation\n- {finding.documentation_url}",
                "",
            ]
        )
    return "\n".join(lines)


def terminal_report(findings: list[Finding], source_name: str) -> str:
    """Render a concise report for direct terminal use."""

    if not findings:
        return (
            f"No supported diagnostic pattern found in {redact(source_name)}.\n"
            "Keep the first failure event and inspect the relevant AWS documentation.\n"
            "Run `sam-doctor rules` for current coverage; if this was a real failure, "
            f"share a short, sanitized excerpt at {_RULE_REQUEST_URL}."
        )

    blocks = [f"SAM Doctor found {len(findings)} possible issue(s) in {redact(source_name)}."]
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


def rules_report(output_format: str) -> str:
    """Render the supported-rule catalog for prospective users and CI checks."""

    rules = supported_rules()
    if output_format == "json":
        payload = {
            "sam_doctor_version": __version__,
            "rule_count": len(rules),
            "rules": [
                {
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
