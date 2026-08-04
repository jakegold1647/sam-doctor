# Rule roadmap: well-scoped diagnostics looking for a contributor

Each entry below is a real, recurring AWS deployment failure that SAM Doctor
does not diagnose yet. Every entry is intentionally specified to the level of
[issue #24](https://github.com/jakegold1647/sam-doctor/issues/24) so that one
contributor can pick it up and land it in a single focused PR: one rule, one
positive/negative test pair, one changelog line.

Before starting:

1. Read [Contributing a diagnostic rule](contributing-a-diagnostic-rule.md) for
   the rule checklist and a worked end-to-end example.
2. Comment on (or open) the matching `rule_request` issue so the work is
   visibly claimed and nobody duplicates it.
3. Keep fixtures sanitized: no account IDs, ARNs, tokens, or production logs.

## How to claim one

Open a [rule request issue](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)
titled `Rule request: <title below>`, mention that it comes from this roadmap,
and say you would like to be assigned.

---

## 1. Another CloudFormation operation is already in progress on the stack

**Status:** open for a contributor.

**Failure family.** Two deployments race on the same stack — a teammate,
a second CI run, or a console operation — and CloudFormation rejects the new
one until the in-flight operation finishes.

**Sanitized signal lines.**

```text
Stack my-service-prod is in UPDATE_IN_PROGRESS state and can not be updated.
```

```text
An error occurred (OperationInProgressException) when calling the UpdateStack operation
```

**Pattern hints.** Match `is in (CREATE|UPDATE|DELETE)_IN_PROGRESS` plus
"can not be updated", and `OperationInProgressException`. Do **not** match
`ROLLBACK_IN_PROGRESS` or `UPDATE_ROLLBACK_IN_PROGRESS` — those already belong
to the rollback rules.

**Nearby non-matches to test.** A successful log that merely reports
`UPDATE_IN_PROGRESS` as a normal progress event followed by
`UPDATE_COMPLETE` should not produce this finding.

**Safe verification steps to include.** Check for a concurrent deployment
against the same stack and let it finish; `aws cloudformation
describe-stack-events --stack-name <stack>` is a read-only way to see the
in-flight operation; serialize CI deploys with a GitHub Actions `concurrency`
group keyed by stack name.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html>

**Suggested confidence.** high.

---

## 2. SAM could not upload a build artifact referenced by the template

**Status:** open for a contributor.

**Failure family.** `sam deploy`/`sam package` fails because a `CodeUri`,
`ContentUri`, or `DefinitionUri` path does not exist — usually `sam build` was
never run, the deploy ran from the wrong directory, or the source template was
deployed instead of `.aws-sam/build/template.yaml`.

**Sanitized signal lines.**

```text
Error: Unable to upload artifact HelloWorldFunction referenced by CodeUri parameter of HelloWorldFunction resource.
Parameter CodeUri of resource HelloWorldFunction refers to a file or folder that does not exist
```

**Pattern hints.** Match `Unable to upload artifact ... referenced by
(CodeUri|ContentUri|DefinitionUri)` and `refers to a file or folder that does
not exist`. The generic "AWS SAM deployment configuration or parameter
resolution failed" rule will need these added to its `suppressed_by` tuple so
the narrower finding wins.

**Nearby non-matches to test.** A successful upload line such as
`Uploading to my-bucket/artifact.zip (100%)` should not match.

**Safe verification steps to include.** Run `sam build` and deploy the built
template; confirm the CI job checks out the repository and runs build and
deploy in the same working directory; verify the referenced path exists in the
environment that runs the deploy.

**Documentation link.**
<https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html>

**Suggested confidence.** high.

---

## 3. S3 bucket name is already taken globally

**Status:** open for a contributor.

**Failure family.** A stack creates an `AWS::S3::Bucket` with an explicit
`BucketName` that another AWS account already owns; bucket names are globally
unique, so `CREATE_FAILED` reports `BucketAlreadyExists` (another account) or
`BucketAlreadyOwnedByYou` (a leftover bucket in the same account, often from a
half-deleted stack).

**Sanitized signal lines.**

```text
MyBucket CREATE_FAILED my-app-logs already exists (Service: S3, Status Code: 409, Error Code: BucketAlreadyExists)
```

**Pattern hints.** Match the `BucketAlreadyExists` and
`BucketAlreadyOwnedByYou` error codes. Distinguish this from the existing
"An S3 bucket name failed AWS validation" rule (`InvalidBucketName`), which is
about illegal names rather than taken names.

**Nearby non-matches to test.** `Creating the required S3 bucket...` progress
output and an `InvalidBucketName` log (which must keep producing the existing
validation finding, not this one).

**Safe verification steps to include.** Choose a globally unique name or let
CloudFormation generate one by omitting `BucketName`; for
`BucketAlreadyOwnedByYou`, check whether a previous stack left the bucket
behind before reusing the name.

**Documentation link.**
<https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html>

**Suggested confidence.** high.

---

## 4. CloudFormation template exceeds a size or count quota

**Status:** open for a contributor.

**Failure family.** Deployment fails validation because the template body,
parameter count, output count, or resource count exceeds a CloudFormation
quota (for example, a 51,200-byte template body passed directly instead of via
S3).

**Sanitized signal lines.**

```text
An error occurred (ValidationError) when calling the CreateChangeSet operation: 1 validation error detected: Value at 'templateBody' failed to satisfy constraint: Member must have length less than or equal to 51200
```

**Pattern hints.** Match the `templateBody ... length less than or equal to`
validation wording and the `Template format error: ... limit` family. Keep the
patterns anchored to template quota wording so ordinary validation errors do
not match.

**Nearby non-matches to test.** A generic `ValidationError` about a missing
parameter value.

**Safe verification steps to include.** Deploy the template through an S3
location (SAM does this automatically with a resolved bucket) instead of
passing the body inline; split very large stacks with nested stacks; review
the CloudFormation quotas page for the specific limit named in the error.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-limits.html>

**Suggested confidence.** medium.

---

## Claimed / in progress

- Lambda code storage limit exceeded (`CodeStorageExceededException`) —
  [issue #24](https://github.com/jakegold1647/sam-doctor/issues/24), claimed by
  a contributor.

When an entry above is claimed, move it into this section with a link to its
issue so the roadmap stays honest about what is actually open.
