# SAM Doctor v0.6.0

SAM Doctor v0.6.0 makes it easier to use the local diagnostic in GitHub Actions
without hand-writing an installation or report-parsing step.

## Highlights

- Adds a composite GitHub Action: `jakegold1647/sam-doctor@v0.6.0`.
- Exposes `finding-count` and `has-findings` workflow outputs.
- Keeps Markdown job summaries and failure gating opt-in, so a workflow author
  chooses when diagnostics should be surfaced or fail a job.
- Adds high-confidence diagnosis for four public deployment signals: missing
  `esbuild`, conflicting `--resolve-s3` and `--s3-bucket` settings, API Gateway
  deployments with no methods, and initial stacks left in `ROLLBACK_COMPLETE`.

The action analyzes only the log file supplied by the workflow. Its summary
contains matched, redacted evidence rather than the full input log; review it
before sharing a workflow run outside your team.
