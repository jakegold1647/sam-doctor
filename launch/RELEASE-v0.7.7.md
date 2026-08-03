# SAM Doctor v0.7.7

SAM Doctor v0.7.7 adds a focused diagnosis for Lambda container-image deployments
that fail because Lambda cannot access the configured Amazon ECR image.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Marketplace Action with `jakegold1647/sam-doctor@v0.7.7`.
- Use `--fail-on-findings` only when a supported diagnosis should fail a CI job.
- Reports remain local, redacted, and evidence-first.
