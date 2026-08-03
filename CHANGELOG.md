# Changelog

All notable changes to SAM Doctor are documented here.

## v0.7.1 - 2026-08-03

- Ordered multiple findings by the first supporting line in the supplied log so
  earlier failures are presented before downstream deployment noise.

## v0.7.0 - 2026-08-03

- Added direct findings for invalid SAM template properties, IAM trust-policy
  `Resource` fields, Lambda image code-signing conflicts, invalid S3 bucket
  names, and S3 access denied for Lambda layer artifacts.

## v0.6.0 - 2026-08-03

- Added a composite GitHub Action with redacted job-summary output and opt-in
  failure gating for supported findings.
- Added direct findings for a missing `esbuild` dependency, conflicting SAM S3
  deployment options, API Gateway deployments with no methods, and non-updatable
  initial stacks in `ROLLBACK_COMPLETE`.

## v0.5.0 - 2026-08-03

- Added a high-confidence diagnosis for CloudFormation capability acknowledgements
  required by IAM resources and nested applications.

## v0.4.1 - 2026-08-03

- Redacted bearer tokens and JWT-shaped tokens when they appear in matched evidence.

## v0.4.0 - 2026-08-02

- Added a direct diagnostic when a GitHub Actions job lacks `id-token: write`.
- Added a direct diagnostic for a missing GitHub Actions OIDC provider in the
  target AWS account.

## v0.3.1 - 2026-08-02

- Added the tool version to JSON reports and the rule catalog.
- Added a practical GitHub Actions to AWS OIDC troubleshooting guide.
- Updated OIDC verification guidance for GitHub's immutable subject-claim format.

## v0.3.0 - 2026-08-02

- Added a catalog command: `sam-doctor rules`.
- Added a bundled CloudFormation failed-resource demo.
- Added a direct high-confidence finding for CloudFormation `CREATE_FAILED` and
  `UPDATE_FAILED` resource events.
- Tightened OIDC audience matching so a generic `InvalidIdentityToken` is not
  reported as an audience problem without supporting evidence.
- Redacted common key, token, password, and session-token assignments in evidence.

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
