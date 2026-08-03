# SAM Doctor v0.4.0

SAM Doctor v0.4.0 completes more of the GitHub Actions OIDC setup path with
high-confidence findings that distinguish a workflow-permission problem, a
missing AWS identity provider, and a role trust-policy mismatch.

## Highlights

- Detects a job that cannot request an OIDC token because it lacks `id-token: write`.
- Detects a target AWS account that has no GitHub Actions OIDC provider.
- Keeps each finding focused on the smallest safe next check instead of treating
  all STS failures as generic IAM access-denied errors.

## Try it

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v0.4.0"
sam-doctor rules
```

Use the free alpha on sanitized log excerpts only. It runs locally and does not
access AWS, upload logs, or make infrastructure changes.
