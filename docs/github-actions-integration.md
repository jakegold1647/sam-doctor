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
  uses: jakegold1647/sam-doctor@v0.7.7
  with:
    log-file: deployment.log
    summary: "true"
```

The action writes a compact diagnosis to the workflow log and, when `summary` is enabled, to the job summary. By default it also adds one redacted GitHub Actions notice for the first finding, so the likely cause is visible in the run UI. Set `annotations: "false"` if your workflow should not create that notice. The action exposes `finding-count` and `has-findings` as step outputs for a later notification or reporting step.

## Optional: make recognized failures fail the job

Start by observing the diagnostics. When the rule set matches the failures you care about, opt into a diagnostic gate:

```yaml
with:
  log-file: deployment.log
  summary: "true"
  fail-on-findings: "true"
```

This setting does not replace the exit status from `sam deploy`; it makes a recognized diagnostic fail the job as well.

## Use your existing AWS authentication

SAM Doctor does not need AWS credentials. It reads a local log file, so leave the credentials and permissions model of your existing deployment workflow unchanged. If you deploy with GitHub Actions OIDC, see [Debug AWS SAM deployments with GitHub Actions OIDC](oidc-deployment-debugging.md) for the failure patterns SAM Doctor recognizes.

For a representative result, see the [first-failure guide](cloudformation-first-failure.md). For repositories where CloudFormation requests missing capabilities, see [Diagnose CAPABILITY_IAM and CAPABILITY_NAMED_IAM errors](capability-acknowledgement.md).