# SAM Doctor

[![Verify free core](https://github.com/jakegold1647/sam-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/jakegold1647/sam-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![GitHub Marketplace](https://img.shields.io/badge/GitHub%20Marketplace-Available-blue?logo=github)](https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics)
[![PyPI](https://img.shields.io/pypi/v/sam-doctor.svg)](https://pypi.org/project/sam-doctor/)
[![GitHub stars](https://img.shields.io/github/stars/jakegold1647/sam-doctor?style=social)](https://github.com/jakegold1647/sam-doctor/stargazers)
[![GitHub release](https://img.shields.io/github/v/release/jakegold1647/sam-doctor?include_prereleases&label=release)](https://github.com/jakegold1647/sam-doctor/releases)

SAM Doctor reads a failed `sam deploy`, `cdk deploy`, or
`aws cloudformation deploy` log locally and reports the first supported failure
pattern it finds: a short diagnosis, redacted evidence lines, safe verification
commands, and a link to the relevant official documentation.

It does **not** access AWS, upload logs, change resources, or claim an
authoritative root cause. It matches known patterns in text you provide. When
nothing matches, it says so instead of guessing.

[Project page](https://sam-doctor.jacobgoldstein.dev/) |
[GitHub Marketplace](https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics) |
[Report a bad diagnosis](https://github.com/jakegold1647/sam-doctor/issues/new?template=bug_report.yml) |
[Request a rule](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)

## Try it

```bash
python -m pip install sam-doctor
sam-doctor demo
```

The bundled demo needs no AWS credentials and makes no network calls. Other
install paths:

```bash
pipx install sam-doctor      # isolated global CLI
uvx sam-doctor demo          # run without installing
```

For a one-off diagnosis without changing the environment, run the stable
package directly through `uvx`:

```bash
uvx sam-doctor diagnose deployment.log --format markdown
```

The current branch also contains the shell-independent `run` wrapper and the
native clipboard handoff. Until those features land in the next stable PyPI
release, try them explicitly from `main`:

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@main"
```

The public guides follow the current `main` catalog (86 diagnostics). Stable
PyPI `0.11.0` contains the released 48-rule catalog, so use the explicit
`main` install above when you need newer rule coverage as well as `run` or
clipboard support.

To install from a tagged source release instead of PyPI, use
`pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@<tag>"`
with a tag from the [releases page](https://github.com/jakegold1647/sam-doctor/releases).
If your shell cannot find `sam-doctor` after installing, use
`python -m sam_doctor` instead.

![SAM Doctor turns a failed deployment log into a concise diagnosis](docs/assets/sam-doctor-demo.svg)

The demo diagnoses a bundled GitHub Actions OIDC failure:

```text
SAM Doctor found 1 possible issue(s) in oidc-assume-role-failure.txt.

1. GitHub Actions cannot assume the configured AWS role through OIDC (high confidence)
   Matched on line: 2
   The workflow reached AWS STS but the role trust relationship did not accept
   the GitHub-issued OIDC token. ...
   Evidence:
   - Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity
   - An error occurred (AccessDenied) when calling the AssumeRoleWithWebIdentity
     operation: Not authorized to perform sts:AssumeRoleWithWebIdentity
   Verify:
   - Confirm the workflow or job permissions include `id-token: write`.
   - Check that the role trust policy accepts `token.actions.githubusercontent.com:aud`
     equal to `sts.amazonaws.com`.
   Docs: https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
```

The description line is truncated here; the CLI prints it in full, along with a
third trust-policy `sub` check. Output is deterministic for the same input, and
evidence is redacted before display.

## Who this is for

Use it as a fast local first pass when a SAM, CloudFormation, or GitHub Actions
deployment fails and the useful error line is buried under rollback noise. It
works best on logs with explicit error lines and rollback context.

Lambda invoke smoke tests are supported too: a missing function, alias, or
published version is reported with a read-only target check instead of an IAM
guess.

Skip it if you need account-state inspection, drift analysis, quota checks, or
automatic fixes. See [When not to use this](#when-not-to-use-this).

## Usage

Diagnose a log file:

```bash
sam-doctor diagnose deployment.log
```

Pick the output format for where the report is going:

| Situation | Command |
| --- | --- |
| Handoff in a ticket or thread | `sam-doctor diagnose deployment.log --format markdown` |
| Machine-readable output for CI | `sam-doctor diagnose deployment.log --format json --output diagnosis.json` |
| GitHub workflow annotations | `sam-doctor diagnose deployment.log --format github` |
| Code scanning / SARIF consumers | `sam-doctor diagnose deployment.log --format sarif --output sam-doctor.sarif` |
| Share a reviewed report from the clipboard | `sam-doctor diagnose deployment.log --format markdown --copy` |
| Pasted excerpt, no file | `printf '%s\n' "...error excerpt..." \| sam-doctor diagnose -` |
| A workflow that saves a log | The [GitHub Action](#github-actions) below |

All formats include the first matching line number and the matched evidence,
not the full input log. Diagnosis time scales with log size - every line is
checked against the whole rule catalog, roughly a second per megabyte - so
very large logs take a while, and the CLI says so on stderr past about 25 MB.
Trimming a log to the failing section is faster and finds the same thing. Standard input works anywhere a file path does, so you
can pipe from other tools:

```bash
kubectl logs deploy/my-api | sam-doctor diagnose -
```

If the useful lines are already in your clipboard, send them straight to the
same local command:

```powershell
# PowerShell on Windows
Get-Clipboard | sam-doctor diagnose - --format markdown
```

```bash
# macOS, Wayland Linux, or X11 Linux
pbpaste | sam-doctor diagnose - --format markdown
wl-paste | sam-doctor diagnose - --format markdown
xclip -selection clipboard -o | sam-doctor diagnose - --format markdown
```

Review the excerpt before sharing it. SAM Doctor redacts common identifiers,
but clipboard contents can still include sensitive text that needs your review.
When you use `--copy`, the report is sent to the host's native clipboard
(`clip.exe`, `pbcopy`, `wl-copy`, `xclip`, or `xsel`) without adding a Python
clipboard dependency. Standard output stays unchanged, so the same command is
safe to use in a script.

To make diagnosis part of every local deploy, capture the deploy output and
keep the deploy command's exit status:

```bash
# Bash / zsh
set -o pipefail
sam deploy --no-confirm-changeset 2>&1 | tee deployment.log
deploy_status=${PIPESTATUS[0]}
if [ "$deploy_status" -ne 0 ]; then
  sam-doctor diagnose deployment.log --format markdown
fi
exit "$deploy_status"
```

```powershell
# PowerShell
sam deploy --no-confirm-changeset 2>&1 | Tee-Object deployment.log
$deployStatus = $LASTEXITCODE
if ($deployStatus -ne 0) {
  sam-doctor diagnose deployment.log --format markdown
}
exit $deployStatus
```

If you prefer one command without shell-specific `tee` or `PIPESTATUS` glue,
let SAM Doctor wrap the deploy directly:

```bash
sam-doctor run --log-file deployment.log --format markdown -- \
  sam deploy --no-confirm-changeset
```

It streams the deploy output, keeps the combined log, diagnoses only when the
deploy exits non-zero, and returns the deploy's original exit status. Add
`--output diagnosis.json --format json` when another tool should consume the
failure report, or `--copy --format markdown` when you want to review and paste
the failure report from your clipboard.

The diagnosis stays advisory in these examples; the deploy still owns the
process exit code. Add an explicit confidence or findings gate only when your
team is ready to enforce it.

### Multiple findings

When several supported patterns appear, findings are ordered by their first
matching log line, which puts the root failure before the rollback it caused.
`sam-doctor demo --scenario cloudformation` reproduces this shape:

```text
SAM Doctor found 2 possible issue(s) in cloudformation-resource-failure.txt.

1. CloudFormation resource creation or update failed (high confidence)
   Matched on line: 1
   Evidence:
   - ... MyApiDeployment CREATE_FAILED Resource handler returned message: "Invalid
     request provided: API Gateway deployment cannot be created because the stage
     already exists." ...
   Verify:
   - Identify the failed logical resource ID and preserve its exact status reason.
   - Check the underlying service event or API error named in that status reason.
   - Fix the resource-level cause before retrying the stack operation.

2. CloudFormation stack entered rollback after an earlier resource failure (medium confidence)
   Matched on line: 2
   Verify:
   - Inspect stack events in chronological order and locate the first
     `CREATE_FAILED` or `UPDATE_FAILED` resource.
```

Other bundled scenarios: `sam-doctor demo --scenario capabilities`,
`api-gateway`, `esbuild`, `python-pip`.

### Batch mode

Diagnose many logs in one run:

```bash
sam-doctor batch logs/*.log logs/*.txt --format json --output batch-results.json
```

Add `--fail-on-findings` to exit `1` when any file has a supported finding,
or `--fail-on-confidence high` to gate only on findings the rules are sure
about; the full batch report is still written first either way. With
`--format github`, batch mode emits one annotation per finding and skips
successful inputs.

### Exit codes

| Status | Meaning |
| --- | --- |
| `0` | Command completed with no enforced fail gate hit. |
| `1` | `--fail-on-findings` found a supported finding, or a finding met the `--fail-on-confidence` threshold (`diagnose` or `batch`). |
| `2` | CLI usage or error-path failure (missing inputs, invalid arguments). |

Details and examples: [docs/cli-exit-and-action-exit-codes.md](docs/cli-exit-and-action-exit-codes.md).

### JSON schemas

The JSON payload shapes are documented in checked-in schemas:

- `docs/schemas/diagnose-report.schema.json`
- `docs/schemas/batch-report.schema.json`
- `docs/schemas/rules-report.schema.json`
- `docs/schemas/sarif-report.schema.json` (the narrowed contract for `--format sarif`)

`sam-doctor schemas` prints the schema URLs. The contracts are
additive-compatible: new top-level fields may appear, but removing or renaming
a documented required field is a breaking change and gets a coordinated
version bump.

## GitHub Actions

Add a diagnostics step after any step that saves a deployment log:

```yaml
- name: Deploy
  shell: bash
  run: |
    set -o pipefail
    sam deploy --no-confirm-changeset 2>&1 | tee deployment.log

- name: Diagnose deployment log
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
    # Uncomment to fail this job when a supported finding is detected.
    # fail-on-findings: true
```

Keep `if: always()`; otherwise GitHub Actions skips the step exactly when the
deployment fails. The Markdown job summary is opt-in and contains only matched,
redacted evidence. The action also adds redacted workflow annotations for each
finding by default; set `annotations: "false"` to disable them.

For a single-step CI integration, let the Action run and capture the deploy:

```yaml
- name: Deploy and diagnose
  id: sam-doctor
  uses: jakegold1647/sam-doctor@main
  with:
    log-file: deployment.log
    run-command: sam deploy --no-confirm-changeset
    summary: true
```

It preserves the deployment's original exit status and exposes it as
`deploy-exit-status`; keep authentication and environment setup in earlier
steps. Use either `run-command` or `batch`, not both. This example uses
`@main` because the current stable `v0` tag predates `run-command`; switch to
the next stable tag when it includes this input. The log-only examples below
remain on `@v0`.

`sam-doctor init` generates this workflow for you:

```bash
sam-doctor init --deploy-command "sam deploy --no-confirm-changeset" --summary --annotations
```

By default the generated workflow only runs on `workflow_dispatch` (the
"Run workflow" button in the Actions tab), so an `init` you ran to try
things out can't quietly turn into a deployment on your next push. Add
`--on-push` when you're ready for the workflow to deploy automatically on
pushes to `main`:

```bash
sam-doctor init --deploy-command "sam deploy --no-confirm-changeset" --on-push --summary --annotations
```

A rollout pattern that works: run non-blocking for 3-5 stable runs, then add
`--fail-on-findings --force` to regenerate with strict gating. If you would
rather not regenerate per mode, the
[two-phase starter workflow](examples/github-actions-workflow-two-phase-gating.yml)
stays non-blocking by default and enforces only on a manual
`workflow_dispatch` with `rollout-mode: strict`.

### Action exit codes and outputs

- `0`: no enforced failure (findings may still exist).
- `1`: findings present and `fail-on-findings: true`.
- `2`: runtime or precondition failure (invalid boolean inputs, missing Python).

The action exposes `finding-count`, `has-findings`, and `deploy-exit-status`
outputs for routing:

```yaml
- name: Route to dedicated triage when action reports findings
  if: steps.sam-doctor.outputs.has-findings == 'true'
  run: |
    echo "Routing failure with ${{ steps.sam-doctor.outputs.finding-count }} findings to a higher-signal runbook."
```

### Action batch mode

For CI setups that write many logs per run, set `batch: true` and point
`log-file` at a directory or glob:

```yaml
- name: Diagnose logs in batch
  if: always()
  id: sam-doctor-batch
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: logs/
    batch: true
    summary: true
```

### Starter workflows

Pick the template that matches your deploy command:

- SAM deploy: [`examples/github-actions-workflow.yml`](examples/github-actions-workflow.yml)
- SAM sync: [`examples/github-actions-workflow-sam-sync.yml`](examples/github-actions-workflow-sam-sync.yml)
- CloudFormation package/deploy: [`examples/github-actions-workflow-cf-pipeline.yml`](examples/github-actions-workflow-cf-pipeline.yml)
- CDK deploy: [`examples/github-actions-workflow-cdk.yml`](examples/github-actions-workflow-cdk.yml)
- Batched logs in one run: [`examples/github-actions-workflow-batch-logs.yml`](examples/github-actions-workflow-batch-logs.yml)

The [CI command matrix](docs/ci-command-matrix.md) maps exact deploy commands
to templates, and [`examples/README.md`](examples/README.md) indexes everything.

### Other CI systems

- GitLab: [`examples/gitlab-ci-sam-doctor.yml`](examples/gitlab-ci-sam-doctor.yml)
- CircleCI: [`examples/circleci-sam-doctor.yml`](examples/circleci-sam-doctor.yml)
- Azure Pipelines: [`examples/azure-pipelines-sam-doctor.yml`](examples/azure-pipelines-sam-doctor.yml)
- Bitbucket Pipelines: [`examples/bitbucket-pipelines-sam-doctor.yml`](examples/bitbucket-pipelines-sam-doctor.yml)

## What it detects

Run `sam-doctor rules` (or `rules --format json`) for the current
machine-readable catalog. Each rule triggers on an explicit error signal in the
log, not on template inspection or AWS account access, and carries a stable id
(`iam.deny.explicit`, and so on) that CI tooling can match on across releases -
see [docs/stability.md](docs/stability.md). The current set:

- GitHub Actions OIDC errors: missing `id-token: write`, audience mismatch,
  trust-policy/subject mismatch, and `AssumeRoleWithWebIdentity` failures
- IAM `AccessDenied` failures, with explicit denies (including service control
  policies) distinguished from missing-policy denials
- Expired AWS credentials and runner clock skew (`ExpiredToken`, `Signature expired`)
- CloudFormation API throttling (`Rate exceeded`)
- CloudFormation service interruptions and deploy-wrapper handoffs that need
  stack-event evidence (`ServiceNotAvailable`, `Failed to create/update the stack`)
- CloudFormation failed-resource events and rollback states
- Another operation already in progress on the stack
  (`OperationInProgressException`, `*_IN_PROGRESS state and can not be updated`)
- Empty change sets (`No changes to deploy` in CI)
- Resources that fail to stabilize, with the nested handler message surfaced first
- Exports that cannot change because another stack imports them
- Lambda deployment packages over a per-function size limit, and the regional
  code storage quota (`CodeStorageExceededException`)
- Lambda invoke target misses (`ResourceNotFoundException` on the `Invoke`
  operation), with function, qualifier, account, Region, and timing checks
- Amazon Bedrock first-use access, unresolved model-identifier, empty Converse
  system-prompt, empty `InvokeModel` `modelId`, missing Claude Messages API
  `messages`, and indexed nested content-field failures, with account, Region,
  model catalog, endpoint, API, and request-shape checks
- AWS `UnknownAction` and `InvalidAction` handoffs that keep endpoint and API
  compatibility failures separate from IAM denials
- AWS `NotImplemented` operation handoffs that keep endpoint and emulator
  compatibility failures separate from IAM denials
- AWS `UnknownService` operation handoffs that keep service-target and protocol
  routing failures separate from IAM denials
- STS caller-identity wrapper failures that keep nested endpoint, Region,
  signing, network, and credential-source causes separate from IAM denials
- AWS Glue catalog database rename failures that point to stable-name updates
  or a replacement database instead of IAM changes
- Cloud Control API operation wrappers that point to the nested ProgressEvent
  and request token before retrying or changing IAM
- EC2 `CreateNetworkInterface` provider wrappers that preserve the nested
  status, subnet capacity, permission, request-shape, and endpoint checks
- EKS Amazon VPC CNI pod-sandbox failures that point at the nested `aws-node`
  or `ipamd` error before changing workloads
- EKS VPC CNI network-policy-agent failures that point at the node agent,
  CNI prerequisites, node kernel, and `PolicyEndpoint` evidence before changing
  workloads or IAM
- Kubernetes pod-sandbox network setup wrappers that preserve the named CNI
  plugin and node-level evidence before changing the workload or IAM
- API Gateway enhanced security-policy failures that point at the missing
  `EndpointAccessMode` property before changing IAM
- ECS Exec managed-agent failures (`CannotStartManagedAgentError` and the
  `ExecuteCommand` wrapper), with task-state and SSM prerequisite checks
- Blocked stack deletion: `DELETE_FAILED` blockers and termination protection
- ECR push authentication failures from the CI runner (missing login, expired
  token, denied `ecr:GetAuthorizationToken`)
- CloudFormation capability acknowledgement errors (`InsufficientCapabilities`)
- Lambda container-image failures caused by missing ECR image access
- Lambda VPC execution-role failures caused by missing elastic network-interface permissions
- CodeBuild CodeConnections access failures (`OAuthProviderException`) surfaced
  during a CloudFormation deployment
- EC2 Image Builder recipe-version collisions that require a new immutable version
- API Gateway deployments created before methods exist
- API Gateway CORS preflight conflicts
- SAM deployment/configuration errors, including conflicting artifact-bucket
  settings and missing `esbuild` dependencies
- SAM build errors where Docker is unavailable for `sam build --use-container`
- SAM build output permission failures under `.aws-sam/build`, kept separate
  from Docker availability and AWS IAM errors
- Python dependency resolution or validation errors in SAM/Python builds
- Interactive changeset prompts that stall non-interactive CI
- Template failures: SAM/CloudFormation schema validation
  (`InvalidSamDocumentException`, unsupported properties), invalid properties
  for a resource type, malformed `Fn::GetAtt` resource/attribute pairs,
  unresolved resource dependencies, and templates over a CloudFormation size or
  count quota
- S3 naming failures: invalid bucket names and globally taken names
  (`BucketAlreadyExists`, `BucketAlreadyOwnedByYou`)
- S3 lifecycle conflicts where tag filters cannot be combined with multipart-abort
  actions
- AWS CDK synthesis and asset-bundling handoffs (`AssemblyError: Assembly builder
  failed`, `Failed to bundle asset`) that point at a reproducible
  `cdk synth --verbose` check without inventing the app error
- Bedrock model-lifecycle failures where a requested model version reached
  end of life, pointing at an active replacement instead of IAM changes
- Artifact-path failures: a `CodeUri` that was never built, a deployment
  bucket that denies access to the packaged artifacts, and Lambda layer
  artifacts CloudFormation cannot read back
- IAM trust-policy shape errors and Lambda code-signing conflicts

Every rule also has a human-written reference page on the
[deployment error index](https://sam-doctor.jacobgoldstein.dev/errors/) -
what the exact error string means, the fix, and read-only verification
commands.

If a deployment error you hit is not covered, open a
[rule request](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)
with a sanitized 5-15 line excerpt and the command you ran.
`sam-doctor request-packet deployment.log` writes that excerpt for you: a
redacted context window around the first likely error, never the full log.

## What a report includes

1. A likely failure category and confidence level.
2. Up to three matched log lines, redacted before output.
3. Safe checks to validate the diagnosis before changing a policy or stack.
4. A link to the relevant official documentation.

Reports redact AWS account IDs, ARNs, email addresses, common AWS access key
IDs, bare STS session tokens, secret assignments (including the CamelCase
JSON keys STS output prints), presigned-URL signatures, bearer tokens,
`Authorization: Basic` values, JWT-style tokens, PEM private-key blocks,
credentials embedded in URLs, incoming webhook URLs (Slack, Discord, Teams),
passwords passed on a login command line or in `.netrc` form, and common
GitHub, Slack and Docker Hub token formats before matched evidence is shown.
This is a guardrail, not a secret scanner: review a report before sharing it.

The list stays narrow on purpose. `--password-stdin` is left visible because it
is the safe idiom and starring it out would obscure a log showing the right thing
being done, and third-party API keys that never appear in AWS deployment logs are
left out — every pattern added is another chance to redact something the reader
needed.

To package a diagnosis for handoff, `sam-doctor packet deployment.log` writes
`diagnosis.md` and `diagnosis.json`; the
[evidence packet template](docs/researcher-evidence-packet.md) describes what
to share alongside them, and [RESEARCHER_OVERVIEW.md](RESEARCHER_OVERVIEW.md)
is the summary to hand a reviewer or researcher.

## How it compares

- **vs. reading the log yourself.** For a failure you have seen before, just
  read the log. SAM Doctor helps when the useful line is buried under rollback
  noise, or when the error text (OIDC trust-policy mismatches especially) does
  not say what to check next. It finds the first supported failure signal and
  pairs it with the verification steps and the official doc page.
- **vs. pasting the log into an LLM.** An LLM can reason about failures SAM
  Doctor has no rule for, and that is sometimes the right call. The trade-offs:
  you upload the log (deployment logs routinely contain account IDs, ARNs, and
  role names), the answer varies run to run, and it may be confidently wrong.
  SAM Doctor is deterministic, runs offline, and redacts by default - and when
  it has no matching rule, it says so instead of guessing. Using it first and
  an LLM for the leftovers is a reasonable workflow.
- **vs. AWS Support.** Support can see your account state; SAM Doctor cannot
  and does not try. It is the two-minute local check you run before deciding
  whether a ticket is worth opening, and its redacted report is a safer
  artifact to paste into one.

## When not to use this

- The failure is in application runtime behavior, not the deployment itself -
  this reads deployment logs, not CloudWatch application logs.
- You need account-state inspection (drift, quotas, existing resources). SAM
  Doctor never calls AWS, by design.
- Your failure is outside the [supported rules](#what-it-detects) - you get an
  honest "no supported pattern found", not a guess.
- You want an automatic fix. Every report is a prompt to verify, not a change
  to apply.

## Scope and safety

Run this only on logs you are authorized to inspect. Review every suggested
command and policy change before applying it. SAM Doctor is diagnostic help,
not security, legal, or production-operations advice.

## Guides

- [Add SAM Doctor to an existing GitHub Actions deployment](docs/github-actions-integration.md)
- [On-call playbook: triage sequence, handoff template, escalation threshold](docs/on-call-playbook.md)
- [Fix "Not authorized to perform: sts:AssumeRoleWithWebIdentity" in GitHub Actions](docs/oidc-deployment-debugging.md)
- [Find the first useful error in a CloudFormation ROLLBACK_COMPLETE](docs/cloudformation-first-failure.md)
- [Fix "InsufficientCapabilitiesException" in an AWS SAM deployment](docs/capability-acknowledgement.md)
- [Worked examples (incident-to-action workflows)](docs/worked-examples.md)
- [Rolling out SAM Doctor on a team (commands by role)](docs/team-rollout.md)
- [Create a reproducible evidence packet for collaboration](docs/researcher-evidence-packet.md)

## Contributing

New contributors are welcome, and the best first changes are small: a
documentation correction, a reproducible false positive or missed diagnostic,
or one new diagnostic rule with a positive and a nearby-negative test. Start
with the [contributor setup](CONTRIBUTING.md), pick a fully specified rule
from the [rule roadmap](docs/rule-roadmap.md) or an issue labeled
[`good first issue`](https://github.com/jakegold1647/sam-doctor/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22),
and run `python scripts/check-pr.py` before opening the PR — it is the same
gate CI runs. Before sharing any log excerpt, remove account IDs, ARNs,
credentials, tokens, and customer data.

When you report a wrong or unclear diagnosis, include the SAM Doctor version,
the exact command, a sanitized excerpt, and what you expected. Small
reproducible reports get fixed fastest.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

`python scripts/run-smoke.py` runs the packaged demo and a sample diagnosis,
then checks that the JSON output is well-formed and contains findings.

See [CHANGELOG.md](CHANGELOG.md) for release history, [SECURITY.md](SECURITY.md)
for vulnerability reporting, [SUPPORT.md](SUPPORT.md) for help boundaries, and
[docs/pypi-publishing.md](docs/pypi-publishing.md) for the stable-release
publishing setup.

## Related projects

- Portfolio: [jacobgoldstein.dev](https://jacobgoldstein.dev)
- Historical text tooling: [aktreader](https://github.com/jakegold1647/aktreader)
  and [aktreader-research](https://github.com/jakegold1647/aktreader-research)
- Records corpus: [congress-poland-registers](https://github.com/jakegold1647/congress-poland-registers)
