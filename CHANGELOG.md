# Changelog

All notable changes to SAM Doctor are documented here.

## Unreleased

- Added a rule for `ReservedConcurrentExecutions` dropping the account below
  its `UnreservedConcurrentExecution` minimum. Fresh accounts, whose
  concurrency limit can still be at the 1,000 default (or lower), hit this
  reserving concurrency for even one function; the log previously fell
  through to the generic `CREATE_FAILED` finding.
- The nested-stack rule excludes the embedded-stack line from the generic
  resource-failure rule per line rather than suppressing that rule for the
  whole log. A parent stack that fails a child usually fails other resources
  too, and whole-log suppression dropped those other failures from the report
  entirely - the opposite of what someone debugging a nested deployment needs.

- Added a rule for nested (embedded) stack failures. When a `AWS::Serverless::Application`
  or nested `AWS::CloudFormation::Stack` fails, the parent's own event only
  says an embedded stack was not successfully created or updated - the actual
  root cause lives in the child stack's own events, and rollback can delete
  the child stack before anyone reads them. The new rule takes priority over
  the generic CREATE_FAILED/UPDATE_FAILED and rollback findings on these
  lines and points at the child stack's ARN instead. Closes #23.

- The executable-bit check now also looks at untracked scripts, so a missing
  bit fails locally instead of one commit later. The existing check reads the
  git index, which cannot see a script that has never been added: the suite
  passes, the commit lands, and CI fails on the next push. That happened twice
  while adding gate scripts.

- Added a scheduled documentation-link check. Every finding points a user at
  official documentation, and those links rot quietly as AWS reorganizes its
  docs - nothing in an offline test suite can notice. All 31 unique links
  currently resolve. The check runs weekly rather than in the pull-request
  gate on purpose: sam-doctor's premise is offline determinism, and a network
  call in that gate would make a contributor's build depend on someone else's
  website being up.

- Closed two coverage gaps found by measuring rather than guessing.
  `python -m sam_doctor` - the fallback the README recommends when the console
  script is not on PATH - had no test at all, so breaking it would have left a
  documented instruction failing with nothing in CI to notice; it is now
  exercised end to end for version, diagnosis, the fail gate, and the exit-2
  usage path. The Action's single-log annotation path, which is the mode most
  workflows use, also had no direct test, though the batch branch did.

- An empty log now says so instead of reporting "no supported pattern found".
  A deploy step that fails before writing output leaves an empty log, and the
  old wording told the user the tool had read their failure and not recognized
  it - so the honest next step (check the step that writes the log) was
  replaced by an invitation to file a rule request for an excerpt that does
  not exist. Terminal and Markdown output distinguish the two cases; the JSON
  and SARIF payloads are unchanged, since a zero finding count already says it
  accurately and their shapes are covered by the stability promise. The
  Action's job summary - the surface most CI users actually read - is rebuilt
  from that payload and so could not tell the two cases apart; the wrapper now
  checks the log itself, per file in batch mode. `sam-doctor packet` renders
  the same Markdown into the artifact people attach to a ticket, so it makes
  the distinction too.

- Large logs now say what they are doing. Diagnosis is roughly a second per
  megabyte, so a 100 MB log took a silent minute and looked like a hang; past
  25 MB the CLI notes the expected wait on stderr, leaving stdout clean for
  the machine-readable formats. Measured first: the per-line prefilter was
  profiled against a single-pass alternative (slower) and every pattern was
  timed individually (no outlier), so this is a reporting fix rather than a
  speculative rewrite of the matching hot path.

- The rule catalog gate now times every pattern against adversarial input and
  fails any that backtracks catastrophically. sam-doctor reads log text it
  does not control, so a nested-quantifier pattern in a future rule could hang
  the CI job of anyone running it; the bait strings are sized so a bad pattern
  reports a clear failure in seconds instead of hanging the check itself. All
  46 current rules pass, and the whole gate still runs in under a tenth of a
  second.

## v0.10.0 - 2026-08-08

- Added a rule for invalid or wrong-account AWS credentials
  (`UnrecognizedClientException`, `security token included in the request is
  invalid`), distinct from expired credentials - the invalid rule defers when
  the expired wording is present so the more precise finding wins. From
  roadmap entry 8, issue #31, contributed in #55. Catalog is now 46 rules.
- Added a dedicated rule for a stack stuck in `UPDATE_ROLLBACK_FAILED`
  (the rollback of a failed update itself failed and needs
  `continue-update-rollback`), distinct from the existing `ROLLBACK_COMPLETE`
  rule for an unrecoverable initial create. The generic rollback rule is now
  suppressed by either terminal state so exactly one finding fires. Closes
  #29 (roadmap entry 6).
