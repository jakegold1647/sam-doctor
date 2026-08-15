# First-deployment pilot

This is a short, reversible way to try SAM Doctor on deployment failures before
you add it to a required CI check. It uses only sanitized text and makes no AWS
API calls.

## Before you start

Have the current package installed and three small text inputs ready:

- one supported failure, such as [the OIDC example](../examples/oidc-assume-role-failure.txt);
- a different supported failure, such as [the CloudFormation example](../examples/cloudformation-resource-failure.txt);
- a no-match excerpt with the identifiers removed.

The inputs should contain only the lines you are allowed to inspect. Do not paste
credentials, tokens, account IDs, ARNs, customer data, or a complete production
log.

## Ten-minute run

Install the release you want to evaluate:

```bash
python -m pip install --upgrade sam-doctor
sam-doctor --version
```

Run the two tracked examples and one no-match input:

```bash
sam-doctor diagnose examples/oidc-assume-role-failure.txt --format json --output pilot-oidc.json
sam-doctor diagnose examples/cloudformation-resource-failure.txt --format json --output pilot-cloudformation.json
printf '%s\n' 'deployment finished with status 0' | sam-doctor diagnose - --format json --output pilot-no-match.json
```

On PowerShell, the no-match command is:

```powershell
'deployment finished with status 0' | sam-doctor diagnose - --format json --output pilot-no-match.json
```

Record the result before reading the suggested verification command:

| Input | Finding IDs | Highest confidence | Evidence line reviewed | Result |
| --- | --- | --- | --- | --- |
| OIDC example |  |  |  | expected / unexpected |
| CloudFormation example |  |  |  | expected / unexpected |
| No-match excerpt | none expected | — | — | expected / unexpected |

For each finding, check that the matched line is present in the excerpt and
that the proposed verification is read-only. A finding is a lead for the next
check, not proof of the root cause.

## Try it in CI without making it a gate

After the local run looks right, add the diagnostic step after the deploy step
and keep the deploy's original result visible:

```yaml
- name: Diagnose deployment log
  if: always()
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
    fail-on-findings: false
```

Leave it advisory for three to five stable runs. Note false findings, missed
findings, and findings that were useful but unclear. Only then choose whether
to keep advisory mode, gate high-confidence findings, or enable strict gating.

## Stop and roll back

Stop the pilot if:

- the no-match input produces a finding;
- a report includes text you did not intend to share;
- a suggested check would change infrastructure;
- the action changes the deploy's exit status while fail-on-findings is false; or
- a CI run is too noisy to review safely.

Rollback is just removing the diagnostic step and any generated report files.
The pilot does not change AWS resources, credentials, or repository settings.

If something looks wrong, open a [sanitized usage report](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml)
with the rule ID, short redacted excerpt, command, and expected result. Do not
attach the original log.

## What success looks like

You can explain which findings are useful, which are noise, and what confidence
level your team is comfortable acting on. If that answer is not clear yet,
keep the integration advisory and revisit it after more representative,
sanitized failures.
