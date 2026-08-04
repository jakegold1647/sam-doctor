# SAM Doctor

[![Verify free core](https://github.com/jakegold1647/sam-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/jakegold1647/sam-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![GitHub Marketplace](https://img.shields.io/badge/GitHub%20Marketplace-Available-blue?logo=github)](https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics)
[![PyPI](https://img.shields.io/pypi/v/sam-doctor.svg)](https://pypi.org/project/sam-doctor/)
[![GitHub release](https://img.shields.io/github/v/release/jakegold1647/sam-doctor?include_prereleases&label=release)](https://github.com/jakegold1647/sam-doctor/releases)

**Find the next useful step in a failed AWS deployment - without uploading your
logs or granting AWS access.** Use SAM Doctor for faster triage of `sam deploy`,
`cdk deploy`, and `aws cloudformation deploy` failures.

SAM Doctor reads AWS SAM, CloudFormation, IAM, and GitHub Actions deployment
logs locally. It identifies supported failure patterns and returns short,
redacted evidence, safe checks, and the relevant official documentation.

**[See the project page](https://jakegold1647.github.io/sam-doctor/)** |
**[Use on GitHub Marketplace](https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics)** |
**[Report a bad diagnosis](https://github.com/jakegold1647/sam-doctor/issues/new?template=bug_report.yml)** |
**[Request a rule](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)** |
**[Join the feedback discussion](https://github.com/jakegold1647/sam-doctor/discussions/1)**

It does **not** access AWS, upload logs, change resources, or promise an
authoritative root cause. It detects known patterns in the text you provide,
redacts common identifiers, and gives safe verification steps and the relevant
official documentation.

Current release: **v0.7.7**.

## Who this is for

- Use this tool if you need a fast local first pass when a SAM/CloudFormation/GitHub
  Actions deployment fails.
- Skip it if you need account-state inspection, drift analysis, quota checks, or
  automatic fixes.
- It is most useful for actionable deployment logs with explicit error lines and
  rollback context.

## Who should use it first

If you are:

- **Developer on-call:** use SAM Doctor before escalating to an engineering lead.
- **SRE/DevOps:** use it as a first triage step before opening deeper incident
  tickets.
- **Team lead / reviewer:** use it as a shared triage template for faster
  incident handoffs.

### Choose your path in 20 seconds

- **You have a failing deployment log file:** run one command and share one finding:
  `sam-doctor diagnose deployment.log --format markdown`.
- **You use GitHub Actions for deployment:** add one diagnostics step from one of the
  starter workflows in the [CI matrix](docs/ci-command-matrix.md).
- **You need a research-ready packet:** run
  `sam-doctor packet deployment.log` and share `diagnosis.md` + `diagnosis.json`
  only.
- **You're onboarding a team:** use the [Adopter onboarding kit](docs/adopter-onboarding-kit.md)
  for role-based templates and copy/paste text.

### Paste this in Slack/Teams/Email

```text
I ran @sam-doctor on the shared deploy excerpt:
- Finding: [top finding]
- Evidence: [top evidence line]
- Safe next check: [first command]
- Confidence: [high/med/low]
If this is real, next step is: [one action].
```

## Try it in 60 seconds

```bash
python -m pip install sam-doctor
sam-doctor demo
```

You can also use:

```bash
pipx install sam-doctor      # isolated install (no environment changes)
uvx sam-doctor demo          # run without install (if uv is available)
```

## Start using it in 90 seconds

```bash
mkdir -p .github/workflows
curl -sSL https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/examples/github-actions-workflow.yml -o .github/workflows/sam-doctor.yml
```
Prefer the CLI bootstrap command to avoid copy/paste mistakes:

```bash
sam-doctor init
```

Use `sam-doctor init --deploy-command "sam sync --no-confirm-changeset"` to match your
deployment command style.

## New contributor smoke check

Verify your installation and first output in one command:

```bash
python scripts/run-smoke.py
```

It runs a packaged demo and a sample diagnosis locally, then confirms JSON output is
well-formed and contains findings before you add the tool to CI.

1. Save a short failing excerpt as `deployment-failure.log`.
2. Run diagnosis:

```bash
sam-doctor diagnose deployment-failure.log --format markdown
```

3. Share only:

- the top finding title
- the first `verify` command
- a sanitized excerpt of the original error

```text
I ran @sam-doctor and it found: [top finding]
Next check: [one safe verification]
Need: [optional follow-up permission or config check]
```

If this result is wrong or unclear, open a
[`diagnostic report` issue](https://github.com/jakegold1647/sam-doctor/issues/new?template=bug_report.yml)
with the pasted excerpt and command output.

Use this copy/paste block for fast, high-signal reporting:

```text
Title: sam-doctor report - [short summary]
Version: sam-doctor [version]
Command: sam-doctor diagnose deployment-failure.log --format markdown
Finding: [top finding title]
Source: deployment-failure.log
Verify: [one command or doc check]
Excerpt:
<paste 1-3 sanitized lines around first matching error>
```

The bundled demo needs no AWS credentials and makes no network calls. It
prints a real report:

```text
SAM Doctor found 1 possible issue(s) in oidc-assume-role-failure.txt.

1. GitHub Actions cannot assume the configured AWS role through OIDC (high confidence)
   Matched on line: 1
   The workflow reached AWS STS but the role trust relationship did not accept
   the GitHub-issued OIDC token. ...
   Evidence:
   - Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity
   Verify:
   - Confirm the workflow or job permissions include `id-token: write`.
   - Check that the role trust policy accepts `token.actions.githubusercontent.com:aud`
     equal to `sts.amazonaws.com`.
   Docs: https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
```

## Use-case: fix a blocked deployment in one pass

Use this exact flow when a teammate shares an OIDC error in CI:

```bash
sam-doctor diagnose deployment.log --format markdown
```

If the failure text matches the expected pattern, the report starts with a short
actionable finding and the one safe check to run first:

```text
SAM Doctor found 1 possible issue(s) in deployment.log.

1. GitHub Actions cannot assume the configured AWS role through OIDC (high confidence)
   Matched on line: 3
   Evidence:
   - Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity
   Verify:
   - Confirm the workflow or job permissions include `id-token: write`.
   - Confirm the role trust policy includes subject and audience conditions that match
     GitHub's OIDC token.
```

This is built for team handoffs: teammate sends the sanitized excerpt, you run one
diagnosis, then share one verification command before changing IAM or deploy
configuration.

If the error is real, this usually shortens the back-and-forth from "who changed
what?" to "check this trust-policy field" in the same thread.

## Use-case: triage a CloudFormation rollback in one pass

When a teammate posts stack failure noise, search for the first actual signal instead
of treating `ROLLBACK_COMPLETE` as the root cause:

```bash
sam-doctor diagnose deployment.log --format markdown
```

A typical output starts with the earliest actionable finding and then your first
safe check:

```text
SAM Doctor found 1 possible issue(s) in deployment.log.

1. CloudFormation rollback-related failure in resource MyResource (high confidence)
   Matched on line: 4
   Evidence:
   - Received FAILED for resource MyResource in CREATE_FAILED/ROLLBACK_COMPLETE flow.
   Verify:
   - Check the earliest non-rollback resource event and the first AWS error line it includes.
   - Verify the policy/resource dependency and retry after the blocking condition is fixed.
```

Use this sequence in an incident thread:

1. Run `sam-doctor diagnose deployment.log --format markdown`.
2. Share only the first matched line and docs link.
3. Run one targeted fix based on that first event, then re-run deploy.

If your log is only a stack event excerpt, feed it directly with `sam-doctor diagnose -`.

## Use-case: resolve IAM capability blocks in under 2 minutes

When a deployment stops on capability approval, this is the common signature:

```text
CAPABILITY_IAM is required but was not acknowledged in the template
```

Use the same command you already use:

```bash
sam-doctor diagnose deployment.log --format markdown
```

A focused report usually includes:

```text
1. CloudFormation requires CAPABILITY_IAM (high confidence)
   Matched on line: 7
   Evidence:
   - CAPABILITY_IAM is required but was not provided.
   Verify:
   - Confirm whether you expect IAM changes from this template.
   - Re-run with the specific capability and deployment mode intended:
     `--capabilities CAPABILITY_IAM` (or CAPABILITY_NAMED_IAM when required).
```

In practice this shortens "why did it fail?" to "which flag is actually needed?" and
reduces repeated guess-and-retry cycles.

## Proof: one real pattern, redacted and repeatable

The goal is speed and confidence, not secrets. Here is a real-style flow you can
reuse verbatim with customer-safe redaction:

```text
# incident_excerpt.txt (sanitized)
An error occurred: Not authorized to perform: sts:AssumeRoleWithWebIdentity
Check that the identity-based policy attached to the role allows id-token:write.
```

Run:

```bash
sam-doctor diagnose incident_excerpt.txt --format markdown
```

Result:

```text
SAM Doctor found 1 possible issue(s) in incident_excerpt.txt.

1. GitHub Actions cannot assume the configured AWS role through OIDC (high confidence)
   Matched on line: 1
   Evidence:
   - Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity
   Verify:
   - Confirm the workflow includes `id-token: write`.
   - Verify the AWS role trust policy audience and subject conditions.
   Suggested next command:
   - sam deploy --no-confirm-changeset --skip-prompt
```

This output is deterministic for the same input and does not contain account IDs,
ARNs, or tokens.

## On-call playbook

If your team handles deployment incidents, use the ready-to-share playbook:

- [docs/on-call-playbook.md](docs/on-call-playbook.md)

It includes:
- A 60-second triage sequence
- Slack/Teams handoff template
- OIDC, rollback, and capability-specific follow-up checks
- A clear escalation threshold

To diagnose a real deployment log:

```bash
sam-doctor diagnose deployment.log
```

`pip` installs the latest stable release from PyPI. Other install paths that
work the same way:

```bash
pipx install sam-doctor      # isolated global CLI
uvx sam-doctor demo          # run without installing
```

To pin the tested release exactly, use `sam-doctor==0.7.7`; to install from
the tagged source instead:

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v0.7.7"
```

If your shell cannot find `sam-doctor` after installation, activate the
environment where it was installed or use `python -m sam_doctor.cli` in the
commands below.

## Help improve SAM Doctor

If a diagnosis was wrong or unclear, open a small reproducible issue and include:

- SAM Doctor version
- exact command used
- sanitized first relevant excerpt
- what outcome you expected

For new rules, open a rule request with the command family that hit the failure
and one safe follow-up check you expected.

For first-time contributors, keep the change small: one rule or one
documentation improvement, with a focused test.

## Related projects and ecosystem

- **Portfolio:** [jacobgoldstein.dev](https://jacobgoldstein.dev)
- **Research and historical text tooling:** [aktreader (public)](https://github.com/jakegold1647/aktreader)
- **Research edition:** [aktreader-research](https://github.com/jakegold1647/aktreader-research)
- **Historical records corpus project:** [congress-poland-registers](https://github.com/jakegold1647/congress-poland-registers)

## Pick your starting flow (fastest)

Use the first row that matches your current situation:

| Situation | First command |
| --- | --- |
| You have a deployment log file | `sam-doctor diagnose deployment.log --format markdown` |
| You want machine-readable output for CI | `sam-doctor diagnose deployment.log --format json --output diagnosis.json` |
| You want a CI annotation style report | `sam-doctor diagnose deployment.log --format github` |
| You only have pasted excerpt text | `printf '%s\n' "...error excerpt..." \| sam-doctor diagnose - --format markdown` |
| You are testing in a GitHub Action | Use the composite action in the CI section below |

## 60-second first response checklist

Use this when a teammate posts an error:

```bash
sam-doctor diagnose deployment.log --format markdown
```

If you need a quick signal from pasted text, skip the file step:

```bash
printf '%s\n' "Your pasted AWS failure excerpt" | sam-doctor diagnose -
```

If you use a CI step, this is often enough:

```bash
sam-doctor diagnose deployment.log --format github | tee /tmp/sam-doctor.txt
```

Then share the redacted diagnostic text only, or use it directly in a job summary.

Then reply with this pattern:

1. Quote the top finding (or say none supported yet).
2. Include one safe verification command from the report.
3. Ask for one follow-up: did that check pass?

If the tool did not match the failure and this was a real production issue, open
`Report a bad diagnosis` immediately and include a short, sanitized excerpt plus
the command you ran.

![SAM Doctor turns a failed deployment log into a concise diagnosis](docs/assets/sam-doctor-demo.svg)

## Current free core

- GitHub Actions OIDC errors: missing `id-token: write`, audience mismatch,
  trust-policy/subject mismatch, and `AssumeRoleWithWebIdentity` failures
- IAM `AccessDenied` failures
- Expired AWS credentials and runner clock skew (`ExpiredToken`, `Signature expired`)
- CloudFormation API throttling (`Rate exceeded`)
- CloudFormation failed-resource events and rollback states
- Blocked stack deletion: `DELETE_FAILED` blockers and termination protection
- ECR push authentication failures from the CI runner (missing login, expired token,
  denied `ecr:GetAuthorizationToken`)
- CloudFormation capability acknowledgement errors
- Lambda container-image failures caused by missing ECR image access
- API Gateway deployments created before methods exist
- SAM deployment/configuration errors, including conflicting artifact-bucket settings
  and missing `esbuild` dependencies
- SAM build/containerization errors where Docker is unavailable for `sam build --use-container`
- Python dependency resolution or validation errors in SAM/Python builds
- Template shape, IAM trust-policy, Lambda packaging, and S3 artifact failures
- API Gateway CORS preflight conflicts
- Terminal, Markdown, JSON, and GitHub-annotation reports
- Composite GitHub Action with opt-in redacted job summaries and CI gating
- Local redaction for account IDs, ARNs, email addresses, and common CI credentials

For more bundled examples, try `sam-doctor demo --scenario cloudformation`,
`sam-doctor demo --scenario api-gateway`, `sam-doctor demo --scenario esbuild`,
or `sam-doctor demo --scenario python-pip`.
Run `sam-doctor rules --format json` to inspect the exact set of supported
diagnostic categories before sharing a log.

To save a report:

```bash
sam-doctor diagnose deployment.log --format markdown --output diagnosis.md
```

The input can also be read from standard input, which is useful for CI steps and
shell pipelines:

```bash
kubectl logs deploy/my-api | sam-doctor diagnose -
sam-doctor diagnose deployment.log --format json --output diagnosis.json
```

For teams with multi-log workflows, batch reporting works with one command:

```bash
sam-doctor batch logs/*.log logs/*.txt --format json --fail-on-findings \
  --output batch-results.json
```

This returns `1` only when supported findings are detected and still emits a full
batch report for your artifacts.

The terminal format is intended for a quick local check, Markdown is convenient
for a human-readable handoff, JSON is stable for scripts and machine workflows,
and `github` emits GitHub workflow command annotations directly. All formats
include the first matching line number and matched evidence, not the full input
log.

For batch mode, `--format github` still emits one annotation per supported finding
and skips successful inputs, so a large batch can be scanned quickly in workflow
logs.

For machine integrations, the JSON payload shape is documented in checked-in schemas:

- `docs/schemas/diagnose-report.schema.json`
- `docs/schemas/batch-report.schema.json`
- `docs/schemas/rules-report.schema.json`

`sam-doctor` treats the JSON schema contracts as additive-compatible: additive top-level
fields are allowed, but removing or renaming documented required fields is a breaking
change and requires a coordinated version bump.

### CLI exit codes

| Status | Meaning |
| --- | --- |
| `0` | Command completed successfully with no enforced fail gate hit. |
| `1` | `--fail-on-findings` found one or more supported findings (for `diagnose` or `batch`). |
| `2` | CLI usage/error-path failures (for example, missing inputs or invalid arguments). |

For `batch`, `--fail-on-findings` gates the whole run the same way: if any file has
a supported finding, the command exits `1` after reporting all files.

### GitHub Action exit behavior

Action step exit status is `0` unless `fail-on-findings: true` and findings are detected.

- `0`: no enforced action failure (findings may exist).
- `1`: findings present and `fail-on-findings: true`.
- `2`: action runtime/precondition failure (for example, invalid boolean inputs or missing Python in the runner).
- `finding-count` and `has-findings` are available as action outputs:
  - `finding-count` is the number of supported findings.
  - `has-findings` is `true` when `finding-count` is greater than `0`, else `false`.

Use the outputs for non-blocking workflows:

```yaml
- name: Diagnose deployment log
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true

- name: Route to dedicated triage when action reports findings
  if: steps.sam-doctor.outputs.has-findings == 'true'
  run: |
    echo "Routing failure with ${{ steps.sam-doctor.outputs.finding-count }} findings to a higher-signal runbook."
```

You can also process multiple files in batch mode:

```bash
sam-doctor batch logs/*.log logs/*.txt --format json > batch-results.json
```

For a shell-based CI gate, add `--fail-on-findings`. The command still writes
the report, then exits with status 1 only when a supported finding is present:

```bash
sam-doctor diagnose deployment.log --format json \
  --output diagnosis.json --fail-on-findings
```

For multi-file CI input:

```bash
sam-doctor batch logs/*.log logs/*.txt --format json \
  --output batch-results.json --fail-on-findings
```

### GitHub Action batch mode

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
    # Enable strict gating only after a short warm-up period.
    # fail-on-findings: true
```

## GitHub Actions

Use the included action when a workflow already saves a deployment log:

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

Use this ready-to-copy starter workflow as your starting point:

```bash
curl -L https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/examples/github-actions-workflow.yml -o .github/workflows/sam-doctor.yml
```

### 90-second onboarding by stack type

- **AWS SAM deploy command**
  - Start with [`examples/github-actions-workflow.yml`](examples/github-actions-workflow.yml)
- **AWS SAM sync workflows**
  - Start with [`examples/github-actions-workflow-sam-sync.yml`](examples/github-actions-workflow-sam-sync.yml)
- **CloudFormation package/deploy commandline**
  - Start with [`examples/github-actions-workflow-cf-pipeline.yml`](examples/github-actions-workflow-cf-pipeline.yml)
- **AWS CDK deploy command**
  - Start with [`examples/github-actions-workflow-cdk.yml`](examples/github-actions-workflow-cdk.yml)
- **Batched deploy logs in one pipeline run**
  - Start with [`examples/github-actions-workflow-batch-logs.yml`](examples/github-actions-workflow-batch-logs.yml)

You can also use the examples index to track what you changed:

[`examples/README.md`](examples/README.md)

### Deployment onboarding matrix

Use the command-to-template matrix for your exact deploy command:

[`docs/ci-command-matrix.md`](docs/ci-command-matrix.md)

## Non-GitHub CI starter templates

If your repo uses another CI system, copy:

- GitLab: [`examples/gitlab-ci-sam-doctor.yml`](examples/gitlab-ci-sam-doctor.yml)
- CircleCI: [`examples/circleci-sam-doctor.yml`](examples/circleci-sam-doctor.yml)
- Azure Pipelines: [`examples/azure-pipelines-sam-doctor.yml`](examples/azure-pipelines-sam-doctor.yml)
- Bitbucket Pipelines: [`examples/bitbucket-pipelines-sam-doctor.yml`](examples/bitbucket-pipelines-sam-doctor.yml)
- Batch logs: [`examples/github-actions-workflow-batch-logs.yml`](examples/github-actions-workflow-batch-logs.yml)

Put the diagnostic step after the command that writes the log and keep
`if: always()`; otherwise GitHub Actions skips it when the deployment fails.
The action exposes `finding-count` and `has-findings` outputs. Set
`fail-on-findings: true` only when you want a supported diagnostic to fail
the job; the commented line above shows the opt-in placement. The Markdown job
summary is opt-in and contains only matched, redacted
evidence; review it before sharing a workflow run outside your team. The action
also adds redacted GitHub Actions notices for every finding by default; set
`annotations: "false"` to disable it.

You can also adapt the full example from
[`examples/github-actions-workflow.yml`](examples/github-actions-workflow.yml).

## What a report includes

SAM Doctor deliberately reports only what its rules can support:

1. A likely failure category and confidence level.
2. Up to three matched log lines, redacted before output.
3. Safe checks to validate the diagnosis before changing a policy or stack.
4. A link to the relevant official documentation.

It is most useful when you start with the first failure in a deployment log,
not a later rollback message. When multiple supported patterns appear, SAM
Doctor presents findings in the order of their first matching log line.

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
- Your failure is outside the [supported rules](#supported-signals) - you get
  an honest "no supported pattern found", not a guess.
- You want an automatic fix. Every report is a prompt to verify, not a
  change to apply.

## Feedback and roadmap

The free core will stay useful for individual deployment failures. Please open
an issue when a report is wrong, unclear, or missing a failure pattern. For a
new rule, include only a sanitized error excerpt and the safe next check you
expected to see. See [CONTRIBUTING.md](CONTRIBUTING.md) for the exact format.

## Guides

- [Add SAM Doctor to an existing GitHub Actions deployment](docs/github-actions-integration.md)
- [Adopter onboarding kit (team templates + rollout sequence)](docs/adopter-onboarding-kit.md)
- [Fix "Not authorized to perform: sts:AssumeRoleWithWebIdentity" in GitHub Actions](docs/oidc-deployment-debugging.md)
- [Find the first useful error in a CloudFormation ROLLBACK_COMPLETE](docs/cloudformation-first-failure.md)
- [Fix "InsufficientCapabilitiesException" in an AWS SAM deployment](docs/capability-acknowledgement.md)
- [Create a reproducible evidence packet for collaboration](docs/researcher-evidence-packet.md)
- [Community sharing kit (onboarding + announcement templates)](docs/community-sharing-kit.md)

## Supported signals

Run `sam-doctor rules` for the current machine-readable catalog. Each rule is
triggered by an explicit error signal, not by template inspection or AWS account
access; the report is still a prompt to verify the cause, not an automatic fix.

## Scope and safety

Run this only on logs you are authorized to inspect. Review every suggested
command and policy change before applying it. SAM Doctor is diagnostic help,
not security, legal, or production-operations advice.

## Researcher-ready evidence packet

For reproducible, repeatable collaboration:

```bash
sam-doctor packet deployment.log
```

Then share only a minimal sanitized packet (commands, key context, and outputs)
instead of raw logs:

- `diagnosis.md`
- `diagnosis.json`
- `docs/researcher-evidence-packet.md` (template)

Start here:

`docs/researcher-evidence-packet.md`

If you want a ready-to-use onboarding script and short announcement drafts for
community posting, use:

- [docs/community-sharing-kit.md](docs/community-sharing-kit.md)

If you're preparing a repeatable review packet for a teammate, maintainer, or
researcher, use:

- [RESEARCHER_OVERVIEW.md](RESEARCHER_OVERVIEW.md)

Reports redact AWS account IDs, ARNs, email addresses, common AWS access key IDs,
bare STS session tokens, quoted and unquoted secret assignments,
bearer tokens, JWT-style tokens, and common GitHub token formats before matched
evidence or a displayed source name is shared. This is a helpful guardrail, not a secret scanner:
review a report before sharing it.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m build
```

See [CHANGELOG.md](CHANGELOG.md) for release history, [SECURITY.md](SECURITY.md)
for vulnerability reporting, [SUPPORT.md](SUPPORT.md) for help boundaries, and
[docs/pypi-publishing.md](docs/pypi-publishing.md) for the stable-release
publishing setup.

