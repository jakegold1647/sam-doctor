# CI recipes

This page collects the smallest working shape for the environments people
already use with SAM Doctor. Every example is credential-free until you replace
the sanitized fixture with your own approved deployment log.

If you are trying the project for the first time, start with the
[first-deployment pilot](adoption-pilot.md). Keep the diagnostic advisory until
you have reviewed a few real, redacted failures.

## A known result to verify locally

The tracked OIDC sample should produce one finding with the stable rule ID
`github.oidc.assume-role-rejected`:

~~~bash
sam-doctor diagnose examples/oidc-assume-role-failure.txt --format markdown
~~~

The no-match case should say that no supported pattern was found:

~~~bash
printf '%s\n' 'deployment finished with status 0' | sam-doctor diagnose - --format markdown
~~~

Review the output before sharing it. The tool redacts common identifiers, but
redaction is not a substitute for checking the excerpt yourself.

## GitHub Actions

Use the repository's [two-phase workflow](../examples/github-actions-workflow-two-phase-gating.yml)
when you want a manual pilot and a separate strict mode:

~~~yaml
- name: Diagnose deployment log
  if: always()
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
    fail-on-findings: false
~~~

Keep `if: always()` on a diagnostic step that follows a deploy. It should still
run when the deploy fails, and it should preserve the deploy's original exit
status. The [GitHub Actions starter](../examples/github-actions-workflow.yml)
shows the capture step for `sam deploy`.

## Other CI systems

The checked-in starter files keep diagnosis advisory and return the deployment
status unchanged. Copy one, replace the marked deploy command, then choose the
same format your team uses for sharing:

- [GitLab CI](../examples/gitlab-ci-sam-doctor.yml) — use Markdown for a job artifact or
  JSON for a later script.
- [CircleCI](../examples/circleci-sam-doctor.yml) — save the report beside the
  deployment log in the workspace.
- [Azure Pipelines](../examples/azure-pipelines-sam-doctor.yml) — publish the
  reviewed report as a pipeline artifact.
- [Bitbucket Pipelines](../examples/bitbucket-pipelines-sam-doctor.yml) — keep the
  log and report in the step artifacts.

For AWS CDK or direct CloudFormation commands, use the matching
[GitHub Actions starters](../examples/README.md#github-actions-starters) as a
reference for capture and adapt the same two commands to your runner:

~~~bash
set -o pipefail
cdk deploy --all --require-approval never 2>&1 | tee deployment.log
deploy_status=${PIPESTATUS[0]}
sam-doctor diagnose deployment.log --format markdown
exit "${deploy_status}"
~~~

The equivalent direct CloudFormation command is
`aws cloudformation deploy`. The diagnosis is a report about the text it read;
it does not inspect or change the stack.

## Choosing an output

| Where the report goes | Command |
| --- | --- |
| Terminal or ticket draft | `sam-doctor diagnose deployment.log --format markdown` |
| Script or later CI step | `sam-doctor diagnose deployment.log --format json --output diagnosis.json` |
| GitHub workflow annotations | `sam-doctor diagnose deployment.log --format github` |
| Several logs in one run | `sam-doctor batch logs/ --format json` |

Do not enable `--fail-on-findings` just because the first run found something.
Use the [pilot checklist](adoption-pilot.md) to compare expected, missed, and
unclear findings first.

## Safe sharing and feedback

Before posting a result:

1. remove account IDs, ARNs, request IDs, credentials, tokens, private paths,
   and customer names from the input;
2. include the rule ID, the short redacted excerpt, the command, and what you
   expected to happen; and
3. say whether the suggested verification was read-only and useful.

Use the [usage feedback form](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml)
for a confusing or missed result. For changes to the project, read the
[contributor guide](../CONTRIBUTING.md) and [contributor quickstart](contributor-quickstart.md)
before opening an issue or PR.
