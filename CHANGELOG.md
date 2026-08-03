# Changelog

All notable changes to SAM Doctor are documented here.

## v0.2.0 - 2026-08-02

- Added JSON output for scripts and CI.
- Added stdin support with `sam-doctor diagnose -`.
- Redacted common AWS access key IDs and GitHub token formats in matched evidence.
- Made Markdown evidence safe to render and bounded evidence excerpts from noisy logs.
- Reduced false positives for successful SAM, CORS, and STS log lines.
- Expanded CI coverage across Python 3.10, 3.11, and 3.12.

## v0.1.0 - 2026-08-02

- Initial free alpha with local diagnostics for supported AWS SAM, CloudFormation,
  IAM, API Gateway CORS, and GitHub Actions OIDC failures.