- Hardened redaction against four leak shapes found in an audit: the
  CamelCase `"SecretAccessKey"`/`"SessionToken"` JSON keys that `aws sts`
  output prints (previously only the underscore spellings were caught, so a
  pasted assume-role response leaked the real secret key), presigned-URL
  `X-Amz-Signature` values, Slack tokens from CI notification steps, and PEM
  private-key blocks including truncated ones. The fuzz corpus now carries
  all four shapes, and the clock-skew evidence the expired-credentials rule
  depends on is verified to survive untouched.
- Added ten more error-reference pages: the Lambda per-function package
  size limits, the regional code storage quota, the interactive changeset
  prompt hanging CI, termination protection blocking a delete, the unbuilt
  `CodeUri` artifact path, the Lambda service's own ECR pull being refused,
  the duplicate CORS `OPTIONS` preflight, pip dependency resolution, the
  Python runtime/interpreter mismatch, and the `--resolve-s3`/`--s3-bucket`
  conflict, plus nine more covering the full OIDC trio, the trust-policy
  prohibited field, code signing on container images, InvalidBucketName,
  the unreadable layer artifact, the failed wheel build, and the rollback
  that cannot delete an IAM role, and finally the five triage-method pages
  for the generic families (CREATE_FAILED, rollback states, AccessDenied,
  failed changesets, and the single-property mismatch). Every rule now has a
  dedicated page, and the drift gate requires an entry for each - a new rule
  cannot land without its page. v1-milestone item 4 is done.
- The rollout doc now walks teams up the confidence gate (observe, then
  `fail-on-confidence: high`, then `fail-on-findings`) and shows the SARIF
  code-scanning upload.
- Added the missing `launch/RELEASE-v0.9.0.md` launch note the release gate
  requires; the v0.9.0 release workflow failed on exactly that check.

## v0.9.0 - 2026-08-07

- Added five error-reference pages to the website for the highest-traffic
  rules that had none: template schema validation
  (`InvalidSamDocumentException`), a concurrent stack operation
  (`OperationInProgressException`), a taken bucket name
  (`BucketAlreadyExists`), the deployment bucket denying its own artifacts
  (`S3 error: Access Denied`), and template size/count quotas. The error
  index links all five, and `ERROR_PAGE_MAP` in the drift gate now keys by
  stable rule id - 20 of 44 rules have a dedicated page.
- Completed the fixture registry started in #49: every one of the 44 catalog
  rules now has a sanitized positive fixture and a nearby non-match in
  `scripts/check-rule-fixtures.py`, and the registry is keyed by stable rule
  id instead of title, so rewording a rule cannot orphan its fixtures. The
  check now also fails when a catalog rule has no entry, which makes the
  fixture pair a requirement for landing a new rule rather than a
  convention. Closes the follow-up promised on issue #40.
- Added Windows CI coverage for the documented support path: a
  `verify-windows` job runs the quality gates, the full test suite, demo,
  batch, packet, and `init` on `windows-latest`, and exercises the composite
  Action itself on a Windows runner. The action-wrapper tests now skip
  cleanly when bash is not WSL (Git Bash cannot see `/mnt` drive mounts) -
  the Action is covered directly by the CI job instead - and
  `CONTRIBUTING.md` documents that skip as expected. From issue #42.
- Added `sam-doctor request-packet` for the unmatched-log case: when
  `diagnose` finds no supported pattern, it writes a single redacted excerpt
  (a few lines of context around the first likely error, capped at
  `--max-lines`) instead of asking a contributor to copy a whole log into a
  rule request by hand. Runs the same redaction as reports, stays local and
  offline, and says so plainly when nothing in the log looks like an error.
  From issue #41.
- Added `scripts/check-error-pages.py`, an objective gate that keeps
  `site/errors/` and the rule catalog from drifting apart per issue #39.
  `ERROR_PAGE_MAP` inventories the 15 rules that already have a dedicated
  page; the check fails on a mapping pointing at a renamed or removed rule,
  a page that no longer exists, two rules sharing a page, or a page that
  exists (or is linked from `site/errors/index.html`) without a mapping
  entry. Rules without an entry keep using the index page's request-a-rule
  prompt, per the `docs/v1-milestone.md` item 4 concern this closes. It ships
  in `scripts/check-pr.py`, CI, and `tests/test_error_pages.py` alongside the
  existing rule catalog gate.
- Added `scripts/check-rule-fixtures.py`, a fixture registry that pairs each
  rule title with a sanitized positive log line and a nearby non-match, and
  checks that the positive fires the rule, the negative does not, and neither
  contains an account id, ARN, access key, or email address. It ships in
  `scripts/check-pr.py`, CI, and the test suite (`tests/test_rule_fixtures.py`)
  alongside the existing rule catalog gate. This first PR migrates the GitHub
  Actions OIDC rule family (4 rules); the rest of the catalog is a follow-up,
  per issue #40.
