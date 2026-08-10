name: SAM Doctor examples

Use these templates to onboard quickly.

## GitHub Actions starters

- `github-actions-workflow.yml`
  - Works for classic `sam deploy` command.
  - Drop this at `.github/workflows/sam-doctor.yml` and fill in your deployment step.
  - For a single Action step that owns capture and diagnosis, use `run-command` as
    documented in `docs/github-actions-integration.md`.

- `github-actions-workflow-two-phase-gating.yml`
  - Lets teams start non-blocking (`pilot`) and switch to strict enforcement
    (`strict`) for manual rollout validation.
  - Use `workflow_dispatch` with `rollout-mode: strict` to enable
    `fail-on-findings` after pilot stability.

- `github-actions-workflow-sam-sync.yml`
  - Works for `sam sync` style workflows.
  - Replace `your-stack-name` and add any extra `sam sync` arguments.

- `github-actions-workflow-cf-pipeline.yml`
  - Works for direct `aws cloudformation deploy` invocations.
  - Replace template path, stack name, and capabilities.

## AWS CDK Actions starter

- `github-actions-workflow-cdk.yml`
  - Works for `cdk deploy` command flows.
  - Keep `2>&1 | tee deployment.log` on the deploy step and replace `--all --require-approval never` with your team's command.

## GitHub Actions batch logs

- `github-actions-workflow-batch-logs.yml`
  - Use when a single run produces multiple deployment logs (matrix, multi-region, multiple stacks).
  - Point `log-file` at a directory or wildcard and set `batch: true`.

## GitLab CI starter

- `gitlab-ci-sam-doctor.yml`
  - Add this as `.gitlab-ci.yml` and replace deployment command with your team's real deploy step.
  - The example keeps diagnosis advisory while preserving the deployment exit status.

## CircleCI starter

- `circleci-sam-doctor.yml`
  - Add this as `.circleci/config.yml` and replace deployment command with your real deploy step.
  - Use this when you have a non-GitHub pipeline but want the same one-command diagnosis without masking a failed deploy.

## Azure Pipelines starter

- `azure-pipelines-sam-doctor.yml`
  - Add this as `azure-pipelines.yml` and replace deployment command with your real deploy step.
  - The Bash step keeps diagnosis advisory while returning the deployment status.

## Bitbucket Pipelines starter

- `bitbucket-pipelines-sam-doctor.yml`
  - Add this as `bitbucket-pipelines.yml` and replace deployment command with your real deploy step.
  - The example keeps diagnosis advisory while preserving the deployment exit status.

## One-time setup (30 seconds)

1. Copy one starter file into your CI configuration location.
2. Replace the deploy command with your real deployment flow.
3. For GitHub Actions, keep `if: always()` on the diagnose step.

```bash
curl -L https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/examples/github-actions-workflow.yml \
  -o .github/workflows/sam-doctor.yml
```

## Optional CLI-only teams

- `sam-doctor run --log-file deployment.log -- sam deploy --no-confirm-changeset`
- `sam-doctor diagnose deployment.log --format json`
- `sam-doctor batch logs/*.log --format json --fail-on-findings`
- `sam-doctor diagnose deployment.log --format github`

## Reproducible evidence packet for collaborators

If you are sharing results with a teammate, reviewer, or researcher, generate both
human and machine outputs at once:

```bash
sam-doctor packet deployment.log
```

Then include:

- a short sanitized command history,
- `artifacts/diagnosis.md`,
- `artifacts/diagnosis.json`,
- `artifacts/researcher-notes.md`, and
- `docs/researcher-evidence-packet.md` (template and reporting notes).

This keeps the collaboration artifact lightweight and redacted.

Use the packet template:

- [Researcher evidence packet](../docs/researcher-evidence-packet.md)

Keep this checklist in your repo until the template is stable in CI.

## Quick command matching

Use the full matrix to pick the right starter for your exact deploy command:

- [`ci-command-matrix.md`](../docs/ci-command-matrix.md)
