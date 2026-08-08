# SAM Doctor v0.9.0

The integration release. Every rule now carries a stable id
(`iam.deny.explicit`, and so on) that travels through JSON reports, the rules
catalog, and the new SARIF output, so CI dashboards and code-scanning alerts
stay tied to a rule across releases even when its wording improves. Six
community pull requests from this cycle are part of the release.

Highlights:

- `--format sarif` on `diagnose`, `demo`, and `batch` emits a SARIF 2.1.0 run
  ready for GitHub code scanning, with a narrowed schema contract under
  `docs/schemas/`.
- `--fail-on-confidence high` (CLI and Action) gates CI on high-confidence
  findings only, without hiding anything from reports; `--fail-on-findings`
  keeps its exact old meaning.
- `sam-doctor init` now writes a manual-only workflow until you opt into
  `--on-push`, so trying it can never wire up an automatic AWS deployment.
- `sam-doctor request-packet` writes a small redacted excerpt for rule
  requests when nothing matches - never the whole log.
- Six new rules bring the catalog to 44, each with a positive/negative
  fixture pair enforced in CI, and Windows joins the tested support matrix.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Marketplace Action with `jakegold1647/sam-doctor@v0.9.0`.
- Match on `rule_id` in JSON and SARIF output, not on titles - see
  `docs/stability.md`.
- Reports remain local, redacted, and evidence-first.