- Added an opt-in confidence gate: `--fail-on-confidence high` (or `medium`)
  on `diagnose` and `batch`, and a matching `fail-on-confidence` input on the
  Action. It fails the run only when a finding at that confidence or above is
  present, so a team can start by gating on high-confidence findings and
  tighten later. Reports, outputs, and annotations still include every
  finding - only the exit status is gated - and `--fail-on-findings` keeps its
  exact old meaning; when both are given, the explicit threshold is the gate.
  `sam-doctor init --fail-on-confidence high` writes the threshold into the
  generated workflow, from the parallel #52 implementation reconciled in that
  merge. From issue #38.
- Added `--format sarif` to `diagnose`, `demo`, and `batch`: the same findings
  rendered as one SARIF 2.1.0 run, ready for `github/codeql-action/upload-sarif`
  or any other SARIF consumer. Results carry the stable rule id from #47 as
  `ruleId`, high confidence maps to `error` and medium to `warning`, and batch
  mode emits a single document whose results point at their own log files.
  Evidence and source paths go through the usual redaction first. The rule
  table lists only the rules that fired; the full catalog stays with
  `sam-doctor rules`. From issue #43. The parallel #54 implementation
  contributed `docs/schemas/sarif-report.schema.json`, a narrowed contract for
  the emitted shape, now registered under `sam-doctor schemas` and validated
  in the test suite.
- Added a rule for a template that fails SAM or CloudFormation schema
  validation (`InvalidSamDocumentException`, `InvalidResourceException`,
  `Encountered unsupported property`, and a `property ... not defined for
  resource of type` mismatch without the colon the existing property rule
  requires). The existing "A SAM template property is not valid for its
  resource type" rule already owns the colon-and-`AWS::Serverless::` form of
  that wording, so the new rule is suppressed whenever that specific form
  matches - only one finding fires either way. From roadmap entry 7, issue
  #30. Catalog is now 44 rules.
- Gave every diagnostic rule a stable id (`iam.deny.explicit`, and so on),
  distinct from the title. The id now travels with each finding as `rule_id`
  in the diagnose/batch JSON, and with each entry in the rules JSON catalog
  as `id`. Titles and explanations are still free to be reworded as evidence
  improves; the id is the safe integration key for CI dashboards and other
  downstream tooling, and `docs/stability.md` now says so. The catalog check
  rejects a missing, duplicate, or malformed id the same way it already
  rejects a duplicate title. Both schemas add `rule_id`/`id` as required,
  additive fields - existing consumers reading only the fields they already
  knew about keep working. From issue #37.
- Added a rule for a deployment bucket that denies access to the packaged
  artifacts (`S3 error: Access Denied` from `CreateChangeSet`, and a denied
  `PutObject`/`GetObject`/`HeadObject` while uploading to the artifact bucket).
  The explanation separates the two directions - the CLI uploading versus
  CloudFormation reading back, which fail for different identities - and the
  verification steps cover a wrong-Region `s3_bucket`, an SSE-KMS bucket whose
  key the identity cannot use, and cross-account bucket ownership. IAM-worded
  denials (`is not authorized to perform: s3:PutObject ... explicit deny`) stay
  with the explicit-deny and no-policy-allows rules, which name the policy
  layer; only the tool-level S3 wording is claimed here. The generic
  access-denied rule skips those lines per line, so an unrelated `AccessDenied`
  elsewhere in the same log still reports. From roadmap entry 5, issue #28.
  Catalog is now 43 rules.
- Taught the S3 bucket-name collision rule the modern resource-handler wording
  (`Resource handler returned message: "The requested bucket name is not
  available..."`), which previously fell through to the generic `CREATE_FAILED`
  finding. The accompanying `HandlerErrorCode: AlreadyExists` is shared by every
  resource type, so it is deliberately not matched on its own - an
  `AWS::IAM::Role` that already exists still gets the generic finding.
  Suppression is unchanged, so a log carrying only the new wording keeps
  reporting unrelated `CREATE_FAILED` resources alongside the collision.
- Added a rule for a template that exceeds a CloudFormation size or count quota
  (the `templateBody` length constraint, `Template format error: Number of ...
  is greater than maximum allowed`, and the `may not exceed N bytes` wording).
  CloudFormation rejects the template before it evaluates any resource, so the
  guidance is to measure the rendered template, submit it through S3 for the
  larger 460,800-byte ceiling, or split the stack. Patterns stay anchored to
  template quota wording so an ordinary `ValidationError` about a missing
  parameter still gets the generic change-set finding, which this rule
  suppresses when it fires. From roadmap entry 4, issue #46. Catalog is now 42
  rules.
