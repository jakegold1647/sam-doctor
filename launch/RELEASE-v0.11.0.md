# SAM Doctor v0.11.0

Two new rules, and a fix for a bug that was quietly costing people evidence.

**A specific failure no longer hides the stack's other failures.** Nine status
reasons - a taken or invalid bucket name, the code storage quota, a
stabilization timeout, an in-use export, reserved concurrency, a nested stack,
an API with no methods, a prohibited trust-policy field - suppressed the
generic resource-failure rule for the whole log. A stack that failed one of
those *and* an unrelated resource reported only the first, and stacks rarely
fail exactly one resource. Those now exclude their own line instead, so the
specific finding and the rest of the stack's failures both appear.

New rules:

- A nested (embedded) stack failed, with the root cause in the child stack's
  events - including the warning that rollback can delete those events before
  anyone reads them.
- Reserved concurrency would drop the account below its minimum unreserved
  value, an account-level ceiling rather than a template problem.

Also in this release: an empty log now says it is empty instead of reporting
"no supported pattern found" (across the CLI, the Action's job summary, batch
mode, and the evidence packet), redaction covers the CamelCase credential keys
that `aws sts` output prints, the catalog gate rejects patterns that backtrack
catastrophically, and a new interaction guard checks that no rule hides
another's finding.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Marketplace Action with `jakegold1647/sam-doctor@v0.11.0`.
- Match on `rule_id` in JSON and SARIF output, not on titles - see
  `docs/stability.md`.
- Reports remain local, redacted, and evidence-first. Redaction is a
  guardrail, not a secret scanner: review a report before sharing it.
