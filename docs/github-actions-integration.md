# Add SAM Doctor to an existing GitHub Actions deployment

SAM Doctor is most useful when it runs after the AWS SAM deployment command you already use. It reads the captured deployment output, reports the first actionable failure, and can add that result to the GitHub Actions job summary.

This guide does not create an AWS deployment workflow for you. Keep your current authentication, environment protection, and deployment command in place, then add the two steps below.

## 1. Capture deployment output

Add `tee deployment.log` to the step that already runs `sam deploy`. `set -o pipefail` preserves the deployment command's exit code while saving its output.

```yaml
- name: Deploy
  shell: bash
  run: |
    set -o pipefail
    sam deploy --no-confirm-changeset 2>&1 | tee deployment.log
```

If your deployment command has additional parameters, keep them. The important part is writing the combined output to a file.

## 2. Diagnose the log even when deployment fails

Place this step immediately after the deployment step. `if: always()` lets SAM Doctor inspect the log after a failed deploy instead of being skipped with the rest of the job.

```yaml
- name: Diagnose deployment log
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
```

The action writes a compact diagnosis to the workflow log and, when `summary` is enabled, to the job summary. By default it also adds redacted GitHub Actions notices for each finding, so issues are visible in the run UI. Set `annotations: "false"` if your workflow should not create annotations. The action exposes `finding-count` and `has-findings` as step outputs for a later notification or reporting step.

If you want one Action step to run the deployment and diagnose it, keep your
authentication steps before the Action and pass `run-command`:

```yaml
- name: Deploy and diagnose
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    run-command: sam deploy --no-confirm-changeset
    summary: true
```

This mode captures combined output, writes the same redacted summary and
annotations, and returns the deployment's original exit status. The command is
executed by Bash on the runner, so keep shell quoting and any environment setup
in the workflow. `deploy-exit-status` is exposed as an output (`0` when
`run-command` is not used). It cannot be combined with `batch: true`. The
`@v0` tag follows stable releases; pin a specific release tag when
reproducibility requires it.

For repositories that collect several deployment logs per run (for example, matrix jobs),
set `batch: true` and point `log-file` to a directory or glob:

```yaml
- name: Diagnose batched deployment logs
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: logs/
    batch: true
    summary: true
```

You can copy the full starter workflow from
`examples/github-actions-workflow.yml` and adjust your deploy command and
permissions, or use the rollout-safe
`examples/github-actions-workflow-two-phase-gating.yml` starter for pilot-to-strict
adoption.

If you prefer a CLI-first setup, run this once in your repo:

```bash
sam-doctor init --deploy-command "sam deploy --no-confirm-changeset"
```

That writes `.github/workflows/sam-doctor.yml` with the same diagnosis step and
a ready-to-edit deployment command. The workflow only runs on
`workflow_dispatch` until you pass `--on-push`, so trying `init` never wires up
an automatic AWS deployment by itself.

`sam-doctor init` supports rollout-oriented defaults:

- `--on-push` (deploy automatically on pushes to `main`; off by default)
- `--summary` / `--no-summary`
- `--annotations` / `--no-annotations`
- `--batch`
- `--fail-on-findings`
- `--fail-on-confidence high` (gate on high-confidence findings only)

The command above generates a non-blocking pilot workflow. Later, regenerate
with stricter behavior:

```bash
sam-doctor init --deploy-command "sam deploy --no-confirm-changeset" --fail-on-findings --force
```

If you already want a single reusable file for both modes without regenerating,
copy the two-phase template directly:

```bash
mkdir -p .github/workflows
curl -L https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/examples/github-actions-workflow-two-phase-gating.yml \
  -o .github/workflows/sam-doctor.yml
```

If your stack uses different deployment flow, start from one of these:

- `examples/github-actions-workflow-sam-sync.yml` for `sam sync`
- `examples/github-actions-workflow-cf-pipeline.yml` for `aws cloudformation deploy`
- `examples/github-actions-workflow-cdk.yml` for `cdk deploy`

