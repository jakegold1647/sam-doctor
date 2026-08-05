# SAM Doctor researcher overview

## Purpose

SAM Doctor is a deterministic, local-first diagnostic tool for AWS deployment failures.
It is intended for teams that need a short, repeatable pre-analysis step before:

- opening an incident ticket,
- changing IAM or deployment configuration,
- or escalating to a deeper expert review.

Researchers and technical reviewers can use it to evaluate whether failure-to-first-check workflows reduce response time and improve verification quality.

## What SAM Doctor does (and does not do)

### It does

- parse deployment logs from SAM, CloudFormation, IAM-related AWS errors, API Gateway, and
  GitHub Actions OIDC failure lines,
- detect supported failure patterns with short evidence extracts,
- return a ranked finding list with confidence labels,
- provide one or more safe verification commands,
- redact common sensitive identifiers in the report output,
- emit machine-readable output (`json`) for reproducibility.

### It does not do

- access AWS APIs on its own,
- claim authoritative root cause,
- upload logs to a remote service,
- perform automatic remediation.

## Reproducible protocol

1. Keep the sample as short as possible (a few lines around the first failure).
2. Run:

```bash
sam-doctor diagnose deployment.log --format json --output diagnosis.json
```

3. Record the version and command used:

```bash
sam-doctor --version
```

4. Share only sanitized artifacts (`diagnosis.md`, `diagnosis.json`, and your notes) and keep raw logs out of the conversation.

## Standard evidence packet

For reproducible collaboration, use the built-in packet command:

```bash
sam-doctor packet deployment.log --markdown-name diagnosis.md --json-name diagnosis.json
```

The packet command writes:

- `diagnosis.md` (human report),
- `diagnosis.json` (structured result),
- `researcher-notes.md` (brief method note).

To share this workflow with collaborators or reviewers, see the
[team rollout guide](docs/team-rollout.md).

## Why this supports reliable reporting

Each run is deterministic for fixed input. If two people run the same excerpt through the same command and version, they get the same match sequence.
That predictability makes it suitable for methods sections, triage notes, and reviewer-facing appendices.

## What to include when sharing findings

- tool version,
- command line used,
- snippet of the redacted input,
- number of findings and top finding title,
- one next verification action attempted.

Do not include production credentials, account numbers, ARNs, tokens, or full raw logs.
