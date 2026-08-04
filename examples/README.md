name: SAM Doctor examples

Use these templates to onboard quickly.

## GitHub Actions starters

- `github-actions-workflow.yml`
  - Works for classic `sam deploy` command.
  - Drop this at `.github/workflows/sam-doctor.yml` and fill in your deployment step.

- `github-actions-workflow-sam-sync.yml`
  - Works for `sam sync` style workflows.
  - Replace `your-stack-name` and add any extra `sam sync` arguments.

- `github-actions-workflow-cf-pipeline.yml`
  - Works for direct `aws cloudformation deploy` invocations.
  - Replace template path, stack name, and capabilities.

## One-time setup (30 seconds)

1. Copy one starter file into `.github/workflows/`.
2. Replace the deploy command with your real deployment flow.
3. Keep `if: always()` on the diagnose step.

```bash
curl -L https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/examples/github-actions-workflow.yml \
  -o .github/workflows/sam-doctor.yml
```

## Optional CLI-only teams

- `sam-doctor diagnose deployment.log --format json`
- `sam-doctor batch logs/*.log --format json --fail-on-findings`

Keep this checklist in your repo until the template is stable in CI.