Keep a short per-repo checklist in
[`examples/README.md`](../examples/README.md)
while you validate these templates in your CI.

If your workflow already uses a direct `run:` deployment command, you can keep the
integration shell-only and emit workflow-command annotations directly:

```yaml
- name: Diagnose deployment log
  if: always()
  run: |
    python -m sam_doctor.cli diagnose deployment.log --format github
```

## Optional: upload findings to GitHub code scanning

`--format sarif` renders the same findings as a SARIF 2.1.0 document, which
GitHub's code scanning UI (and any other SARIF consumer) can ingest. Each
result carries the rule's stable id (`iam.deny.explicit`, and so on - see
`docs/stability.md`), so alerts stay tied to the same rule across releases
even when titles are reworded:

```yaml
- name: Diagnose deployment log as SARIF
  if: always()
  run: |
    python -m sam_doctor.cli diagnose deployment.log --format sarif --output sam-doctor.sarif

- name: Upload SARIF to code scanning
  if: always()
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_path: sam-doctor.sarif
    category: sam-doctor
```

Batch mode emits one document for the whole run, with each result pointing at
its own log file:

```yaml
    python -m sam_doctor.cli batch logs/ --format sarif --output sam-doctor.sarif
```

High-confidence findings map to SARIF `error`, medium to `warning`. Evidence
lines and source paths go through the same redaction as every other format
before they leave the machine.

## Non-GitHub CI starters

For teams outside GitHub Actions, start from one of these examples:

- `examples/gitlab-ci-sam-doctor.yml` (GitLab)
- `examples/circleci-sam-doctor.yml` (CircleCI)
- `examples/azure-pipelines-sam-doctor.yml` (Azure)
- `examples/bitbucket-pipelines-sam-doctor.yml` (Bitbucket)

For non-`sam` command variants (`cdk deploy`, `serverless deploy`, custom),
use the command matrix:

[`ci-command-matrix.md`](ci-command-matrix.md)

## Optional: make recognized failures fail the job

Start by observing the diagnostics. When the rule set matches the failures you care about, opt into a diagnostic gate:

```yaml
with:
  log-file: deployment.log
  summary: true
  fail-on-findings: true
```

This setting does not replace the exit status from `sam deploy`; it makes a recognized diagnostic fail the job as well.

In `batch` mode, `fail-on-findings: true` also fails the SAM Doctor step when any
analyzed log reports findings; the step still writes output and keeps all findings in
the report for review.

## Action exit behavior

The action step exit status is:

- `0`: run completed and `fail-on-findings` did not request failure, even if findings were found.
- `1`: `fail-on-findings: true` and one or more findings are present.
- `2`: action precondition / runtime error (for example, missing `GITHUB_OUTPUT`,
  unsupported boolean input values, missing Python, or an invalid generated report).
- `deploy-exit-status`: the wrapped deployment status, or `0` when `run-command`
  is not set.
- `finding-count`: total supported findings (stringified integer output).
- `has-findings`: `true` when findings were detected, otherwise `false`.

You can use `has-findings` and `finding-count` outputs in a follow-up step for
structured routing while still keeping the action step non-blocking when desired.

```yaml
- name: Diagnose deployment log
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true

- name: Open one-click ticket details when findings are present
  if: steps.sam-doctor.outputs.has-findings == 'true'
  run: |
    echo "SAM Doctor found ${{ steps.sam-doctor.outputs.finding-count }} findings."
```

## Use your existing AWS authentication

SAM Doctor does not need AWS credentials. It reads a local log file, so leave the credentials and permissions model of your existing deployment workflow unchanged. If you deploy with GitHub Actions OIDC, see [Debug AWS SAM deployments with GitHub Actions OIDC](oidc-deployment-debugging.md) for the failure patterns SAM Doctor recognizes.

For a representative result, see the [first-failure guide](cloudformation-first-failure.md). For repositories where CloudFormation requests missing capabilities, see [Diagnose CAPABILITY_IAM and CAPABILITY_NAMED_IAM errors](capability-acknowledgement.md).
