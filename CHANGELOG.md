# Changelog

All notable changes to SAM Doctor are documented here.

## Unreleased

- **The credential-free first run now names its contract.** The public
  quickstart points to the tracked OIDC sample, states the one expected rule,
  and links support boundaries plus the sanitized usage-feedback path. The
  example index documents how to update the packaged mirror, and a regression
  test keeps both sample copies aligned.

- **Usage-report triage now has four copy-ready maintainer paths.** Helped,
  missed, unclear or unsafe, and setup-friction reports each ask for the
  minimum sanitized evidence, link the right public route, and state when to
  escalate into a scoped contribution.

- **API Gateway deployment throttling now has its own diagnosis.** Anchored
  `TooManyRequestsException` CLI errors and CloudFormation
  `Service: ApiGateway` 429 status reasons point to backoff, account/Region
  deployment serialization, and the relevant control-plane quotas. Bare
  runtime HTTP 429 responses do not match, and the specific finding replaces
  generic change-set or resource-failure noise for the same event.

- **Generated workflows now preserve multiline deploy commands.** `init` used to
  indent only the first line, leaving later lines outside the YAML block while
  still reporting success. The generated step now groups and captures the full
  Bash script, and rejects an empty `--deploy-command` before writing a file.

- **Recursive batch wildcards now reach every directory depth.** A quoted
  `logs/**/*.log` pattern previously behaved like a one-level `*`, silently
  skipping root and deeply nested logs. `**` now has its conventional recursive
  meaning without following directory symlinks into loops.

- **Capped rule-request excerpts keep the actual error line.** When `--context`
  exceeded `--max-lines`, the old window took its first lines and could omit the
  failure it was meant to share. The cap is now centered on that failure, and
  negative context or non-positive line limits fail before creating artifacts.

- **BOM-aware decoding now applies to redirected standard input.** `diagnose -`,
  `packet -`, `request-packet -`, and the repository packet wrapper preserve raw
  stdin bytes until the shared UTF-8/16/32 decoder runs. Previously a UTF-16
  failure piped to these commands silently produced zero findings even though
  the same log was diagnosed correctly by file path.

- **Action summaries now recognize empty Windows-encoded logs.** The composite
  Action uses the CLI's BOM-aware decoder when distinguishing an empty log from
  an unmatched failure, so UTF-16 whitespace no longer produces a misleading
  “No supported pattern found” summary.

- **A command-launch error no longer erases the previous deployment log.** The
  `run` wrapper now waits until the child process starts before truncating an
  existing `--log-file`; successful runs still replace stale output.

- **Quoted secret assignments are now redacted as one value.** Evidence that
  contains a quoted password, token, or secret with spaces no longer leaves the
  words after the first space visible, and the replacement keeps balanced
  quotes. The browser demo uses the same generated behavior as the CLI.

- **Batch mode no longer counts an overlapping input more than once.** When a
  directory, glob, or literal path expands to a log that an earlier argument
  already selected, the first occurrence now wins instead of duplicating the
  result and inflating aggregate finding counts.

- **Report and deployment-log outputs no longer follow symbolic links.** The
  CLI now refuses a symlink used as a report, packet, generated-workflow, or
  `run --log-file` target, matching its hard-link safeguards instead of
  overwriting the link's target under a different path.

- **The website hero now diagnoses a log instead of picturing one.** Paste a
  failed deploy log into the panel on the front page and it reports the same
  findings the CLI would - title, confidence, redacted evidence, next checks,
  rule id and matched line - computed in the browser, with no request made and
  nothing uploaded. "Try a sample failure" loads one of the shipped sample logs
  for anyone without a log to hand. The rule catalog the page matches on is
  generated from `diagnostics.py` and `redaction.py` by
  `scripts/build-site-rule-catalog.py`, which CI runs with `--check` so the
  page cannot drift from the rules; the test suite compares the two engines
  over every rule fixture, every bundled sample, and a corpus of mutated logs.
  With JavaScript unavailable the panel still shows the worked example it
  showed before. No packaged behaviour changed.

## v0.12.2 - 2026-08-11

- **Fixed the PyPI package-page demo image.** The README now uses an absolute
  public asset URL, so PyPI can proxy and render the image instead of emitting
  a bad URL-scheme error. No functional changes.

## v0.12.1 - 2026-08-11

- **Corrected public install guidance and catalog counts.** The README and
  package page now direct users to the stable PyPI release, which already
  includes all 90 documented diagnostics, the `run` wrapper, and clipboard
  handoff. No functional changes.

## v0.12.0 - 2026-08-10

- **The GitHub Marketplace Action can now publish current release metadata.**
  Its short description now meets the Marketplace limit, so the listing can
  advance with this stable release instead of staying on an older version.

- **SAM lint summaries now point back to the matched cfn-lint rules.** A
  medium-confidence finding recognizes the exact `sam validate --lint` failure
  summary and directs the reader to the nearby E/W rule output without
  claiming that the wrapper identifies a specific template problem.

- **Deprecated Lambda runtimes now have a focused deployment handoff.** A
  high-confidence finding recognizes the exact create/update rejection, points
  at the submitted `Runtime`, and leaves quoted documentation alone. The
  generic CREATE_FAILED / UPDATE_FAILED finding still reports unrelated failed
  resources from the same log.

- **Missing CloudFormation stack exports now have a focused handoff.** A
  high-confidence finding recognizes `No export named ... found`, points at the
  producer stack and account/Region boundary, and keeps missing exports
  distinct from exports that cannot be changed while in use.

- **CloudFormation circular dependencies now have a focused handoff.** A
  high-confidence finding recognizes `Circular dependency between resources`,
  points at the transformed dependency graph, and keeps the cycle distinct from
  generic resource, rollback, and change-set wrappers.

- **Lambda VPC execution-role failures now have a focused handoff.** A
  high-confidence finding recognizes `The provided execution role does not have
  permissions to call CreateNetworkInterface on EC2`, points at the function's
  ENI permissions, and keeps the deployer role and lower-level EC2 network
  failures separate.

- **Non-ASCII resource property rejections now have a focused handoff.** A high-confidence finding recognizes `Character sets beyond ASCII are not supported` and points at locating the hidden character instead of retyping the property value blind. The generic CREATE_FAILED / UPDATE_FAILED finding no longer also reports the same line, but keeps reporting any other resource failure in the same log.

