# SAM Doctor

SAM Doctor is a local, evidence-first command-line tool for turning AWS SAM,
CloudFormation, IAM, and GitHub Actions deployment failures into a concise
diagnostic report.

It does **not** access AWS, upload logs, change resources, or promise an
authoritative root cause. It detects known patterns in the text you provide,
redacts common identifiers, and gives safe verification steps and the relevant
official documentation.

## Current free core

- GitHub Actions OIDC errors: missing `id-token: write`, audience mismatch,
  trust-policy/subject mismatch, and `AssumeRoleWithWebIdentity` failures
- IAM `AccessDenied` failures
- CloudFormation rollback states
- SAM deployment/configuration errors
- API Gateway CORS preflight conflicts
- Terminal, Markdown, and JSON reports
- Local redaction for account IDs, ARNs, email addresses, and common CI credentials

## Install and run

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git"
sam-doctor demo
sam-doctor diagnose examples/oidc-assume-role-failure.txt --format markdown
```

For local development, clone the repository and use `python -m pip install -e ".[dev]"`.

To save a report:

```bash
sam-doctor diagnose deployment.log --format markdown --output diagnosis.md
```

The input can also be read from standard input, which is useful for CI steps and
shell pipelines:

```bash
kubectl logs deploy/my-api | sam-doctor diagnose -
sam-doctor diagnose deployment.log --format json --output diagnosis.json
```

The terminal format is intended for a quick local check, Markdown is convenient
for a human-readable handoff, and JSON is stable enough for scripts and CI
annotations. All three formats contain matched evidence rather than the full
input log.

## Example output

```text
Likely cause: GitHub Actions cannot assume the configured AWS role through OIDC.
Confidence: high
Evidence: Not authorized to perform sts:AssumeRoleWithWebIdentity
Safe next step: Confirm the workflow grants `id-token: write` and that the
role trust policy's `sub` condition matches the repository, branch, or GitHub
Environment that ran the job.
```

## Product direction

The free core will stay useful for individual deployment failures. A future
paid edition may add batch analysis, additional rule packs, richer support
reports, configurable redaction, and commercial-use terms. The paid edition
will only be built if developers find the free core useful on real sanitized
failures.

## Scope and safety

Run this only on logs you are authorized to inspect. Review every suggested
command and policy change before applying it. SAM Doctor is diagnostic help,
not security, legal, or production-operations advice.

Reports redact AWS account IDs, ARNs, email addresses, common AWS access key IDs,
and common GitHub token formats before matched evidence is displayed. This is a
helpful guardrail, not a secret scanner: review a report before sharing it.
