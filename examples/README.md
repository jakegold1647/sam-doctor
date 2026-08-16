name: SAM Doctor examples

Use these templates to onboard quickly.

## Credential-free first run

`oidc-assume-role-failure.txt` is the sanitized local sample used by the smoke
check and the GitHub Actions preview. It requires no AWS account, credentials,
deployment, or network access:

```bash
sam-doctor diagnose examples/oidc-assume-role-failure.txt --format markdown
```

Expected result: exactly one finding with the stable rule id
`github.oidc.assume-role-rejected`.

The packaged `sam-doctor demo` command uses the mirror under
`src/sam_doctor/data/`. If the sample changes with the rule, update both copies
and run `python -m pytest tests/test_bundled_samples.py tests/test_run_smoke.py -q`.

## GitHub Actions starters

- [`github-actions-oidc-diagnostic-demo.yml`](https://github.com/jakegold1647/sam-doctor/actions/workflows/oidc-diagnostic-demo.yml)
  - This repository's live, manually triggered demo runs against the bundled,
    sanitized OIDC failure excerpt: no AWS account, credentials, deployment, or
    repository secrets required.
  - To run it from a fork: enable Actions if GitHub asks, open **Actions**, choose
    **Preview a credential-free OIDC diagnosis**, then select **Run workflow**.
    The run stays green and uploads only `redacted-oidc-diagnosis`; it never
    uploads the fixture or a log bundle.
  - The report proves the stable `github.oidc.assume-role-rejected` rule ID.
    For a real deployment, follow [CONTRIBUTING.md](../CONTRIBUTING.md); for a
    result, miss, or confusing local behavior, use the
    [sanitized usage-feedback form](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml).

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

## Opt-in pull request comment

Use [`github-actions-pr-comment.yml`](github-actions-pr-comment.yml) when a same-repository pull request should receive one updated, redacted first-finding comment. Fork PRs keep the job summary and skip the comment; no raw log is uploaded or posted.