- **API Gateway enhanced security-policy failures now have a focused handoff.**
  A high-confidence finding recognizes the missing endpoint-access-mode marker
  and points at the transformed API resource instead of suggesting IAM changes.

- **Bare Kubernetes pod-sandbox network failures now have a focused handoff.**
  A low-confidence fallback preserves the CNI plugin and node-level evidence,
  while specific EKS VPC CNI and network-policy findings continue to take
  precedence when their markers are present.

- **EKS network-policy-agent failures now have a focused handoff.** A
  medium-confidence finding recognizes the policy setup markers, points at the
  `aws-network-policy-agent` logs and EKS prerequisites, and yields to that
  stage instead of repeating the generic pod-sandbox wrapper.

- **SAM build output permission failures now have a focused handoff.** A
  medium-confidence finding recognizes permission errors under `.aws-sam/build`
  and points at local ownership, locks, and generated-output cleanup without
  suggesting Docker or AWS IAM changes.

- **Bedrock end-of-life model failures now have a focused handoff.** A
  high-confidence finding recognizes the model-lifecycle marker and points at
  checking the active catalog and migrating the model ID instead of retrying or
  changing IAM.

- **CDK asset-bundling failures now have a focused handoff.** A low-confidence
  finding recognizes the asset and temporary output wrapper, then points at the
  underlying compiler, dependency, permission, or Docker error without guessing
  which one occurred.

- **Bedrock nested message-content validation failures now have a focused
  handoff.** A medium-confidence finding surfaces the indexed missing field
  path, including text, thinking, image, and document content blocks, before
  changing model access or IAM.

- **Bedrock missing-messages failures now have a focused handoff.** A
  medium-confidence finding recognizes the model-specific `messages: Field
  required` validation marker and points at the Claude Messages API body before
  changing model access or IAM.

- **EKS VPC CNI pod-sandbox failures now have a focused handoff.** A
  low-confidence finding recognizes the `aws-cni` wrapper, points at the
  matching `aws-node` or `ipamd` error, and yields to a nested EC2 cause when
  one is present.

- **Bedrock empty-model-id failures now have a focused handoff.** A
  medium-confidence finding recognizes the runtime client's exact serialization
  marker and points at the model configuration and request shape before model
  access or IAM changes.

- **EC2 network-interface creation wrappers now have a focused handoff.** A
  low-confidence finding preserves the nested `CreateNetworkInterface` status,
  error code, subnet capacity, permission, request-shape, and endpoint checks
  instead of treating the provider's outer wrapper as a root cause.

- **Bedrock first-use access failures now have a focused handoff.** A
  medium-confidence finding recognizes the account-level
  `Model use case details have not been submitted` marker, separates it from a
  missing model resource, and points at the provider form in the same account
  and Region.

- **Bedrock model lookup failures now have a focused handoff.** A
  medium-confidence finding recognizes the runtime's exact unresolved-model
  marker and points at the current model ID, Region, endpoint, and API instead
  of suggesting an IAM change.

- **Bedrock empty-system-prompt failures now have a focused handoff.** A
  medium-confidence finding recognizes the Botocore minimum-length marker and
  points at omitting an empty Converse system block before changing model access
  or IAM.

- **Unknown or invalid AWS API actions now have a focused handoff.** A
  low-confidence finding points at the operation, endpoint, API version,
  Region, SDK, or emulator support without mislabeling the failure as IAM.

- **Unimplemented AWS API actions now have a focused handoff.** A low-confidence
  finding points at the operation, endpoint, API version, Region, proxy, SDK,
  or emulator support without treating the response as an IAM denial.

- **Unknown AWS service routing now has a focused handoff.** A low-confidence
  finding points at the service target, endpoint URL, protocol, SDK, Region,
  proxy, or emulator without treating the response as an IAM denial.

- **STS caller-identity wrapper failures now have a focused handoff.** A
  low-confidence finding keeps the nested endpoint, Region, signing, network,
  and credential-source cause ahead of any IAM change.

- **AWS Glue database rename failures now have a focused handoff.** A
  high-confidence finding points at preserving the catalog name or creating a
  replacement database instead of changing IAM.

- **Cloud Control API operation wrappers now have a focused handoff.** A
  low-confidence finding points at the nested ProgressEvent, status message,
  error code, resource identity, and request token before retrying or changing
  IAM.

- **SAM change-set handoffs now recognize both wrapper wordings.** The existing
  medium-confidence configuration handoff accepts `Failed to create changeset`
  and `Failed to create the changeset`, while sharper template and service
  findings still take precedence.

- **The stable-versus-current catalog boundary is now explicit.** The public
  homepage, quickstart, machine-readable guide, and README say that the guides
  follow `main` (73 diagnostics) while stable PyPI `0.11.0` contains the
  released 48-rule catalog; the branch install remains the opt-in path until a
  new stable release is authorized.

- **ECS Exec managed-agent failures now have a focused handoff.** A
  medium-confidence finding recognizes `CannotStartManagedAgentError`, the
  matching `ExecuteCommand` wrapper, and its truncated operation-only form,
  then points at task launch enablement, `ssmmessages`, network, and
  writable-filesystem checks.

- **Unresolved CloudFormation dependencies now have a focused diagnosis.** A
  high-confidence finding recognizes `Template format error: Unresolved resource
  dependencies`, names the logical-ID checks to perform, and points at
  `sam validate --lint` or `cfn-lint` against the exact submitted template.

- **Lambda invoke target misses now have a focused handoff.** A medium-confidence
  finding recognizes `ResourceNotFoundException` from the Lambda `Invoke`
  operation and points at the exact function, qualifier, account, Region, and
  deployment-timing checks before anyone changes permissions.

- **CDK assembly failures now have a safe handoff.** A low-confidence finding
  recognizes `AssemblyError: Assembly builder failed`, points at `cdk synth
  --verbose` with the same app and context, and keeps the missing application
  error separate from any later CloudFormation failure.

- **CloudFormation wrapper failures now hand off to stack events.** A low-
  confidence finding recognizes `Failed to create/update the stack`, makes no
  unsupported root-cause claim, and points at the read-only event command and
  the first failed resource.

