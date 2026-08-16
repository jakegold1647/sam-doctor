# Sanitized community examples

This gallery shows four small, reproducible SAM Doctor loops using checked-in
fixtures. They are documentation fixtures, not production logs. Each example
uses a deterministic local command, shows only the report fields that matter,
and points to the rule and error guide behind the result.

## Sharing boundary

- The source inputs live in `examples/*.txt` and are safe, synthetic examples;
  the CDK fixture deliberately includes a fake home-directory path to exercise
  redaction.
- The fixtures are part of the repository and are reproducible offline. They do
  not contain customer names, account data, deployment history, or credentials.
- The report fragments below are generated from the matching lines, not copied
  from a production incident. Review any report from your own logs before
  sharing it.

## GitHub Actions: OIDC role assumption

**Tracked input:** [`examples/oidc-assume-role-failure.txt`](../examples/oidc-assume-role-failure.txt)

Run the checked-in GitHub Actions excerpt locally:

```bash
sam-doctor diagnose examples/oidc-assume-role-failure.txt --format markdown
```

**Redacted report, key parts:**

```markdown
## 1. GitHub Actions cannot assume the configured AWS role through OIDC

**Confidence:** high

### Evidence
- Matched on line: 2
- <code>Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity</code>

### Safe verification steps
- Confirm the workflow or job permissions include `id-token: write`.
```

The `github.oidc.assume-role-rejected` rule is supported because the excerpt
contains the explicit STS web-identity denial, not a generic access failure.

**Next read-only verification:** inspect the workflow and reusable workflow
permissions to confirm that the job which requests AWS credentials can mint an
OIDC token.

**Rule and guide:** `github.oidc.assume-role-rejected` —
[AssumeRoleWithWebIdentity guide](https://sam-doctor.jacobgoldstein.dev/errors/assume-role-with-web-identity.html).

## SAM: missing esbuild dependency

**Tracked input:** [`examples/esbuild-missing-failure.txt`](../examples/esbuild-missing-failure.txt)

```bash
sam-doctor diagnose examples/esbuild-missing-failure.txt --format markdown
```

**Redacted report, key parts:**

```markdown
## 1. SAM build cannot find the configured esbuild dependency

**Confidence:** high

### Evidence
- Matched on line: 1
- <code>NodejsNpmEsbuildBuilder:EsbuildBundle - Esbuild Failed: Cannot find esbuild.</code>

### Safe verification steps
- Declare a compatible `esbuild` version in the function project's development dependencies and commit its lockfile.
```

The `sam.build.esbuild-missing` rule requires SAM's esbuild builder together
with the explicit missing-dependency message.

**Next read-only verification:** inspect the function directory's
`package.json` and lockfile, then compare it with the directory that the CI
step passes to `sam build`.

**Rule and guide:** `sam.build.esbuild-missing` —
[esbuild-not-found guide](https://sam-doctor.jacobgoldstein.dev/errors/esbuild-not-found.html).

## CloudFormation: API Gateway deployed before methods existed

**Tracked input:** [`examples/api-gateway-no-methods-failure.txt`](../examples/api-gateway-no-methods-failure.txt)

```bash
sam-doctor diagnose examples/api-gateway-no-methods-failure.txt --format markdown
```

**Redacted report, key parts:**

```markdown
## 1. API Gateway deployment started before the API had any methods

**Confidence:** high

### Evidence
- Matched on line: 1
- <code>... MyApiDeployment CREATE_FAILED Resource handler returned message: "The REST API doesn't contain any methods."</code>

### Safe verification steps
- Check whether the template declares a manual `AWS::ApiGateway::Deployment` alongside `AWS::Serverless::Api`.
```

The targeted `apigateway.deployment.no-methods` rule owns the exact API
Gateway message. The same event may also produce the broader
`cloudformation.resource.create-update-failed` context; start with the
specific result.

**Next read-only verification:** review the transformed template and list the
methods that exist before the manual deployment resource is created.

**Rule and guide:** `apigateway.deployment.no-methods` —
[REST API has no methods guide](https://sam-doctor.jacobgoldstein.dev/errors/rest-api-no-methods.html).

## CDK: asset bundling wrapper

**Tracked input:** [`examples/cdk-asset-bundling-failure.txt`](../examples/cdk-asset-bundling-failure.txt)

```bash
sam-doctor diagnose examples/cdk-asset-bundling-failure.txt --format markdown
```

**Redacted report, key parts:**

```markdown
## 1. AWS CDK could not bundle an asset before deployment

**Confidence:** low

### Evidence
- Matched on line: 1
- <code>Failed to bundle asset example-app/function/Api/Code/Stage, bundle output is located at [REDACTED_PRIVATE_PATH]: Error: esbuild exited with status 1</code>

### Safe verification steps
- Rerun `cdk synth --verbose` from the same project directory with the same app, context, and environment, then inspect the first bundler error for the named asset.
```

The `cdk.asset.bundling-failed` rule needs both the asset wrapper and its
temporary-output marker. It is intentionally low confidence: the wrapper
does not identify the compiler, dependency, permission, or Docker failure
that caused the bundle to stop.

**Next read-only verification:** run the suggested verbose synth and preserve
the first underlying bundler error before changing generated CDK output.

**Rule and guide:** `cdk.asset.bundling-failed` —
[failed-to-bundle-asset guide](https://sam-doctor.jacobgoldstein.dev/errors/cdk-asset-bundling-failed.html).

## Using these examples in a discussion

Link to a fixture and the matching rule when you want to show a supported
pattern. For a real incident, use the smallest authorized excerpt, run
`sam-doctor packet`, review the generated files, and share only the reviewed
packet — never a full deployment log.
