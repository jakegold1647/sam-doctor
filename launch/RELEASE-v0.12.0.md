# SAM Doctor v0.12.0

SAM Doctor v0.12.0 packages the current catalog of 90 evidence-first
deployment diagnostics for AWS SAM, CDK, CloudFormation, IAM, and GitHub
Actions failures.

This release also refreshes the GitHub Action's Marketplace metadata so the
Marketplace listing can publish the current stable release.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Action with `jakegold1647/sam-doctor@v0`.
- Try the no-credentials [OIDC diagnostic demo](../examples/github-actions-oidc-diagnostic-demo.yml)
  before wiring the Action into a deployment workflow.
- Reports remain local and redacted. Review any report before sharing it.