- **Terminal stack recovery now covers `DELETE_COMPLETE`.** The existing
  terminal-state diagnosis now recognizes both `ROLLBACK_COMPLETE` and
  `DELETE_COMPLETE` update refusals, with separate checks for the original
  failed create, deletion completion, and retained resources.

- **CloudFormation service interruptions now have a focused diagnosis.** The
  catalog recognizes `ServiceNotAvailable` and `ServiceUnavailable` responses
  on stack operations, separates them from throttling, and points at a safe
  retry with a stable client request token.

- **EC2 Image Builder recipe collisions now have a focused diagnosis.** The
  catalog recognizes an `ImageRecipe` version that already exists, separates
  it from generic CloudFormation failures, and points at the read-only recipe
  check plus the new-version fix.

- **S3 lifecycle tag conflicts now have a focused diagnosis.** The catalog
  recognizes `AbortIncompleteMultipartUpload cannot be specified with Tags`,
  separates it from generic CloudFormation failures, and links to the safe
  split between an unfiltered abort rule and tag-based object rules.

- **Stable and branch-only CLI features are now labeled in onboarding.** The
  quickstart, README, homepage, and machine-readable site guide keep PyPI
  `0.11.0` focused on `diagnose` and show the explicit `main` install for the
  newer `run` and clipboard workflows until the next stable release. The
  homepage note uses the same dark-panel styling as the install commands.

- **The homepage coverage count now matches the catalog.** The public proof
  strip and error-guide link both show all 56 documented diagnostics.

- **The public one-step Action examples now point at a working ref.** The
  `run-command` input shipped after the current `v0` tag, so the homepage,
  quickstart, README, and integration guide use `@main` for that mode and say
  when to move back to the next stable tag. Existing log-only examples remain
  on `@v0`.

- **CodeBuild CodeConnections failures now identify the project-side access
  check.** A specific `AWSCodeBuild` `OAuthProviderException` no longer falls
  through to generic CloudFormation failure guidance; the report points at the
  CodeBuild service role, connection status, and IAM attachment ordering.

- **Unmatched failures now have a direct sharing path.** Terminal and Markdown
  reports show the sanitized `sam-doctor request-packet` follow-up, including
  stdin; the homepage and machine-readable site summary point to the same
  reviewed excerpt workflow.

- **Successful local deploys stay quiet.** The Bash, zsh, and PowerShell
  onboarding recipes retain the deployment log and original exit status, but
  run the advisory diagnosis only when the deploy exits non-zero.

- **Non-GitHub CI starters no longer mask deployment failures.** GitLab,
  CircleCI, Azure Pipelines, and Bitbucket examples capture the original Bash
  deploy status, diagnose only after a failed deploy, and return that status
  while keeping SAM Doctor advisory.

- **`sam-doctor run` provides a shell-independent deploy wrapper.** It streams
  and saves combined command output, diagnoses only after a non-zero command
  exit, and returns that original status even if advisory report writing fails.

- **Reports can be copied without leaving the terminal workflow.** `diagnose`
  and failed `run` commands accept `--copy`, using the host's native clipboard
  tools without adding a Python dependency; stdout remains unchanged for pipes
  and machine-readable formats.

- **The stable install path now has a one-shot example.** README, quickstart,
  and the machine-readable site guide show `uvx sam-doctor diagnose ...` for
  trying a diagnosis without installing a global CLI.

- **The GitHub Action can own the capture step.** Optional `run-command` mode
  runs the deployment through the existing safe wrapper, emits the same report,
  summary, and annotations, and returns the deployment's original status in the
  new `deploy-exit-status` output. Existing log-only and batch modes are unchanged.

- **Report outputs can no longer overwrite their source logs.** `diagnose` and
  `batch` reject literal, normalized-path, symlink, and hard-link aliases before
  writing, while packet commands also reject pre-existing hard-linked artifact
  targets that could modify files outside their output directory. Launch,
  distribution, and outreach maintenance commands preflight every active input
  and output for the same collisions before collecting data or changing files.

- **Release tags can no longer supply code to a write-capable workflow.** GitHub
  releases now start by manual dispatch from the current default-branch head,
  build reviewed tag history with read-only permissions, and transfer only
  fingerprinted distributions to the job that creates releases, dispatches
  PyPI, and advances `v0`.

- **PyPI recovery now publishes only immutable, prebuilt release assets.** A
  default-branch validator resolves strict stable tags, verifies the tagged project
  version, release state, GitHub asset IDs and SHA-256 digests, and embedded wheel and
  source metadata before environment approval. The OIDC job performs the same checks
  and re-downloads the same asset IDs after approval; it cannot check out an arbitrary
  ref or rebuild package contents.

- **Every public guide now carries a complete social sharing card.** Open Graph
  and Twitter metadata is generated from each page's canonical title and URL,
  uses the local branded preview image, and is checked for completeness and
  drift across all 58 indexable pages.

- **Packet outputs cannot overwrite the file being diagnosed.** Both packet
  commands reject literal, normalized-path, symlink, and hard-link aliases
  between a file input and any output target before the first artifact write.

- **Batch text reports redact sensitive source paths consistently.** Markdown
  section headings and terminal prefixes now apply the same secret filtering as
  their nested reports, preventing a credential-shaped filename from leaking
  through the outer wrapper.

- **Evidence packets reject colliding artifact filenames.** Markdown, JSON, and
  researcher notes must resolve to three distinct targets, so literal,
  normalized-path, and symlink aliases cannot silently overwrite earlier packet
  files.

- **Mobile brand links retain their accessible name at the narrow breakpoint.**
  The compact header still hides the long wordmark visually, but keeps “SAM
  Doctor” available to screen readers on all 58 pages; a shared CSS and markup
  regression test protects the behavior.

- **Repository workflows now pin every external GitHub Action to an immutable
  commit.** Readable version comments and Dependabot keep updates reviewable,
  while a static gate prevents a mutable tag or branch from returning to CI,
  Pages deployment, release creation, or trusted PyPI publishing.

- **Packet artifact filenames can no longer escape their output directory.**
  `packet` and `request-packet` reject traversal and absolute outside paths for
  every filename option before writing an artifact, while retaining nested
  filenames that resolve safely inside the selected directory.

