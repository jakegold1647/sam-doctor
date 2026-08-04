# Changelog

All notable changes to SAM Doctor are documented here.

## Unreleased

- Added a diagnostic for deployments that fail only because the change set was
  empty (`No changes to deploy`, `The submitted information didn't contain
  changes`, `No updates are to be performed`), pointing CI users at
  `--no-fail-on-empty-changeset`. Catalog is now 32 rules.
- Added seven diagnostic rules: expired AWS credentials and runner clock skew
  (`ExpiredToken`, `Signature expired`), CloudFormation API throttling
  (`Rate exceeded`), stack deletion blocked by termination protection, general
  `DELETE_FAILED` resource blockers, ECR push-authentication failures from CI
  runners (missing login, expired token, denied `ecr:GetAuthorizationToken`),
  and Docker unavailable for `sam build --use-container`. Catalog is now 31 rules.
- Made rule suppression declarative: rules carry `suppressed_by` and
  `excluded_line_patterns` instead of hard-coded logic in `diagnose()`, so new
  rules no longer edit engine code.
- Added `--format github` to diagnose, demo, and batch: one workflow-command
  annotation per finding with `file=`/`line=` properties and full
  workflow-command escaping; clean logs emit nothing.
- Findings now expose the first matching log line (`line_number`) in all
  report formats.
- Hardened redaction: quoted secret assignments (`password="..."`,
  JSON-style pairs), bare STS session tokens (`IQoJ...`/`FwoG...`), and the
  evidence-packet notes file (source path and command line) are now redacted;
  verified by a deterministic cross-format fuzz test.
- Roughly halved diagnose() time on large logs by scanning each line once
  against a combined pattern instead of once per rule.
- CLI failure paths (missing input, unwritable output, empty stdin) now
  consistently exit 2 and are covered by tests; documented exit codes for
  diagnose, batch, and the GitHub action.
- Batch mode gained `--fail-on-findings`.
- Re-dispatching the PyPI publish workflow for an already-published tag is now
  a safe no-op (`skip-existing`).
- Added diagnostic coverage for Python SAM build dependency validation failures
  (`PythonPipBuilder:ResolveDependencies`/`Binary validation failed`) with
  demo fixture and ordered rule matching.
- Added published JSON Schema documents for diagnose, batch, and rules JSON outputs,
  with schema-backed tests and a dev dependency on `jsonschema` for local CI
  validation.
- Added structured SEO metadata to the project landing page (`SoftwareApplication`,
  `FAQPage`, and `HowTo`) to improve discoverability for common deployment
  diagnostic queries.
- Added Ruff checks to the CI validation workflow so style and lint failures
  fail fast and local contribution requirements are explicit.
- Enforced website QA during GitHub Pages publish so link/metadata regressions
  are blocked before docs deploy.
- Marked package maturity as Beta in `pyproject.toml` to improve distribution
  trust signals in package indexes.

## v0.7.7 - 2026-08-03

- Added a focused diagnostic for Lambda failures caused by missing ECR container-image access.
- Documented direct CLI failure gating for shell-based CI jobs.
- Switched the primary install path to the verified PyPI package.
- Clarified the common GitHub OIDC audience mismatch in the deployment guide.

## v0.7.6 - 2026-08-03

- Added an opt-in `--fail-on-findings` CLI flag for CI jobs that should fail
  when a supported diagnostic is found.
- Recognized CloudFormation `ROLLBACK_FAILED` states and added cleanup-focused
  verification guidance for stacks that cannot finish rolling back.
- Kept the stable install links, Marketplace example, and release metadata on
  one tested version.

## v0.7.5 - 2026-08-03

- Fixed stable PyPI recovery so the current workflow runs from `main` while
  building the exact release tag supplied by the operator.
- Added coverage for CloudFormation's `ROLLBACK_FAILED` stack state, including
  the cleanup-focused verification step.
- Added an opt-in CLI `--fail-on-findings` flag for direct CI gating without the
  composite GitHub Action.

## v0.7.5 - 2026-08-03

- Promoted the tested prerelease to a stable package and Marketplace Action
  release with a verified GitHub wheel install path.
- Added an explicit workflow-dispatch handoff so automated stable releases can
  publish to PyPI even when GitHub does not fan out the release event.
- Documented the exact manual PyPI workflow retry fields for the first stable
  publication or a later recovery.

## v0.7.5-rc.1 - 2026-08-03

- Published the first tested prerelease containing the polished CLI install path,
  Action diagnostics, and ethical growth feedback improvements.

- Fixed ASCII-only trend reporting in `scripts/check-distribution.py` and removed
  duplicated trend calculation logic.
- Polished Marketplace publishing docs to separate prerelease workflow behavior from
  manual listing publish steps.
- Updated release automation so plain tags (`vX.Y.Z`) publish as public releases
  while pre-release tags keep prerelease behavior.
- Kept scheduled distribution monitoring from treating the intentionally
  pre-release Marketplace build as a failed stable-release gate.
- Hardened release automation for existing tag re-runs and clarified PyPI/launch
  docs to match release-tag behavior.
- Added a lightweight outreach tracking template to support the ethical,
  conversation-first growth loop.
- Added an organic-growth score and concrete next actions to outreach summaries
  so real follow-through is easier to measure without incentivizing stars.
- Replaced placeholder install examples with verified release commands and
  removed the unavailable PyPI badge from the first-use path.
