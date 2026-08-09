# Stability promise

What CI integrations can depend on, and what they cannot. This is the
commitment v1-milestone item 3 asks for; at 1.0 the README will link here.

## Stable now, frozen at 1.0

- **JSON report shapes.** The payloads described by
  `docs/schemas/diagnose-report.schema.json`,
  `docs/schemas/batch-report.schema.json`, and
  `docs/schemas/rules-report.schema.json`. Existing fields keep their names
  and types. New optional fields may be added; parse leniently.
  `docs/schemas/sarif-report.schema.json` narrows the same promise for the
  SARIF output: it describes the shape sam-doctor emits, not the full
  upstream SARIF 2.1.0 spec.
- **Rule IDs.** Every rule has a short id such as `iam.deny.explicit`
  (the `rule_id` field on findings, `id` in the rule catalog). Unlike titles
  and explanations, ids do not change when a rule's wording is tightened or
  reworded, and the catalog check rejects duplicates. Match on the id, not
  the title.
- **CLI surface.** The subcommands (`diagnose`, `demo`, `rules`, `schemas`,
  `packet`, `request-packet`, `batch`, `init`) and their documented flags. Flags
  may be added; documented flags will not be removed or change meaning within a
  major version. A test asserts this list matches the subcommands the CLI
  actually registers, so a new one cannot ship without a decision about whether
  it belongs under the promise.
- **Exit codes.** As documented in `docs/cli-exit-and-action-exit-codes.md`.
  `0` and `1` keep their meanings; new nonzero codes may be added for new
  failure classes.
- **Action inputs/outputs.** The composite Action's documented inputs and
  outputs in `action.yml`.

## Not covered by the promise

- The rule catalog's contents. Rules are added, tightened, and re-titled as
  evidence improves. Do not match on finding titles or explanation text;
  match on `rule_id`.
- Human-readable output: terminal formatting, markdown reports, wording.
- The website, docs, and launch material.

## Deprecation policy

Anything documented that must change gets one minor release of overlap: the
old form keeps working, the changelog says so, and the CLI warns on stderr
where it can. Removal happens no sooner than the next minor release after
the warning first ships.