- **Homepage FAQ structured data now mirrors the visible FAQ exactly.** A
  whitespace-normalized parity test keeps the ordered questions and answers in
  the JSON-LD block synchronized with what readers can actually see.

- **Three recently added diagnostics now honor their full acceptance
  boundaries.** The Lambda environment-key rule requires KMS-specific context,
  SSM precedence cannot erase a generic change-set finding on a truncated
  reason, and tag denials cover hyphenated AWS service prefixes plus
  `CreateTags`, `DeleteTags`, `AddTagsToResource`, and `RemoveTagsFromResource`.
  Their generic fallbacks remain visible for nearby non-matches.

- **Evidence-packet scenarios now receive the same secret redaction as their
  source and command fields.** A regression test puts a synthetic credential in
  `--scenario` and checks every generated packet file before it can be shared.

- **The sitemap now stays on the public site's own origin.** Search-engine entries
  cover the 58 published pages only, while repository and package destinations
  remain ordinary outbound links. Site QA rejects any future off-origin sitemap
  URL instead of silently accepting it.

- **The project site is now a focused, responsive product page.** The new layout
  puts the local diagnostic flow, real output shape, install path, supported
  failure families, CI example, and safety boundaries into one clear path. The
  same design system now keeps the quickstart and all 55 error guides readable
  on narrow screens, including long commands and exact AWS error strings.

- **Public site metadata now points to
  `https://sam-doctor.jacobgoldstein.dev/`.** Canonical links, social cards,
  structured data, sitemaps, share snippets, package metadata, documentation,
  and their deterministic checks all move together instead of splitting search
  and release metadata across two hostnames.

- **Generated share links now keep tracking data in the URL query and the page
  anchor in the fragment.** The generator URL-encodes campaign values, and a
  structural test verifies every generated link plus each referenced homepage
  anchor instead of preserving a malformed literal string.

- **Muted site copy now meets WCAG AA contrast on both paper backgrounds.** A
  token-level regression test protects the small supporting text shared across
  the homepage, quickstart, error index, and all 55 error guides.

- **Reports now serialize consistently across platforms.** Output files, packet
  artifacts, and redirected CLI output use UTF-8 with LF newlines instead of
  inheriting Windows newline translation. Batch input ordering now uses exact path
  spelling, and reported batch sources use `/` separators, rather than changing
  order and representation with the host path rules.

- **New: a high-confidence diagnostic for malformed `Fn::GetAtt` parameter
  lists.** CloudFormation's exact two-parameter rejection now points to the
  resource-and-attribute pair instead of returning no supported pattern. A
  same-line generic change-set wrapper yields to the specific finding without
  hiding a separate change-set failure elsewhere in the log.

- **The field-detection measurement no longer depends on GitHub search-result
  order.** Duplicate-prefix groups now choose a defined representative, groups
  have a stable order, and missed signatures with equal counts use the signature
  as a tie-breaker. Reversing the same API results now produces the same samples,
  detection count, and report.

- **The workflow `sam-doctor init` writes now grants the permission its deploy step
  needs, and pins current actions.** Two problems in the scaffold, both invisible to
  the tooling that would normally catch them.

  It declared no `permissions:` block, so an OIDC deploy failed before it started -
  without `id-token: write` the runner never sets `ACTIONS_ID_TOKEN_REQUEST_URL`.
  That is the most common failure in the real-log measurement, found in four
  unrelated repositories. Shipping a scaffold that walks into the very failure this
  tool is best known for diagnosing is a poor first experience. `contents: read` is
  restated alongside it, because naming permissions replaces the defaults rather
  than adding to them, and the generated file says so in a comment.

  It also pinned `actions/checkout@v4` and `setup-python@v5` after this repository
  had moved to v7. The template is a Python string, so dependabot cannot see it. A
  test now compares the versions in the template against the ones the repository's
  own workflows use, which means the dependabot pull request that bumps the
  workflows fails until the scaffold is updated with it.

- **Every pinned action is on its current major**, reviewed by diffing each action's
  own definition across the two versions rather than taken on trust: no input was
  removed and nothing became newly required in any of the six. The common thread is
  node20 reaching end of life on the runners.

- **Redaction was deleting the fix from the OIDC finding.** `token` sits in the
  secret-keyword list, so `permissions: id-token: write` was rewritten to
  `id-token=[REDACTED_SECRET]` - in the evidence line for the rule that fires most
  often on real logs. The finding therefore hid the single word a reader needs in
  order to fix the failure, and mangled the YAML separator into `=` while doing it.
  Configuration values (`write`, `read`, `none`, `true`, `false`, `admin`, `null`)
  are no longer treated as credentials, and the original separator is preserved, so
  a redacted line keeps the syntax somebody actually wrote.

  Found by reading the output of the new field measurement rather than by testing
  redaction: the tool printed `id-token=[REDACTED_SECRET]` in its own report.

- **New: `scripts/measure-field-detection.py`,** which measures the catalog against
  deployment logs pasted into public GitHub issues, and a monthly workflow that
  publishes the result. Detection sits at 88% of 249 real failure excerpts, and the
  missed signatures it prints are the closest thing this project has to a rule
  roadmap grounded in reality rather than in guesswork. Not part of the
  pull-request gate: it needs the network, and no contributor's build should depend
  on a search API.

- **The two flagship OIDC rules were matching wordings that real logs do not
  contain.** Measured against 231 real failure excerpts pasted into public GitHub
  issues, the catalog diagnosed 83%. Three of the misses were ours, not exotic:

  - `Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable` — what
    `@actions/core` actually prints when a job lacks `permissions: id-token:
    write`. Both existing patterns required the log to mention `id-token: write`,
    which is the *fix*, not the error: without the permission the runner never
    injects the variable, so the log cannot name it. Seen in four unrelated
    repositories.
  - `Not authorized to perform sts:AssumeRoleWithWebIdentity` — no colon after
    `perform`, which is how `configure-aws-credentials` words it, with "Not
    authorized" *before* the action name rather than after. All three patterns
    missed it. Seen in three unrelated repositories.
  - A bucket collision wrapped by a resource handler — `"my-app-logs already
    exists (Service: S3, …)" (HandlerErrorCode: AlreadyExists)`. The rule's own
    comment described this shape; the pattern was never added, so it produced no
    finding at all. `Service: S3` keeps it specific, since the handler code is
    shared by every resource type.

  Detection went from 83% to 88% on those three changes. The verbatim strings are
  now regression tests, alongside near-misses that must stay clean — another
  service's "already exists", an OIDC success line, and prose mentioning the
  permission.

