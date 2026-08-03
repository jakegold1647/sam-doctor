# SAM Doctor

[![Verify free core](https://github.com/jakegold1647/sam-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/jakegold1647/sam-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

SAM Doctor is a local, evidence-first command-line tool for turning AWS SAM,
CloudFormation, IAM, and GitHub Actions deployment failures into a concise
diagnostic report.

**[See the project page](https://jakegold1647.github.io/sam-doctor/)** |
**[Use on GitHub Marketplace](https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics)** |
**[Report a bad diagnosis](https://github.com/jakegold1647/sam-doctor/issues/new/choose)** |
**[Request a rule](https://github.com/jakegold1647/sam-doctor/issues/new/choose)** |
**[Join the feedback discussion](https://github.com/jakegold1647/sam-doctor/discussions/1)**

It does **not** access AWS, upload logs, change resources, or promise an
authoritative root cause. It detects known patterns in the text you provide,
redacts common identifiers, and gives safe verification steps and the relevant
official documentation.

## Current free core

- GitHub Actions OIDC errors: missing `id-token: write`, audience mismatch,
  trust-policy/subject mismatch, and `AssumeRoleWithWebIdentity` failures
- IAM `AccessDenied` failures
- CloudFormation failed-resource events and rollback states
- CloudFormation capability acknowledgement errors
- API Gateway deployments created before methods exist
- SAM deployment/configuration errors, including conflicting artifact-bucket settings
  and missing `esbuild` dependencies
- Template shape, IAM trust-policy, Lambda packaging, and S3 artifact failures
- API Gateway CORS preflight conflicts
- Terminal, Markdown, and JSON reports
- Composite GitHub Action with opt-in redacted job summaries and CI gating
- Local redaction for account IDs, ARNs, email addresses, and common CI credentials

## Try it in 60 seconds

```bash
python -m pip install https://github.com/jakegold1647/sam-doctor/releases/download/v0.7.4/sam_doctor-0.7.4-py3-none-any.whl
sam-doctor demo
sam-doctor demo --scenario cloudformation
sam-doctor demo --scenario capabilities
sam-doctor rules
sam-doctor diagnose examples/oidc-assume-role-failure.txt --format markdown
```

This installs the published release directly and does not require Git. The
bundled demo needs no AWS credentials and makes no network calls. To install
from the tagged source instead, run:

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v0.7.4"
```

Run `sam-doctor rules --format json` to inspect the exact set of supported
diagnostic categories before sharing a log.

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

## GitHub Actions

Use the included action when a workflow already saves a deployment log:

```yaml
- id: sam-doctor
  uses: jakegold1647/sam-doctor@v0.7.4
  with:
    log-file: deployment.log
    summary: "true"
```

The action exposes `finding-count` and `has-findings` outputs. Set
`fail-on-findings: "true"` only when you want a supported diagnostic to fail
the job. The Markdown job summary is opt-in and contains only matched, redacted
evidence; review it before sharing a workflow run outside your team.

## What a report includes

SAM Doctor deliberately reports only what its rules can support:

1. A likely failure category and confidence level.
2. Up to three matched log lines, redacted before output.
3. Safe checks to validate the diagnosis before changing a policy or stack.
4. A link to the relevant official documentation.

It is most useful when you start with the first failure in a deployment log,
not a later rollback message. When multiple supported patterns appear, SAM
Doctor presents findings in the order of their first matching log line.

## Example output

```text
Likely cause: GitHub Actions cannot assume the configured AWS role through OIDC.
Confidence: high
Evidence: Not authorized to perform sts:AssumeRoleWithWebIdentity
Safe next step: Confirm the workflow grants `id-token: write` and that the
role trust policy's `sub` condition matches the repository, branch, or GitHub
Environment that ran the job.
```

## Feedback and roadmap

The free core will stay useful for individual deployment failures. Please open
an issue when a report is wrong, unclear, or missing a failure pattern. For a
new rule, include only a sanitized error excerpt and the safe next check you
expected to see. See [CONTRIBUTING.md](CONTRIBUTING.md) for the exact format.

## Distribution and ethics

SAM Doctor is grown through practical conversations and feedback, not star
incentives. If you run outreach, ask for one realistic use case first, then
share the report and a short ask for permission to improve coverage.

Track progress with:

```bash
python scripts/check-distribution.py --output-format json --output artifacts/distribution.json --append-csv artifacts/distribution.csv --print-trend --summary artifacts/distribution-summary.md
```

## Guides

- [Diagnose a GitHub Actions to AWS OIDC deployment failure](docs/oidc-deployment-debugging.md)
- [Find the first useful error in a CloudFormation rollback](docs/cloudformation-first-failure.md)

## Supported signals

Run `sam-doctor rules` for the current machine-readable catalog. Each rule is
triggered by an explicit error signal, not by template inspection or AWS account
access; the report is still a prompt to verify the cause, not an automatic fix.

## Scope and safety

Run this only on logs you are authorized to inspect. Review every suggested
command and policy change before applying it. SAM Doctor is diagnostic help,
not security, legal, or production-operations advice.

Reports redact AWS account IDs, ARNs, email addresses, common AWS access key IDs,
bearer tokens, JWT-style tokens, and common GitHub token formats before matched
evidence or a displayed source name is shared. This is a helpful guardrail, not a secret scanner:
review a report before sharing it.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

See [CHANGELOG.md](CHANGELOG.md) for release history, [SECURITY.md](SECURITY.md)
for vulnerability reporting, [SUPPORT.md](SUPPORT.md) for help boundaries, and
[docs/pypi-publishing.md](docs/pypi-publishing.md) for the stable-release
publishing setup.
