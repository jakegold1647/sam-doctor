# CI command -> SAM Doctor onboarding matrix

Use this matrix to quickly choose the right starting template.

| Deployment command | Typical scenario | Starting template | Capture step |
| --- | --- | --- | --- |
| `sam deploy --no-confirm-changeset` | GitHub SAM CLI deploy | [`examples/github-actions-workflow.yml`](../examples/github-actions-workflow.yml) | Add `2>&1 | tee deployment.log` to the deploy command |
| `sam sync` | AWS SAM iterative sync | [`examples/github-actions-workflow-sam-sync.yml`](../examples/github-actions-workflow-sam-sync.yml) | Add `2>&1 | tee deployment.log` to the sync command |
| `aws cloudformation deploy ...` | Direct CloudFormation deployments | [`examples/github-actions-workflow-cf-pipeline.yml`](../examples/github-actions-workflow-cf-pipeline.yml) | Add `2>&1 | tee deployment.log` in your deploy step |
| `sam deploy` in GitLab CI | GitLab pipeline | [`examples/gitlab-ci-sam-doctor.yml`](../examples/gitlab-ci-sam-doctor.yml) | Keep `sam-doctor diagnose deployment.log ... || true` until stable |
| `sam deploy` in CircleCI | CircleCI pipeline | [`examples/circleci-sam-doctor.yml`](../examples/circleci-sam-doctor.yml) | Add diagnosis in the same step as your deploy command |
| `sam deploy` in Azure Pipelines | Azure pipeline | [`examples/azure-pipelines-sam-doctor.yml`](../examples/azure-pipelines-sam-doctor.yml) | Keep `continueOnError: true` while you validate |
| `sam deploy` in Bitbucket Pipelines | Bitbucket pipeline | [`examples/bitbucket-pipelines-sam-doctor.yml`](../examples/bitbucket-pipelines-sam-doctor.yml) | Keep diagnosis non-blocking during early rollout |
| Multiple deployment logs in one GitHub Action run | Batch-mode CI workflows | [`examples/github-actions-workflow-batch-logs.yml`](../examples/github-actions-workflow-batch-logs.yml) | Save logs under `logs/` and set `batch: true` with `log-file` |
| Any other command (`cdk deploy`, `serverless deploy`, custom scripts) | Non-standard | [`examples/README.md`](../examples/README.md) | Use any starter and replace the deploy line with your command |

## 90-second quick path

1. Pick your command from the matrix.
2. Copy the linked starter template.
3. Replace deploy line with your command + `2>&1 | tee deployment.log` (or equivalent).
4. Keep an optional non-blocking diagnose flag until your team is ready.
5. Turn strict failure gating on only after a few stable runs.

### Batched logs in GitHub Actions

If your workflow writes multiple logs, keep the diagnosis step at the end and set
`batch: true`, then pass a directory or glob:

`log-file: logs/`

## Notes

- `findings` can be surfaced in JSON for scripts and chat ops.
- For GitHub Actions, keep `if: always()` on the diagnose step so failures still get analyzed.
- For all flows, use sanitized log excerpts if you paste anything externally.