- **Workflow annotations said ``write`..``** — the sentence period was appended
  unconditionally, and all 54 rules already end their first verification step with
  one. That is the surface most users see: for many people the annotation in the
  GitHub UI is the only sam-doctor output they ever read. It is now added only when
  the step does not already end a sentence, checked across every rule in the
  catalog.

  Found while confirming that hostile log content cannot break a workflow command —
  percent signs, `%0A`, `::stop-commands::`, carriage returns. It cannot: the
  annotation carries the rule's own explanation, first verification step and docs
  URL, never raw log text. The doubled period was sitting in the output being
  examined.

- **`docker login -p <token>` left a live registry credential in the report.**
  This one matters more than it first looks: `ecr.auth.login-failed` is a rule in
  this catalog, so a log containing a failed registry login is a log sam-doctor is
  built to be handed — and the `-p` form of that command carries the credential
  the login used. Also redacted now: the `.netrc` shape (`login <user> password
  <value>`, which uses whitespace instead of `=` and so was invisible to the
  assignment pattern), `curl -u user:token`, and Docker Hub `dckr_pat_` tokens.

  The patterns are deliberately narrow, because over-redaction has real costs
  here. `--password-stdin` is excluded: it is the *safe* idiom, names no secret,
  and starring it out would hide the fact that the log shows someone doing the
  right thing. A bare `-p` is never matched, or `mkdir -p /path` would lose its
  path. The `.netrc` pattern requires the `login <user>` prefix, or prose like
  "password is invalid" gets redacted. Eight near-miss lines of ordinary build
  output are pinned as must-not-change, including the ECR rule's own pattern line.

  Out of scope and left alone deliberately: Stripe, SendGrid and similar
  third-party API keys. They are recognizable by prefix, but they do not appear in
  AWS deployment logs, and every pattern added is a chance to redact something a
  reader needed.

- **Two credentials survived redaction: `Authorization: Basic` and incoming
  webhook URLs.** `Bearer` was handled and `Basic` was not, which is the wrong way
  round if either had to be missed — a Basic value is base64 of `user:password`,
  so it hands over a reusable credential rather than a token that expires. Docker,
  npm and pip registry auth all print that header, as does any verbose curl.
  Incoming webhook URLs (Slack, Discord, Teams) are credentials in link form:
  whoever holds one can post as the integration, and a deploy notification step
  prints the URL when its own post fails — which is exactly the log someone
  attaches to a bug report. Both are redacted now, and both are in the fuzz
  corpus, which was confirmed to fail without the fix.

  Ordering mattered more than the patterns. A Discord webhook path begins with a
  numeric id, so the twelve-digit account-id pass rewrote that id first, after
  which the URL no longer looked like a webhook: the harmless id was starred out
  and the token half — the actual secret — went into the report. The webhook pass
  runs first now, with a test naming the trap.

  Over-redaction was checked too, because it has its own cost: the ECR rule's own
  `no basic auth credentials` line and every documentation URL come through
  untouched.

- **An output directory that could not be created crashed instead of failing.**
  `packet`, `request-packet` and `init` called `mkdir` bare, while reads
  (`_read_text`) and writes (`_write_report`) both translate `OSError` into the
  message-plus-exit-2 path. So a read-only checkout, an output path that is
  already a file, or a full disk produced a Python traceback and exit `1` — the
  code reserved for a fail gate being hit, which a CI step branching on it reads
  as "this deployment has findings". All three now report
  `sam-doctor: error: Could not create <path>: ...` and exit `2`.

  Found by running the documented exit-code table against the real CLI. The other
  thirteen cases matched, including `--fail-on-confidence` taking precedence over
  `--fail-on-findings` in both `diagnose` and `batch`, and the empty-log path,
  which already explains itself rather than silently reporting nothing. Two
  behaviours the table did not mention are now written down: this one, and that
  `init` exits `2` rather than overwriting an existing workflow file.

- **The packet wrapper reported "findings found" when the path was wrong.**
  `scripts/export-evidence-packet.py` ran the CLI with `check=True`, so a missing
  log file — which the CLI correctly answers with exit 2 and a clear "Could not
  read" message — came out of the wrapper as a `CalledProcessError` traceback and
  exit 1. In this project's contract 1 means a fail gate was hit, so a workflow
  branching on the exit code read "your deployment has problems" from "your path
  is wrong", and the reader saw a crash in the tool instead of the tool's own
  message. The child's exit code now passes through unchanged. Empty stdin is
  likewise a message and exit 2 rather than a raised `ValueError`.

  A wrapper kept for compatibility has to preserve the contract it wraps, so both
  cases are now pinned by tests that fail against the old behaviour.

- **A `#` in a log filename sent the SARIF finding to the wrong place.**
  `artifactLocation.uri` is a URI reference rather than a path, and the log name
  was written into it unencoded. In a URI a `#` starts a fragment, so
  `logs/#build.log` reached a consumer as the path `logs/` — the finding
  attributed to the directory, the filename discarded. A space is not legal in a
  URI at all, and a strict consumer rejecting the document loses every finding in
  it rather than just the one. Both are percent-encoded now.

  The colon after a Windows drive letter is encoded too, which looks like
  over-encoding and is not: RFC 3986 forbids a colon in the first segment of a
  relative reference because it is ambiguous, and `C:/builds/deploy.log` really
  does parse with `C` as a scheme, dropping the drive from the path. Ordinary
  relative paths are untouched, so what code scanning matches against the
  repository is unchanged.

- **Coloured logs no longer lose findings.** The SAM CLI colours its own output,
  as do most build tools, so a log saved from a terminal or downloaded raw from a
  CI provider can read `ESC[31mFAILED ESC[0m` where a rule pattern expects
  `FAILED`. The escape sits inside the word, which is the worst place for it: the
  line reads normally to a human, the pattern quietly does not match, and the
  finding is simply absent - no error, no warning, just a shorter report.
  Colouring the words a CI provider actually colours dropped one of the two
  findings on the bundled CloudFormation sample. Escape sequences are now removed
  before anything tries to match, which also covers the whole-log suppression
  search and keeps evidence snippets free of escapes in JSON and SARIF output.

  Timestamp prefixes, CRLF, lone carriage returns from progress bars, indented
  output and non-breaking spaces were checked at the same time and needed no
  handling, since patterns are searched within a line. They are pinned by tests
  anyway, so a later change to normalization cannot break them either.

