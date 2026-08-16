# Contributor quickstart

You can make a useful SAM Doctor contribution without AWS credentials, private
logs, or a large feature. Pick one small task, show the evidence, and ask for
help early if you get stuck.

## Pick one starting point

- [Add a sanitized deployment-log example](https://github.com/jakegold1647/sam-doctor/issues/69) — documentation only.
- [Add a first-deployment pilot checklist](https://github.com/jakegold1647/sam-doctor/issues/71) — documentation and examples.
- [Add a contribution-friendly CI recipe index](https://github.com/jakegold1647/sam-doctor/issues/77) — documentation only.
- [Add a safe first-run workflow](https://github.com/jakegold1647/sam-doctor/issues/73) — a credential-free GitHub Actions example.
- [Add a CloudFormation stack-name collision rule](https://github.com/jakegold1647/sam-doctor/issues/66) — one diagnostic, one fixture pair.

For the pilot issue, use the [first-deployment pilot checklist](adoption-pilot.md) to verify the tracked examples before wiring CI.\n\nThese issues are marked ready and have a maintainer path. If none fits, use the
[ready newcomer queue](https://github.com/jakegold1647/sam-doctor/issues?q=is%3Aissue+is%3Aopen+label%3A%22status%3A+ready%22+label%3A%22mentor%20available%22).

## Claim it before editing

Comment on one issue:

> I'd like to take this. I'll start with `<file or example>` and verify it with
> `<command>`.

That prevents duplicate work. A maintainer will confirm the scope and answer
setup questions. Draft PRs are welcome before the work is finished.

## Set up and verify

```bash
git clone https://github.com/YOUR-USER/sam-doctor.git
cd sam-doctor
python -m pip install -e ".[dev]"
python scripts/check-pr.py --fast
```

If the baseline fails before you edit anything, stop there and use the
[contributor setup form](https://github.com/jakegold1647/sam-doctor/issues/new?template=setup_problem.yml).

## Keep the first PR narrow

For a diagnostic, add one positive sanitized example and one nearby non-match.
For documentation or examples, include the exact command a reviewer can run.
Never include account IDs, ARNs, credentials, tokens, customer data, or raw
production logs.

When ready, open a draft PR, link the issue, and include:

1. what changed;
2. the command or test you ran; and
3. anything you want reviewed before you continue.

The full details are in the [contributor guide](../CONTRIBUTING.md) and the
[diagnostic-rule guide](contributing-a-diagnostic-rule.md).
