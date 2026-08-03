"""Deterministic, evidence-first diagnostic rules for deployment logs."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

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
            r"AssumeRoleWithWebIdentity",
            r"Not authorized to perform: sts:AssumeRoleWithWebIdentity",
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
            "Compare the trust policy's `sub` condition with the branch or GitHub Environment that ran the job.",
        ),
        documentation_url="https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws",
    ),
    Rule(
        title="GitHub OIDC token audience does not match AWS STS",
        confidence="high",
        patterns=(r"Incorrect token audience", r"audience.*sts\.amazonaws\.com", r"InvalidIdentityToken"),
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
        patterns=(r"sam deploy", r"Unable to locate credentials", r"Parameter.*must have values", r"Error: Failed to create changeset"),
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
        patterns=(r"duplicate.*OPTIONS", r"CORS", r"preflight"),
        explanation=(
            "SAM can generate CORS preflight handling. Defining an overlapping OPTIONS "
            "method or mixing manual and generated CORS configuration can create a conflict."
        ),
        verification=(
            "Check whether the API definition already declares an `OPTIONS` method for the affected path.",
            "Use either SAM-managed CORS or a fully manual preflight implementation for that route—not both.",
            "Verify the generated API definition before redeploying.",
        ),
        documentation_url="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-api.html#sam-api-cors",
    ),
)


def _matching_evidence(
    text: str, patterns: tuple[str, ...], excluded_patterns: tuple[str, ...] = ()
) -> tuple[str, ...]:
    lines = text.splitlines()
    matches = [
        line.strip()
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