- **The weekly documentation-link check no longer cries wolf on one bad
  request.** It made a single attempt per URL and treated any failure as rot, so
  one timeout or one 503 from a documentation host would report a healthy link as
  broken. A maintenance signal that fires falsely gets ignored, and then it is
  worth nothing when it fires correctly. Transient answers - timeouts, DNS
  failures, 408, 425, 429, 5xx - now get one retry after a pause. A 404 is taken
  at its word and not retried, because the host already told the truth and asking
  twice only doubles the load on it.

  The checker had no tests at all, which is understandable: it needs the network
  and runs on a schedule outside the pull-request gate on purpose. But the
  *decision* about what counts as rot does not need the network, so that is now
  covered offline by stubbing the one function that fetches - including that a
  persistently failing host still reports, so the retry cannot swallow a real
  outage.

  Confirmed against the live hosts as well: all 38 unique links resolve,
  including the six added with this release's new rules.

- **A release tag that disagreed with the packaged version would have shipped
  silently.** Nothing compared the pushed tag to `pyproject.toml`. Tag `v0.12.0`
  while the package still said `0.11.0` and the chain fails without failing:
  `sync-site-metadata --check` passes because the site matches the *package*,
  the readiness check passes because pyproject and `__init__` agree with each
  other, `python -m build` produces `0.11.0` artifacts, `gh release create`
  attaches them to `v0.12.0` regardless, and the PyPI step - correctly using
  `skip-existing` so re-dispatching a recovery is a no-op - sees `0.11.0`
  already published and does nothing. The outcome is a GitHub release tagged for
  a version it does not contain, PyPI unchanged, and no error anywhere.

  `check-launch-readiness.py` takes a `--tag` now, and `release.yml` passes
  `github.ref_name`. The check is opt-in so the scheduled monitoring run, which
  has no tag, does not start failing. A tag with or without the `v` prefix is
  accepted; a mismatch exits 1 and stops the release before anything is
  published.

  Also audited every flag the workflows pass to a repo script against what that
  script declares - eight invocations, no drift. Worth checking because release
  and schedule workflows only run at release time, so a renamed flag there stays
  invisible until the moment it costs the most.

- **Froze what the shipped sample logs report.** `src/sam_doctor/data/*.txt` go
  inside the wheel: `sam-doctor demo` runs one, the README quotes them, and the
  Action's own CI asserts a finding count against
  `examples/oidc-assume-role-failure.txt` in both the Linux and Windows jobs. So
  their finding sets are published behaviour, not an implementation detail - but
  nothing pinned them.

  That matters because tightening a rule is meant to remove false positives
  without removing real detections, and the difference is invisible unless
  something checks. The baseline was captured by checking out v0.11.0 into a
  worktree and running *its* code against the same eight files: every finding
  set matched what the current build produces, so the several rules narrowed in
  this release cost no real detection. The expectations recorded now are what
  shipped, not what happened to be true afterwards.

- **Two rollout guides walked the reader into a gate that silently does
  nothing.** Both describe tightening CI in stages: observe, then
  `fail-on-confidence: high`, then strict `fail-on-findings: true`. Neither said
  to *remove* the threshold at the last step, and `team-rollout.md` showed both
  keys in one YAML block - so a team following it literally ends up with both
  set, where the threshold takes precedence and medium-confidence findings keep
  passing. They would believe strict mode was on when it was not.

  The behaviour is correct and deliberate, and already pinned by
  `test_threshold_overrides_fail_on_findings_when_both_are_given`. Only the
  guides were wrong: both now say to replace rather than add, and explain why.

  Found by extracting every `sam-doctor` invocation from the README and all
  fifteen docs and checking each against the real parser - 30 real commands,
  every flag valid, no rot there. The claims in `worked-examples.md` check out
  too: the OIDC example's stated finding, title, confidence and verification
  steps all match what the tool emits.

- **Two rules matched words instead of failures.** `Aborted!` was a pattern in
  its own right on the interactive-confirmation rule, so every interrupted tool
  in a job - docker, pip, terraform, anything stopped with Ctrl-C - was reported
  as a SAM interactive-changeset problem and told to set
  `--no-confirm-changeset`, which would not have helped any of them. The prompt
  itself is the signal, and SAM prints it directly above its own `Aborted!`, so
  the real case is unaffected; the bundled sample still reports. Primary patterns
  are matched per line, so the bare word could not be qualified by context and is
  simply gone.

  The CORS rule matched `(?:CORS|preflight).{0,80}(?:conflict|error|failed|
  duplicate|overlap)`. Across an eighty-character window, `error` and `failed`
  reach ordinary configuration output - "Configuring CORS ... - no errors"
  reported a preflight conflict. They are dropped; a real conflict says
  conflict, duplicate or overlap, or is caught by the two OPTIONS patterns.

  Both were found by ranking every rule pattern by how little literal text it
  requires and then testing the loosest against benign vocabulary. Most of what
  that surfaced was not a bug - `UPDATE_ROLLBACK_COMPLETE` firing is correct,
  because an update failed and rolled back - and there is now a test pinning
  that on purpose, so it is not "tightened" away later by someone reading it as
  a false positive.

- **A stack in `ROLLBACK_COMPLETE` reported the right answer and a distracting
  one.** CloudFormation returns "is in ROLLBACK_COMPLETE state and can not be
  updated" inside the `CreateChangeSet` ValidationError, on the same line as the
  generic wrapper - so the precise recreate-required finding arrived alongside
  the generic configuration finding, which tells the reader to run
  `sam validate --lint` and check `samconfig.toml` for a stack that simply has
  to be deleted first. The `*_IN_PROGRESS` form of the same sentence was already
  suppressed; the ROLLBACK_COMPLETE form was not. It is now, matching its
  sibling.

  Found by a new whole-log test file. Every other test hands a rule the single
  line it was written for, but real output wraps the status reason inside a
  ValidationError, prints several failed resources for one stack, and threads
  progress lines through all of it - and precedence between rules only matters
  in that shape. Eight realistic logs now assert the whole finding *set*,
  including a clean deployment that must report nothing, a stack that fails
  three resources at once and must report all three, and an unrecognised failure
  reason that must name the failed resource without inventing a cause for it.

