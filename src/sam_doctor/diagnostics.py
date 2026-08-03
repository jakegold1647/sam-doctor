"""Deterministic, evidence-first diagnostic rules for deployment logs."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
import re

from . import __version__
from .redaction import redact


@dataclass(frozen=True)
class Finding:
    """A matched failure pattern and safe next actions."""

    title: str
    confidence: str
    explanation: str
    verification: tuple[str, ...]
    documentation_url: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    title: str
    confidence: str
    patterns: tuple[str, ...]
    explanation: str
    verification: tuple[str, ...]
    documentation_url: str


_RULES = (
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
    ),
    Rule(
        title="CloudFormation stack entered rollback after an earlier resource failure",
        confidence="medium",
        patterns=(r"ROLLBACK_IN_PROGRESS", r"ROLLBACK_COMPLETE", r"UPDATE_ROLLBACK"),
        explanation=(
            "Rollback is a downstream stack state. The most useful evidence is usually "
            "the first failed resource event that appears before the rollback entries."
        ),
        verification=(
            "Inspect stack events in chronological order and locate the first `CREATE_FAILED` or `UPDATE_FAILED` resource.",
            "Preserve the exact resource status reason before retrying the deployment.",
            "Use a change set or isolated stack when testing a fix, where practical.",
        ),
        documentation_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/determine-root-cause-for-stack-failures.html",
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


def _matching_evidence(
    text: str, patterns: tuple[str, ...], excluded_patterns: tuple[str, ...] = ()
) -> tuple[str, ...]:
    lines = text.splitlines()
    matches = [
        _compact_evidence(line.strip())
        for line in lines
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns)
        and not any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in excluded_patterns)
    ]
    return tuple(dict.fromkeys(redact(line) for line in matches[:3]))


def diagnose(text: str) -> list[Finding]:
    """Return all deterministic findings supported by the supplied text."""

    findings: list[Finding] = []
    for rule in _RULES:
        excluded_patterns = ()
        if rule.title == "AWS denied an API action required by the deployment":
            # STS OIDC failures are authorization failures, but the OIDC rule
            # provides a more precise and actionable explanation than the
            # generic IAM finding.
            excluded_patterns = (r"AssumeRoleWithWebIdentity",)
        evidence = _matching_evidence(text, rule.patterns, excluded_patterns)
        if evidence:
            findings.append(
                Finding(
                    title=rule.title,
                    confidence=rule.confidence,
                    explanation=rule.explanation,
                    verification=rule.verification,
                    documentation_url=rule.documentation_url,
                    evidence=evidence,
                )
            )
    return findings


def markdown_report(findings: list[Finding], source_name: str) -> str:
    """Render a shareable report without including the full raw input."""

    lines = [
        "# SAM Doctor diagnostic report",
        "",
        f"**Source:** <code>{escape(source_name)}</code>",
        "",
        "This report is generated from matched log patterns. Review the evidence and "
        "commands before applying any change.",
        "",
    ]
    if not findings:
        lines.extend(
            [
                "## No supported pattern found",
                "",
                "The input did not match the current rule set. Preserve the first error "
                "and relevant CloudFormation event details, then consult the linked AWS "
                "documentation or an authorized support engineer.",
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
            f"No supported diagnostic pattern found in {source_name}.\n"
            "Keep the first failure event and inspect the relevant AWS documentation."
        )

    blocks = [f"SAM Doctor found {len(findings)} possible issue(s) in {source_name}."]
    for index, finding in enumerate(findings, start=1):
        blocks.extend(
            [
                "",
                f"{index}. {finding.title} ({finding.confidence} confidence)",
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
        "source": source_name,
        "finding_count": len(findings),
        "findings": [
            {
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
