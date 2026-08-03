# SAM Doctor v0.2.0

SAM Doctor v0.2.0 is a more shareable free alpha for diagnosing supported AWS
SAM, CloudFormation, IAM, API Gateway CORS, and GitHub Actions OIDC failures
without uploading logs or requiring AWS credentials.

## Highlights

- JSON output for CI, scripts, and structured handoffs.
- Stdin support: `some-command | sam-doctor diagnose -`.
- Stronger local redaction for common AWS access key IDs and GitHub token formats.
- Shorter, safer report excerpts from noisy CI logs.
- Tighter matching that avoids treating successful SAM, CORS, and STS lines as failures.

## Try it

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v0.2.0"
sam-doctor demo
```

Feedback is most useful when it includes a short, sanitized error excerpt and
whether the report led to a useful next check.