- **Determinism is now checked across processes, not just within one.** The
  README promises identical output for identical input, and the existing tests
  render twice in the same process - where dict and set iteration order is
  stable by construction, so a hash-order dependence could never show up. The
  same input now runs through separate processes under different
  `PYTHONHASHSEED` values, for every output format, and under different locales
  including `tr_TR.UTF-8`, whose dotless-i breaks naive case folding and every
  rule matches case-insensitively. Working-directory independence is asserted
  too. All of it already held; none of it was covered.

  `packet` timestamps are also asserted to carry `+00:00` whatever the local
  zone. A local-time timestamp in an artifact meant for sharing leaks the
  reporter's timezone and makes two packets hard to order against each other.

- **The stability promise now checks itself.** `docs/stability.md` names the
  subcommands covered by the CLI-surface guarantee, and the list had drifted:
  `request-packet` has shipped for a while and was not in it, so a reader could
  not tell whether it was covered. It is listed now, and a test compares that
  clause against the subcommands the parser actually registers, so a new one
  cannot ship without someone deciding whether it belongs under the promise.

  The same file promises that rule ids never change, because integrations are
  told to match on `rule_id` rather than the title - but nothing compared the
  catalog against the ids that had actually been released. A frozen baseline of
  the 48 ids shipped in v0.11.0 is now asserted to still exist, so removing or
  renaming one fails the suite instead of quietly breaking someone's pipeline.
  Adding rules needs no maintenance; only a release appends to the baseline.
  A third test guards the guard, since an empty baseline would pass vacuously.
  Verified against v0.11.0: 48 ids then, 54 now, none removed or renamed.

- **`init` wrote a GitHub expression that GitHub would not have interpolated.**
  The generated workflow ends with a commented-out follow-up step for the user
  to uncomment, and its `echo` referenced
  `${ steps.sam-doctor.outputs.finding-count }` with single braces. GitHub needs
  `${{ ... }}`; with one brace it prints the literal text. The template source
  had it right - the workflow is rendered with `str.format()`, which collapses
  `{{` to `{`, so the correct-looking source emitted the broken output. The
  braces are quadrupled now, with a note saying why, and a test that fails on
  any single-brace expression in either trigger mode.

- **The shareable artifacts name the log file, not the path it came from.**
  `request-packet` writes an excerpt specifically to be pasted into a public
  rule request, and `packet` writes notes whose own text says to discuss the
  case using those files - and both recorded the full working path, twice, in
  the `Source` and `Command` lines. Source names are redacted, but only for the
  identifier patterns: an ARN, an account id, an email. A path is none of those,
  so it passed through whole.

  CONTRIBUTING asks contributors never to post private repository names, and a
  working path usually contains exactly that - `.../acme-private-client/infra/
  deployment.log` - along with the OS user name from the home directory. The
  file name is the part with diagnostic meaning; the directories above it are
  not the maintainer's business. Both now record the name alone.

- **Read logs that carry a byte-order mark.** Every input was decoded as UTF-8,
  so a UTF-16 log produced no findings at all - each character separated by a
  NUL, nothing matching, and a report saying "no supported pattern found" for a
  log full of failures. That is not a rare shape on the platform this project
  supports: PowerShell writes redirected output as BOM-marked Unicode, so
  `sam deploy > deploy.log` under PowerShell 5.1 hands the tool UTF-16 LE. A
  BOM is now honoured for UTF-8, UTF-16 and UTF-32 in both byte orders, with
  UTF-32 tested before UTF-16 because its little-endian mark begins with the
  UTF-16 one. Anything unmarked is still UTF-8 with replacement, which keeps a
  latin-1 log readable rather than raising. UTF-8-with-BOM previously worked
  only by luck - the mark decoded to a stray character and the unanchored
  pattern matched past it - and is now decoded properly, so the mark no longer
  appears in evidence. Line numbers are asserted to survive decoding, and CRLF
  input is covered too.

- **Stopped diagnosing four different Docker failures as the same one.** The
  Docker rule matched the bare phrase `Error response from daemon`, so a pull
  denial, a missing tag, a full disk and a platform mismatch all reported "SAM
  build requires Docker for containerized builds" - and were all told to check
  `docker version`, inspect `docker.sock` permissions, and consider disabling
  container builds. That advice is wrong for every one of them.

  The phrase is evidence of the opposite of what it was being read as: a
  response *from* the daemon means the daemon is running and answered. It no
  longer matches, and two rules now claim the cases worth naming - a registry
  refusing or lacking the image (`pull access denied`, `manifest unknown`), and
  a build host with no disk left (`no space left on device`, `ENOSPC`). The
  registry rule also notes that an arm64-only image requested for an x86_64
  build reports as a *missing manifest*, which reads like a typo and is not one.

  The platform-mismatch case is deliberately left unmatched rather than folded
  into a neighbouring rule. An unmatched log says "no supported pattern found"
  and offers the rule-request link, which costs the reader less than a confident
  wrong answer - the whole problem being fixed here.

- **Fixed a false positive that also hid the real failure.** Running the tool
  over a completely successful build-and-deploy log produced a high-confidence
  "SAM Python dependency resolution failed" finding. The rule matched the bare
  token `PythonPipBuilder:ResolveDependencies`, and SAM prints
  `Running PythonPipBuilder:ResolveDependencies` as ordinary progress on every
  successful Python build - so the finding fired for any project that builds
  with pip, which is the default Python path.

  The second half is worse. That same bare token was a whole-log
  `suppressed_by` pattern on the change-set rule, so merely *having built* with
  pip switched that rule off: a successful build followed by a genuine
  `Failed to create changeset` reported the Python failure that had not happened
  and stayed silent about the one that had. Both now require the failure
  continuation (`... ResolveDependencies - {...}`), which is the form SAM only
  prints when the stage actually fails.

  Two things were added so this class cannot come back. The build-stage progress
  lines are now in the catalog gate's benign-log corpus - every builder stage
  prints `Running <stage>` on success, and only `CopySource` was listed, which
  is why this slipped through. And the gate now checks `suppressed_by` patterns
  against those benign lines too, not just primary patterns: a suppression
  pattern matching a benign line is the more dangerous of the two, because it
  removes a real finding silently instead of adding a visible wrong one. The
  rule-interaction guard could not have caught this - it pairs fixtures with
  fixtures, so it never puts a benign line next to a failure.