- Clarified the GitHub Actions example so diagnostics still run after a failed
  deployment step.
- Standardized the README's installed-command examples and documented the
  module fallback for shells that do not expose the console script.
- Added a clear sanitized rule-request path when a human-readable report finds
  no supported pattern.
- Made the test suite import the checked-out source tree so local runs cannot
  silently exercise an older installed package.
- Added Marketplace and PyPI badges to the README launch header.
- Added regression tests for the distribution checker trend helpers and output text.
- Added a release-readiness checker script and integrated it into launch docs and
  README for pre-tag validation.
- Replaced stale hard-coded release version examples in install and CI snippets
  with version placeholders to reduce release drift.
- Added a dedicated rule for non-interactive SAM deploy confirmation prompts
  (`Aborted! Deploy this changeset?`) to improve CI-directed diagnosis.
- Added a dedicated rule for CloudFormation rollback role-deletion failures so role
  cleanup blockers are called out as a separate action path.
- Added an outreach metrics helper (`scripts/check-outreach.py`) and launch docs
  guidance to keep ethical, repeatable growth tracking lightweight.
- Added `--strict-distribution-during-release` to `scripts/check-launch.py` so
  teams can keep pre-release checks non-blocking while enforcing full
  distribution-channel readiness after publication.
- Deepened outreach health checks so we can distinguish paid-interest signal from
  uncontextualized voluntary stars and keep outreach loops ethical.
- Added a new `batch` CLI subcommand to diagnose multiple deployment logs in one
  run and aggregate findings for local triage.
- Added launch-readiness validation of marketplace action metadata so pre-release
  checks catch listing blockers before manual publication.
- Improved batch output to preserve full source paths for duplicate filenames
  (especially from similarly-named directories) and to include per-file markdown
  section labels.
- Strengthened launch-readiness checks so stable versions fail when their
  associated GitHub release is a draft or prerelease, preventing misleading
  Marketplace pre-release states.
- Added launch-readiness snapshot capture to the 12-hour distribution workflow so
  repository publish checks are archived with distribution trend artifacts.
- Added an outreach execution checklist for ethical pre-founder asks and a
  concrete 12-hour-informed review cadence in the outreach playbook.

## v0.7.4 - 2026-08-03

- Renamed the GitHub Action display name to `SAM Doctor AWS Deployment
  Diagnostics` so it can be uniquely listed in GitHub Marketplace.

## v0.7.3 - 2026-08-03

- Added GitHub Marketplace branding to the composite action and refreshed the
  diagnostic issue form's version placeholder.

## v0.7.2 - 2026-08-03

- Redacted sensitive identifiers in displayed source filenames as well as matched
  log evidence across terminal, Markdown, and JSON reports.

## v0.7.1 - 2026-08-03

- Ordered multiple findings by the first supporting line in the supplied log so
  earlier failures are presented before downstream deployment noise.

## v0.7.0 - 2026-08-03

- Added direct findings for invalid SAM template properties, IAM trust-policy
  `Resource` fields, Lambda image code-signing conflicts, invalid S3 bucket
  names, and S3 access denied for Lambda layer artifacts.

## v0.6.0 - 2026-08-03

- Added a composite GitHub Action with redacted job-summary output and opt-in
  failure gating for supported findings.
- Added direct findings for a missing `esbuild` dependency, conflicting SAM S3
  deployment options, API Gateway deployments with no methods, and non-updatable
  initial stacks in `ROLLBACK_COMPLETE`.

## v0.5.0 - 2026-08-03

- Added a high-confidence diagnosis for CloudFormation capability acknowledgements
  required by IAM resources and nested applications.

## v0.4.1 - 2026-08-03

- Redacted bearer tokens and JWT-shaped tokens when they appear in matched evidence.

## v0.4.0 - 2026-08-02

- Added a direct diagnostic when a GitHub Actions job lacks `id-token: write`.
- Added a direct diagnostic for a missing GitHub Actions OIDC provider in the
  target AWS account.

## v0.3.1 - 2026-08-02

- Added the tool version to JSON reports and the rule catalog.
- Added a practical GitHub Actions to AWS OIDC troubleshooting guide.
- Updated OIDC verification guidance for GitHub's immutable subject-claim format.

## v0.3.0 - 2026-08-02

- Added a catalog command: `sam-doctor rules`.
- Added a bundled CloudFormation failed-resource demo.
- Added a direct high-confidence finding for CloudFormation `CREATE_FAILED` and
  `UPDATE_FAILED` resource events.
- Tightened OIDC audience matching so a generic `InvalidIdentityToken` is not
  reported as an audience problem without supporting evidence.
- Redacted common key, token, password, and session-token assignments in evidence.

## v0.2.0 - 2026-08-02

- Added JSON output for scripts and CI.
- Added stdin support with `sam-doctor diagnose -`.
- Redacted common AWS access key IDs and GitHub token formats in matched evidence.
- Made Markdown evidence safe to render and bounded evidence excerpts from noisy logs.
- Reduced false positives for successful SAM, CORS, and STS log lines.
- Expanded CI coverage across Python 3.10, 3.11, and 3.12.

## v0.1.0 - 2026-08-02

- Initial free alpha with local diagnostics for supported AWS SAM, CloudFormation,
  IAM, API Gateway CORS, and GitHub Actions OIDC failures.
