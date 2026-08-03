# SAM Doctor v0.3.1

SAM Doctor v0.3.1 makes diagnostic reports easier to share and verify while
adding current guidance for GitHub Actions to AWS OIDC deployments.

## Highlights

- JSON reports and `sam-doctor rules --format json` now include the exact tool version.
- New [OIDC deployment debugging guide](https://github.com/jakegold1647/sam-doctor/blob/main/docs/oidc-deployment-debugging.md).
- OIDC verification steps now call out GitHub's newer immutable subject-claim
  format, so a trust policy can be matched to the token a repository actually emits.

## Try it

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v0.3.1"
sam-doctor demo
```

Please share only sanitized deployment errors. A report that did not help is as
useful as a report that did: open an issue or reply in the project discussion
with the first error and the check that would have saved time.
