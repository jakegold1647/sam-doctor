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

If you are helping spread the project, include short onboarding notes and share one
closed reproduction with a link to the community kit:
`docs/community-sharing-kit.md`.

For tooling improvements, use the feature request template and include:

1. the command or workflow family,
2. the behavior gap,
3. expected adoption impact.

## First contribution path

If this is your first contribution, start with this three-step flow:

1. Open a small diagnostic issue with the built-in template.
2. Add one focused regression test in `tests/test_diagnostics.py` (or a fixture for
   `src/sam_doctor/data` if needed).
3. Open a PR using the template and include the exact command that reproduced the issue.

To lower contributor friction, labels to look for:

- `good first issue`
- `documentation`
- `help wanted`

Want a ready-made first PR? The [rule roadmap](docs/rule-roadmap.md) lists
fully specified diagnostic rules waiting for a contributor — each with sample
log lines, pattern hints, non-match cases, and verification steps already
drafted, so the PR is mostly a translation exercise.

For rule proposals, use `docs/contributing-a-diagnostic-rule.md` and keep the
change scope to one signal and one fixture pair.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

Keep rules deterministic, explain the evidence they match, and add regression
coverage for both the intended failure and a nearby non-failure case. Do not add
commands that change AWS resources or require credentials.

## Pull requests

Use the repository PR template and keep a change narrow enough to review safely.
For new diagnostics, follow [Contributing a diagnostic rule](docs/contributing-a-diagnostic-rule.md)
and include both a positive fixture and a nearby non-match. Maintainers may ask
for a smaller excerpt or clearer evidence before merging.
