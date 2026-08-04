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

If an entry links to an existing issue, comment there and ask to be assigned.
Otherwise, open a [rule request issue](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)
titled `Rule request: <title below>`, mention that it comes from this roadmap,
and say you would like to be assigned. Check the
[open rule requests](https://github.com/jakegold1647/sam-doctor/issues?q=is%3Aissue+is%3Aopen+%22Rule+request%22)
first so nothing gets duplicated.

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

**Status:** open for a contributor — tracked in
[issue #20](https://github.com/jakegold1647/sam-doctor/issues/20); comment
there to claim it rather than opening a new issue.

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

## 5. The deploy bucket denied access to the packaged artifacts

**Status:** open for a contributor.

**Failure family.** `sam deploy` fails talking to the artifact bucket: the
upload is rejected, or CloudFormation cannot read the uploaded template or
zip back from S3. Common causes are a bucket owned by another account, a
bucket policy or Block Public Access change, SSE-KMS on the bucket without
matching key permissions, or a `samconfig.toml` pointing at a bucket in the
wrong Region.

**Sanitized signal lines.**

```text
Error: Failed to create changeset for the stack: my-app, An error occurred (ValidationError) when calling the CreateChangeSet operation: S3 error: Access Denied
```

```text
Error uploading to my-deploy-bucket: An error occurred (AccessDenied) when calling the PutObject operation: Access Denied (Service: S3, Status Code: 403)
```

**Pattern hints.** Match `S3 error: Access Denied` and S3-scoped
`AccessDenied ... (PutObject|GetObject|HeadObject)` wording. Distinguish the
upload direction (the CLI writing to the bucket) from the readback direction
(CloudFormation fetching the template), because the fix differs. This will
need `suppressed_by` wiring so it wins over the generic access-denied rule
*and* the two specific denial rules (explicit deny / no policy allows) when
the denied service is the artifact bucket.

**Nearby non-matches to test.** `Uploading to my-bucket/artifact.zip (100%)`
progress output; an `AccessDenied` for a non-S3 service must keep producing
the IAM denial findings, not this one.

**Safe verification steps to include.** `aws s3api head-object` against the
reported key to separate upload from readback failures; `aws s3api
get-bucket-location` to catch a wrong-Region `s3_bucket` in `samconfig.toml`;
`aws s3api get-bucket-encryption` to spot SSE-KMS buckets that also need key
permissions; confirm which account owns the bucket before changing any
policy.

**Documentation link.**
<https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html>

**Suggested confidence.** high.

---

## 6. The stack is stuck in a terminal rollback state

**Status:** open for a contributor.

**Failure family.** Every deploy fails immediately because the stack sits in
`ROLLBACK_COMPLETE` (first creation failed; the stack can only be deleted) or
`UPDATE_ROLLBACK_FAILED` (a rollback itself failed and must be continued or
skipped past). No template change can fix it until the state is cleared.

**Sanitized signal lines.**

```text
An error occurred (ValidationError) when calling the CreateChangeSet operation: Stack:arn:aws:cloudformation:us-east-1:123456789012:stack/my-app/abc is in ROLLBACK_COMPLETE state and can not be updated.
```

```text
Stack my-app is in UPDATE_ROLLBACK_FAILED state and can not be updated.
```

**Pattern hints.** Match `in ROLLBACK_COMPLETE state` and
`in UPDATE_ROLLBACK_FAILED state`. Do **not** match the `*_IN_PROGRESS`
states — those belong to roadmap entry 1 (concurrent operation), and plain
`ROLLBACK_IN_PROGRESS` progress events must stay unmatched.

**Nearby non-matches to test.** A log where `ROLLBACK_COMPLETE` appears as a
final status event without the "can not be updated" refusal.

**Safe verification steps to include.** For `ROLLBACK_COMPLETE`: read the
original `CREATE_FAILED` events first (`aws cloudformation
describe-stack-events`), fix that cause, then delete and recreate the stack —
warn about stateful resources before deleting. For `UPDATE_ROLLBACK_FAILED`:
`aws cloudformation continue-update-rollback`, with `--resources-to-skip`
only for resources that genuinely cannot roll back.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html#troubleshooting-errors-update-rollback-failed>

**Suggested confidence.** high.

---

## 7. The template failed SAM or CloudFormation schema validation

**Status:** open for a contributor.

**Failure family.** The deploy dies before any resource is created:
`InvalidSamDocumentException`, `InvalidResourceException`, or an unsupported /
unknown property on a resource type. Frequent causes are indentation mistakes,
properties on the wrong nesting level, or a missing
`Transform: AWS::Serverless-2016-10-31` line.

**Sanitized signal lines.**

```text
Error: Failed to create changeset for the stack: my-app, ex: Waiter ChangeSetCreateComplete failed: Waiter encountered a terminal failure state: For expression "Status" we matched expected path: "FAILED" Status: FAILED. Reason: Invalid Serverless Application Specification document. Number of errors found: 1. Resource with id [HelloFunction] is invalid. property Handler not defined for resource of type AWS::Serverless::StateMachine
```

```text
InvalidSamDocumentException: Encountered unsupported property MemorySize
```

**Pattern hints.** Match `InvalidSamDocumentException`,
`InvalidResourceException`, `property .* not defined for resource of type`,
and `Encountered unsupported property`. **Check overlap first:** the catalog
already has "A SAM template property is not valid for its resource type" —
read its patterns and either extend that rule or scope the new one to the
exception names it does not match, with suppression wiring so exactly one
finding fires per log.

**Nearby non-matches to test.** A benign `sam validate` success line and a
`ValidationError` about a missing parameter value.

**Safe verification steps to include.** Run `sam validate --lint` (cfn-lint
rules) locally and in CI before deploying; report the exact resource id and
property path from the error; confirm the template keeps its `Transform`
line when SAM resource types are used.

**Documentation link.**
<https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-validate.html>

**Suggested confidence.** high.

---

## 8. The deployment ran with invalid or wrong-account AWS credentials

**Status:** open for a contributor.

**Failure family.** The request never passed authentication: the security
token is invalid (not merely expired), or the access key belongs to no known
account (`UnrecognizedClientException`). Typical causes are stale `AWS_*`
environment variables overriding the intended profile, credentials for the
wrong account, or a region configured only under one `samconfig.toml`
section.

**Sanitized signal lines.**

```text
An error occurred (UnrecognizedClientException) when calling the CreateChangeSet operation: The security token included in the request is invalid.
```

```text
Error: The security token included in the request is invalid
```

**Pattern hints.** Match `security token included in the request is invalid`
and `UnrecognizedClientException`. The existing expired-credentials rule owns
`is expired` and `ExpiredToken` — keep the boundary clean with tests in both
directions (invalid ≠ expired), and add suppression so only the more precise
rule fires.

**Nearby non-matches to test.** An `ExpiredToken` log (must keep producing
the expired-credentials finding) and a successful `sts get-caller-identity`
debug line.

**Safe verification steps to include.** `aws configure list` in the failing
environment to see which source supplied each credential value; check for
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` environment
variables overriding the profile; confirm the intended account with `aws sts
get-caller-identity` once credentials are corrected.

**Documentation link.**
<https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html>

**Suggested confidence.** high.

---

## 9. CloudFormation refused the deployment for a missing capability

**Status:** already covered — no contribution needed.

The shipped catalog already diagnoses this failure: the rule titled
"CloudFormation needs an explicit capability acknowledgement" matches
`InsufficientCapabilitiesException` / `Requires capabilities` and walks
through `CAPABILITY_IAM`, `CAPABILITY_NAMED_IAM`, and
`CAPABILITY_AUTO_EXPAND` with review-first guidance. This entry is kept only
so the numbering of the other candidates stays stable; if you were eyeing
this one, pick another open entry above or below.

---

## 10. The Lambda deployment package is over a size limit

**Status:** open for a contributor.

**Failure family.** The function code (zip or unzipped) exceeds a Lambda
per-function size limit, so `UpdateFunctionCode`/`CreateFunction` fails.
**Scope note:** the *regional code storage* quota
(`CodeStorageExceededException`) is a different failure and already claimed
as [issue #24](https://github.com/jakegold1647/sam-doctor/issues/24) — this
entry must not match it, and needs a negative test proving that.

**Sanitized signal lines.**

```text
An error occurred (InvalidParameterValueException) when calling the UpdateFunctionCode operation: Unzipped size must be smaller than 262144000 bytes
```

```text
An error occurred (RequestEntityTooLargeException) when calling the UpdateFunctionCode operation: Request must be smaller than 70167211 bytes for the UpdateFunctionCode operation
```

**Pattern hints.** Match `Unzipped size must be smaller than` and
`Request must be smaller than .* bytes`. Exclude any line containing
`CodeStorageExceededException` or `Code storage limit exceeded`.

**Nearby non-matches to test.** A `Code storage limit exceeded` log (which
must keep producing the issue-24 finding once that lands, and must not
produce this one).

**Safe verification steps to include.** Measure the built artifact before
deploying; list the largest contents of the zip to find heavy dependencies;
move shared dependencies to a layer, trim dev/test dependencies from the
bundle, or switch the function to a container image (10 GB limit) when it is
genuinely large.

**Documentation link.**
<https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html>

**Suggested confidence.** high.

---

## 11. Tag-on-create was denied or a tag failed validation

**Status:** open for a contributor.

**Failure family.** The resource itself is allowed but tagging it is not:
the deploy principal lacks `iam:TagRole`/`TagResource`-style permissions, an
organization tag policy or CloudFormation hook rejects the tag set, or a tag
uses a reserved `aws:` prefix or fails the allowed-character pattern.

**Sanitized signal lines.**

```text
An error occurred (AccessDenied) when calling the CreateRole operation: User: arn:aws:iam::123456789012:user/deploy is not authorized to perform: iam:TagRole on resource: role my-app-role
```

```text
1 validation error detected: Value 'aws:team' at 'tags.1.member.key' failed to satisfy constraint: Member must satisfy regular expression pattern
```

**Pattern hints.** Match denials whose action is a `Tag*`/`UntagResource`
action, and tag-key validation wording (`tags.*failed to satisfy
constraint`, reserved `aws:` prefix errors). Tag-action denials currently
land in the IAM denial rules — this entry needs suppression wiring so the
tagging-specific finding wins on those lines, the same way the ECR rules
outrank the generic denial.

**Nearby non-matches to test.** A non-tag `AccessDenied` (must keep
producing the IAM denial findings) and a benign log line listing resource
tags.

**Safe verification steps to include.** Name the exact denied tag action and
resource from the error; grant tag-on-create permissions alongside the
create permissions for the deploy role; if a tag policy or hook rejected the
tag, report which organizational layer enforced it — do not suggest removing
governance hooks or tag policies to make a deploy pass.

**Documentation link.**
<https://docs.aws.amazon.com/IAM/latest/UserGuide/id_tags.html>

**Suggested confidence.** medium.

---

## Claimed / in progress

- Lambda code storage limit exceeded (`CodeStorageExceededException`) —
  [issue #24](https://github.com/jakegold1647/sam-doctor/issues/24), claimed by
  a contributor.

When an entry above is claimed, move it into this section with a link to its
issue so the roadmap stays honest about what is actually open.