- Added a rule for an S3 bucket name that is already taken
  (`BucketAlreadyExists`, `BucketAlreadyOwnedByYou`). Bucket names are globally
  unique, so an explicit `BucketName` can collide with another account or with
  a bucket this account left behind; the guidance splits those two cases and
  stops short of deleting a bucket nobody has inspected. It stays distinct from
  the existing `InvalidBucketName` validation rule and suppresses the generic
  `CREATE_FAILED` and change-set findings so one finding fires per log. From
  roadmap entry 3, issue #20. Catalog is now 41 rules.
- Added a rule for a concurrent CloudFormation operation blocking the deploy
  (`is in CREATE/UPDATE/DELETE_IN_PROGRESS state and can not be updated`,
  `OperationInProgressException`). Normal `*_IN_PROGRESS` progress events and
  the rollback states stay with their existing rules, and the generic
  change-set finding is suppressed so the report names the in-flight
  operation as the cause. From roadmap entry 1.
- Added a rule for a missing build artifact referenced by the template
  (`Unable to upload artifact ... referenced by CodeUri`, `refers to a file
  or folder that does not exist`), the classic deploy-before-`sam build`
  failure. Suppresses the generic change-set finding on those logs. From
  roadmap entry 2. Catalog is now 40 rules.
- Added a rule for the Lambda regional code storage quota
  (`CodeStorageExceededException`, `Code storage limit exceeded`), which counts
  deployed packages, retained versions, and layers together and is distinct
  from the per-function package size limit added in v0.8.0. It suppresses the
  generic `CREATE_FAILED` finding so the report names the cause rather than the
  symptom. Contributed in #35. Catalog is now 38 rules.

## v0.8.1 - 2026-08-05

- Shortened the GitHub Action `description` in `action.yml` from 134 to 120
  characters. The GitHub Marketplace rejects any description of 125 characters
  or more, which failed validation on the v0.8.0 publish and left the
  Marketplace listing stuck on v0.7.4. No input, output, or behavior of the
  action changed.
- Corrected every README sample output so each block shows what the CLI
  actually prints. The demo, OIDC, rollback, capability, and proof blocks were
  verified against a fresh install; the proof section had shown a
  suggested-next-command line the tool has never emitted, and two use-case
  blocks paired `--format markdown` with terminal-format output.

## v0.8.0 - 2026-08-04

- Added a rule for Lambda per-function package size limits (`Unzipped size
  must be smaller than`, `Request must be smaller than ... bytes`), kept
  separate from the regional code-storage quota. Contributed in #34. Catalog
  is now 37 rules.
- `python -m sam_doctor` now works as an alias for the `sam-doctor` console
  script, matching what the README suggests when the script is not on PATH.
- Added two advanced diagnostics: resource stabilization failures
  (`did not stabilize`, `HandlerErrorCode: NotStabilized`, `Exceeded attempts
  to wait`) that surface the nested handler status reason first and route
  guidance for slow-by-design resource families (ACM, CloudFront, RDS, custom
  resources), and in-use stack exports (`Export ... cannot be updated/deleted
  as it is in use by`) with the `list-imports` staged-migration path and an
  explicit warning against deleting consumer stacks as a shortcut. Both
  suppress the generic CREATE/UPDATE/DELETE_FAILED findings for their logs.
  Catalog is now 36 rules.
- Split IAM access denials into two new high-confidence diagnostics with
  parsed denial context: an explicit-deny rule (including service control
  policies, which cannot be fixed from the member account) and an
  implicit-deny rule for `because no ... policy allows` errors that names the
  policy layer AWS expected the permission in. Findings now append the denied
  action, redacted principal/resource presence, and denial type parsed from
  the evidence; the generic access-denied rule still catches bare
  `AccessDenied` lines. Catalog is now 34 rules.
- Contributor on-ramp: CONTRIBUTING gained a full development-setup guide
  (fork/clone, virtual environments including Windows PowerShell, baseline
  commands that reproduce CI); the README now has a Contributing section near
  the top; the PR template checklist covers Ruff, the smoke check, and the
  rule-catalog gate; and a "Contributor setup problem" issue form reports
  environment failures with sanitized output.
- Added `scripts/check-pr.py`: one cross-platform command that runs every
  check a pull request must pass (site metadata, site QA, Ruff, rule-catalog
  gate, pytest, package build, smoke check), mirroring CI so failures surface
  locally before a push; `--fast` skips the build and smoke steps.
- Added `scripts/check-rule-catalog.py`, an objective quality gate for the
  rule catalog (patterns compile, cannot match empty input or ordinary
  successful deploy output, metadata complete); enforced in the test suite so
  local runs and CI report identical problems.
- Added `docs/rule-roadmap.md`: fully specified diagnostic-rule candidates
  (sample log lines, pattern hints, non-matches, verification steps) that a
  first-time contributor can claim and land in one focused PR; linked from the
  README and CONTRIBUTING.
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