- **Fixed two redaction gaps that leaked live credentials.** Both were found by
  probing the layer with realistic CI lines rather than by a rule change, and
  both defeated the one promise this tool has to keep.

  First: the secret-assignment pattern required a word boundary before the
  keyword, and `_` is a word character - so `\bpassword` never matched inside
  `DB_PASSWORD`. `password=hunter2` was redacted and `DB_PASSWORD=hunter2` was
  not. Environment variables are conventionally UPPER_SNAKE_CASE with a prefix,
  so the spelling that leaked was the *common* one, and Lambda environment
  variables are squarely in this tool's subject matter. The boundary is gone;
  the `[:=]` that follows the keyword is what makes the pattern specific, and
  `tokenizer=fast` still does not match. Hyphenated spellings (`x-api-key`) and
  `passwd` are covered too.

  Second: credentials in a URL - `https://user:token@host/path` - were only
  redacted by accident, when the *email* pattern happened to match
  `password@host.tld`. That pattern needs a dot in the host, so an internal
  single-label host leaked the credential in full:
  `git clone https://oauth2:glpat-...@gitlab/team/repo.git` passed through
  untouched, and that is an ordinary line in a CI log. When it did match, the
  value was labelled `[REDACTED_EMAIL]`, which hides what actually leaked.
  There is now a dedicated pattern, running before the email pass, that keeps a
  placeholder username like `oauth2` (it identifies which credential failed)
  and redacts the secret half as `[REDACTED_URL_CREDENTIAL]`. The
  token-as-username form, `https://glpat-...@host`, redacts the username
  instead, because there the single value *is* the credential.

- Added a rule for an SSM dynamic reference that cannot be resolved
  (`Parameters: [ssm:/path] cannot be found`, `SSM parameter ... not found`),
  which previously landed on the generic configuration finding and got generic
  advice. The thing worth saying about this failure is *when* resolution
  happens: at change-set time, in the target account and Region, as the
  deploying identity - so a parameter you can read from your own terminal
  proves nothing about the account being deployed to, and checking it with the
  wrong profile is the usual way this investigation goes quiet. The rule names
  the four causes that account for nearly all of them (a stage baked into the
  path, an environment nobody seeded, the wrong Region, and `ssm-secure` that
  is readable but not decryptable) and gives the lookup with the Region and
  `--with-decryption` flags that actually reproduce it. The generic rule
  suppresses for the whole log here rather than per line, matching the existing
  choice for the other change-set reasons: CloudFormation prints the wrapper on
  a separate line from the reason, so excluding one line would report the same
  failure twice.

- Added a rule for a Lambda function that cannot use its environment-variable
  KMS key. AWS wraps this one badly: the outer error is a Lambda
  `InvalidParameterValueException`, which reads like a bad template value, and
  the actual cause is the `KMS Exception:` buried inside the status reason.
  Worse, when that inner exception is `AccessDeniedException` the log matched
  the generic denial rule, so the report pointed at the IAM policy simulator
  when the thing to review is the key's own resource policy - a wrong answer is
  more expensive than no answer here. The rule now reads the inner exception
  name and splits the three causes that look identical in the wrapper: a key
  policy that will not grant `kms:CreateGrant`, a key that is disabled or
  pending deletion (where no policy change helps), and an ARN that is malformed
  or names another Region. `KMS Exception:` is excluded per line from the
  generic denial and the generic resource-failure rules, so a second failed
  resource in the same stack still reports.

- Added two rules for tag failures, which previously fell through to the
  generic denial finding or produced nothing at all. A tag-on-create denial is
  the more confusing of the two: the error names the operation that was called
  (`CreateRole`) and, separately, the action that was denied (`iam:TagRole`),
  and the fix is on the second one. A deploy policy granted `iam:CreateRole`
  without `iam:TagRole` fails the whole create, because CloudFormation applies
  tags in the same call - so reading the old finding as "I need more create
  permissions" sent you looking in the wrong place. The rule names the tagging
  action and says to grant it alongside the create action it belongs with.
  Where an Organizations tag policy or a CloudFormation hook rejected the tag
  set instead, it says to find the layer that enforced it, and deliberately
  does not suggest removing the control to get a green deploy.

- The second rule covers a tag key or value rejected by validation, which is a
  template problem wearing a permission problem's clothes - most often the
  reserved `aws:` prefix, which no policy can grant the ability to write, or a
  value interpolated from a branch name or commit subject that breaks the
  allowed character set. It points at the index in `tags.N.member.key`, since
  that names which tag of the set failed and beats re-reading the template.

- The three IAM denial rules exclude tag-action denials per line rather than
  suppressing themselves for the whole log. A deployment that fails on a tag
  usually fails other things too, and whole-log suppression would have dropped
  those other denials from the report - so a non-tag `AccessDenied` sharing the
  log still produces its own finding, with a regression test that fails if that
  stops being true.

## v0.11.0 - 2026-08-08

- Added a rule-interaction guard. Every rule's fixture is paired with every
  other rule's and the suite checks which findings disappear, against a list
  of the suppressions that are intended. The nine-rule hiding bug fixed above
  passed every individual rule's tests, so nothing caught it; this does, with
  a message that names the two mechanisms and when each is right.

- A specific failure no longer hides the stack's other failed resources. Nine
  status reasons - a taken or invalid bucket name, the code storage quota, a
  stabilization timeout, an in-use export, reserved concurrency, a nested
  stack, an API with no methods, a prohibited trust-policy field - suppressed
  the generic resource-failure rule for the whole log, so a stack that failed
  one of those *and* an unrelated resource reported only the first. Stacks
  rarely fail exactly one resource, so the rest of the report simply vanished.
  Those now exclude their own line instead. Three reasons still suppress the
  whole rule because CloudFormation prints them on a separate line from the
  event they explain, where excluding the reason line would report the same
  failure twice; that trade-off is now written down next to the code.

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
