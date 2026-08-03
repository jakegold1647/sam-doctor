# Contributing to SAM Doctor

The most useful contributions are reproducible false positives, missed failure
patterns, and improvements to safe verification steps.

## Before opening an issue

Never post raw production logs, AWS account IDs, ARNs, access keys, session
tokens, customer data, or private repository names. Redaction helps with common
identifiers, but it is not a substitute for reviewing an excerpt yourself.

For a diagnostic problem, include:

1. The SAM Doctor version from `sam-doctor --version`.
2. The exact command you ran, with private paths or values replaced.
3. A short, sanitized excerpt containing the first relevant error.
4. What you expected the report to say and what it said instead.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

Keep rules deterministic, explain the evidence they match, and add regression
coverage for both the intended failure and a nearby non-failure case. Do not add
commands that change AWS resources or require credentials.
