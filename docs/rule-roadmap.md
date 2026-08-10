# Rule roadmap: well-scoped diagnostics looking for a contributor

Each entry below records a real, recurring AWS deployment failure. Entries
marked **open** are not diagnosed yet; landed entries stay here so the evidence
and numbering remain useful. Every open entry is intentionally specified to the
level of [issue #24](https://github.com/jakegold1647/sam-doctor/issues/24) so one
contributor can land it in a focused PR with the rule, tests, fixture-registry
entry, error page, and changelog entry a complete contribution requires.

> **Two issues are reserved.**
> [#21](https://github.com/jakegold1647/sam-doctor/issues/21) (IAM policy size
> and attachment quotas) and
> [#25](https://github.com/jakegold1647/sam-doctor/issues/25) (API Gateway
> `TooManyRequestsException`) are held for first-time contributors. Please leave
> those two even if you could finish them in an afternoon - a project asking for
> contributors has to keep something worth contributing. Roadmap entries
> explicitly marked **open** are otherwise available.

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
   first so nothing gets duplicated. Do not claim #26, #27, or #33: their rules
   shipped already, although the tracker still shows the requests as open.

---

## 1. Another CloudFormation operation is already in progress on the stack

**Status:** landed — shipped as "Another CloudFormation operation is already
in progress on the stack" (see the v0.9.0 changelog entry). Kept here so
the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "SAM could not upload a build artifact
referenced by the template" (see the v0.9.0 changelog entry). Kept here so
the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "An S3 bucket name in the template is already
taken" (see the v0.9.0 changelog entry), closing
[issue #20](https://github.com/jakegold1647/sam-doctor/issues/20). Kept here so
the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "The template exceeds a CloudFormation size or
count quota" in commit `63ba18e` (see the v0.9.0 changelog entry), tracked
in [issue #46](https://github.com/jakegold1647/sam-doctor/issues/46). Kept here so
the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "The deployment bucket denied access to the
packaged artifacts" (see the v0.9.0 changelog entry), closing
[issue #28](https://github.com/jakegold1647/sam-doctor/issues/28). Kept here so
the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "Stack rollback itself failed and must be
continued or skipped" in v0.10.0. The existing
`ROLLBACK_COMPLETE` rule already covered the other half of this failure
family. Kept here so the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "The template failed SAM or CloudFormation
schema validation" (see the v0.9.0 changelog entry), closing
[issue #30](https://github.com/jakegold1647/sam-doctor/issues/30). Kept here
so the numbering of the other candidates stays stable.

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

**Status:** landed — shipped as "The deployment ran with invalid or
wrong-account AWS credentials" in v0.10.0, contributed in
[#55](https://github.com/jakegold1647/sam-doctor/pull/55) and closing
[issue #31](https://github.com/jakegold1647/sam-doctor/issues/31). Kept here
so the numbering of the other candidates stays stable.

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

**Status:** landed — contributed in
[#34](https://github.com/jakegold1647/sam-doctor/pull/34), closing
[issue #32](https://github.com/jakegold1647/sam-doctor/issues/32).

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

**Status:** landed — see the entry in
[What is still open](#what-is-still-open). Kept here because the specification
below is still the clearest description of the failure family, and because the
two rules it produced are a worked example of splitting one roadmap entry into
two rules when the fixes differ.

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

## 12. `Fn::GetAtt` has malformed parameters

**Status:** landed — shipped as "Fn::GetAtt parameters are malformed" (see
the Unreleased changelog). The signal came from the field
measurement; its single sighting likely understates a mistake anyone
hand-editing a template can make.

**Failure family.** CloudFormation rejects the change set before touching a
resource because an `Fn::GetAtt` was written with one parameter or three instead
of exactly two (logical id and attribute), or because either item is empty. The
short form `!GetAtt Thing.Attr` expands to the two-element list; writing
`!GetAtt Thing` or leaving either long-form list item blank produces this.

**Sanitized signal lines.**

```text
An error occurred (ValidationError) when calling the CreateChangeSet operation: Template error: every Fn::GetAtt object requires two non-empty parameters, the resource name and the resource attribute
```

**Pattern hints.** Anchor on `every Fn::GetAtt object requires two non-empty
parameters`. This is a template-authoring error, not a permissions or state
problem, so it should not be suppressed by - or suppress - the generic changeset
rule; check that the generic `sam.deploy.configuration-resolution-failed` finding
does not also fire on the same line, since its advice (`sam validate --lint`,
check `samconfig.toml`) is unrelated.

**Nearby non-matches to test.** A working `Fn::GetAtt` in ordinary template
output, and `Template error: instance of Fn::Select` (a different template error
that should keep whatever finding it produces today).

**Safe verification steps to include.** Search the template for `GetAtt`
occurrences and check each has exactly a logical id and an attribute; remember the
short form `!GetAtt Thing.Attr` and the long form
`Fn::GetAtt: [Thing, Attr]` are the same thing, and mixing them is the usual
cause.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html>

**Suggested confidence.** high.

---

## 13. A resource property was rejected for non-ASCII characters

**Status:** landed — shipped as "A resource property was rejected for
non-ASCII characters" (see the Unreleased changelog). Closes
[issue #62](https://github.com/jakegold1647/sam-doctor/issues/62). Kept here
so the numbering of the other candidates stays stable.

**Failure family.** A resource handler refuses a property value because it
contains characters outside ASCII - an em dash or an arrow pasted from a design
document into a `Description`, or a smart quote from a word processor. The
deployment fails on a value that looks completely ordinary on screen, which is
what makes it worth a rule: the character is usually invisible to the person
reading their own template.

**Sanitized signal lines.**

```text
Resource handler returned message: "Value (Pre-deploy Lambda → RDS plus VPC endpoints) for parameter GroupDescription is invalid. Character sets beyond ASCII are not supported"
```

**Pattern hints.** Anchor on `Character sets beyond ASCII are not supported`. The
parameter name in the message varies by resource type, so do not hard-code
`GroupDescription`; capture nothing and let the evidence line carry it. Add the
exact phrase to the generic resource-failure rule's per-line
`excluded_line_patterns`, rather than suppressing that rule for the whole log.

**Nearby non-matches to test.** A different `is invalid` parameter rejection (for
example a value that breaks a length limit), which must keep producing the
generic resource-failure finding rather than this one.

**Safe verification steps to include.** Name the offending property from the
evidence line, and suggest finding the character rather than retyping the value
blindly - `python -c "from pathlib import Path; p=Path('template.yaml'); print([n for n,s in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if not s.isascii()])"`
locates it. Worth saying that the fix is to replace the character with wording
allowed by the property's documentation, not to remove the description. For the
sample, use `to`, not `->`: the documented `GroupDescription` character set does
not include `>`.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-securitygroup.html>

**Suggested confidence.** high.

---

## 14. CloudFormation early validation rejected a property

**Status:** needs a sanitized reproduction, from the field measurement. The
sampled log did not include the full message, so collect a complete example before
writing the pattern. [Issue #63](https://github.com/jakegold1647/sam-doctor/issues/63)
has the requested evidence and acceptance criteria.

**Failure family.** CloudFormation now validates some properties before the
change set is created, and reports the failure as an
`AWS::EarlyValidation::PropertyValidation` pseudo-resource inside the usual
waiter error. Because the waiter wrapper is what surfaces, the generic changeset
rule fires and sends the reader to
`samconfig.toml` - the wrong place entirely, since the template is what was
rejected.

**Sanitized signal lines.**

```text
Waiter ChangeSetCreateComplete failed: AWS::EarlyValidation::PropertyValidation
```

**Pattern hints.** Anchor on the exact `AWS::EarlyValidation::PropertyValidation`
marker. Do not match the separate `AWS::EarlyValidation::ResourceExistenceCheck`
family. The interesting design question is precedence: this should claim the line
ahead of the generic changeset rule, which means
`excluded_line_patterns` on that rule rather than a whole-log suppression - see
the note on choosing between them in the contributing guide.

**Nearby non-matches to test.** An ordinary `Waiter ChangeSetCreateComplete
failed` with a `Status: FAILED` reason, which must keep its existing finding.

**Safe verification steps to include.** Use `aws cloudformation describe-events`
to inspect `LogicalResourceId`, `ResourceType`, `ValidationPath`, and
`ValidationStatusReason`, then compare that path with the submitted or generated
template. The generic change-set status reason alone may not contain those details.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/validate-stack-deployments.html>

**Suggested confidence.** medium - the sample is incomplete, so a narrow pattern
with an honest confidence beats a broad one.

---

## 15. `sam validate --lint` failed the template

**Status:** open, from the field measurement. Tracked in
[issue #64](https://github.com/jakegold1647/sam-doctor/issues/64) - claim it
there.

**Failure family.** A deploy pipeline runs `sam validate --lint` and cfn-lint
matches at least one rule. The SAM CLI reports only that linting failed; the
individual `E....`/`W....` rule codes appear on their own lines above it, so the
summary line alone tells the reader nothing actionable.

**Sanitized signal lines.**

```text
[[E1031: ToJsonString validation of parameters] (Fn::ToJsonString is not supported without 'AWS::LanguageExtensions' transform) matched 17]
Error: Linting failed. At least one linting rule was matched to the provided template.
```

**Pattern hints.** Match `Linting failed. At least one linting rule was matched`.
The useful work is in the explanation rather than the pattern: point the reader at
the `E`/`W` codes above the summary line, since those name the actual problem. A
rule that only repeats "linting failed" is not worth adding.

**Nearby non-matches to test.** A successful `sam validate` run, a standalone
cfn-lint code, `InvalidSamDocumentException`, and a named property mismatch.

**Safe verification steps to include.** Re-run `sam validate --lint` and read the
nearby rule codes; use the official cfn-lint rule catalog or `cfn-lint
--list-rules` rather than guessing from the message.

**Documentation link.**
<https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/validate-cfn-lint.html>

**Suggested confidence.** medium.

---

## 16. Lambda invoke targeted a missing function, alias, or version

**Status:** landed - the catalog now recognizes the exact Lambda `Invoke`
operation wrapper and points at a read-only target check.

**Failure family.** A post-deploy smoke test or integration step invokes a
function name or qualifier that is absent in the selected account and Region.
The usual causes are a stale function name, an alias or version that has not
finished publishing, or a command running against the wrong Region or account.

**Sanitized signal line.**

```text
An error occurred (ResourceNotFoundException) when calling the Invoke operation: Function not found
```

**Pattern hint.** Match the `ResourceNotFoundException` and `Invoke operation`
pair only. A missing resource from another Lambda operation is not enough to
claim that an invoke target is absent.

**Safe verification steps.** Read the exact function and qualifier with
`aws lambda get-function --function-name <function-name> --qualifier
<alias-or-version>` in the same account and Region; compare it with the stack
output or transformed template; wait for an `AutoPublishAlias` or version to
finish before retrying. Do not broaden IAM permissions for a target that does
not exist.

**Documentation link.**
<https://docs.aws.amazon.com/lambda/latest/api/API_Invoke.html>

**Suggested confidence.** medium.

---

## 37. Kubernetes could not set up a pod sandbox network

**Status:** landed - the catalog recognizes the `FailedCreatePodSandBox` /
`failed to setup network for sandbox` wrapper when no more specific EKS plugin
or nested cause is named.

**Failure family.** The kubelet reached the CNI network setup stage but the
plugin could not create the pod's network namespace. The wrapper is deliberately
low confidence: the useful cause is in the named plugin's node-level log, and a
bare sandbox event is not evidence of an AWS IAM problem.

**Sanitized signal line.**

```text
Warning FailedCreatePodSandBox: Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox "<sandbox-id>": plugin type="<cni-plugin>" failed (add): <nested cause>
```

**Pattern hint.** Match the kubelet sandbox/network stage, but let the existing
EKS `aws-cni`, network-policy-agent, EC2, and other nested-cause rules own a
more specific marker.

**Safe verification steps.** Preserve the pod, namespace, node, timestamp,
`plugin type`, and nested message. Inspect that CNI plugin's DaemonSet or host
log at the same time; on EKS, start with `aws-node` and `ipamd`. Only change IAM
when the nested evidence explicitly names a denied AWS action.

**Documentation link.**
<https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/network-plugins/>

**Suggested confidence.** low.

---

## 17. CloudFormation could not resolve a resource dependency

**Status:** landed - the catalog now recognizes the exact template-format error
and names the logical-ID checks that resolve it.

**Failure family.** A change set references a logical ID that is misspelled,
missing, or outside the current template scope. The reference may be in
`Ref`, `Fn::GetAtt`, `DependsOn`, or a substitution, and CloudFormation rejects
the template before it provisions a resource.

**Sanitized signal line.**

```text
Template format error: Unresolved resource dependencies [Environment] in the Resources block of the template
```

**Pattern hint.** Anchor on `Template format error: Unresolved resource
dependencies`; the bracketed logical IDs vary by template and should remain in
the redacted evidence rather than in the pattern.

**Safe verification steps.** Compare every bracketed name with the exact
`Resources` and `Parameters` logical IDs in the submitted or SAM-transformed
template. Check `Ref`, `Fn::GetAtt`, `DependsOn`, and substitutions for case
and scope, then run `sam validate --lint` or `cfn-lint` against the exact file
the deploy submits.

**Documentation link.**
<https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-anatomy.html>

**Suggested confidence.** high.

---

## 18. ECS Exec could not start its managed agent

**Status:** landed - the catalog now recognizes both the managed-agent startup
error and the `ExecuteCommand` wrapper that reports the same condition.

**Failure family.** A task was launched without ECS Exec enabled, or the
managed SSM agent could not start because the task role, SSM messaging path,
network, agent version, or container filesystem does not satisfy the Exec
prerequisites. Existing tasks must be replaced after launch-time settings
change.

**Sanitized signal lines.**

```text
CannotStartManagedAgentError: failed to start managed agent inside container
```

```text
An error occurred (InvalidParameterException) when calling the ExecuteCommand operation: The execute command failed because execute command was not enabled when the task was run or the execute command agent isn't running.
```

**Pattern hint.** Match the explicit `CannotStartManagedAgentError` or the
full ECS `ExecuteCommand` agent-not-running wording. Do not claim that every
`InvalidParameterException` is an ECS Exec failure.

**Safe verification steps.** Read `enableExecuteCommand` and the
`ExecuteCommandAgent` `lastStatus` and reason with
`aws ecs describe-tasks --cluster <cluster> --tasks <task>`. Then check the
task role's `ssmmessages` permissions and network path, and confirm the task
filesystem is writable; ECS Exec does not support `readonlyRootFilesystem`.
Launch a new task after changing the task definition.

**Documentation link.**
<https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-exec.html>

**Suggested confidence.** medium.

---

## 19. Bedrock model use-case details have not been submitted

**Status:** landed - the catalog now recognizes the Bedrock account-level
first-use access marker and keeps it separate from a missing model ID.

**Failure family.** A post-deploy smoke test or application call reaches Amazon
Bedrock, but the account has not submitted the model provider's required
first-use details. Bedrock may report this as `ResourceNotFoundException` even
though the model is listed, so treating it as an absent CloudFormation resource
leads to the wrong fix.

**Sanitized signal line.**

```text
An error occurred (ResourceNotFoundException) when calling the ConverseStream operation: Model use case details have not been submitted for this account.
```

**Pattern hint.** Match the exact `Model use case details have not been
submitted for this account` marker, whether the surrounding client formats it as
`ResourceNotFoundException`, `API Error: 404`, or a plain Bedrock return line.
Do not turn every Bedrock `ResourceNotFoundException` into an access-form
diagnosis; an unknown model ID needs a different check.

**Safe verification steps.** Confirm the caller's account, Region, and model ID,
then open Bedrock model access in that same account. For Anthropic models,
complete the Anthropic use-case details form and wait for the access state to
update before retrying. Do not delete the stack or broaden IAM permissions based
on this marker alone.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html>

**Suggested confidence.** medium.

---

## 20. Bedrock could not resolve the foundation model identifier

**Status:** landed - the catalog now recognizes Bedrock's exact unresolved-model
marker and points at the current catalog, Region, endpoint, and API checks.

**Failure family.** A Bedrock runtime call reaches the service, but the supplied
model identifier cannot be resolved at that endpoint. A retired model version,
wrong Region, missing inference-profile prefix, or unsupported API can all look
like a generic `ResourceNotFoundException` until the full message is read.

**Sanitized signal line.**

```text
An error occurred (ResourceNotFoundException) when calling the InvokeModelWithResponseStream operation: Could not resolve the foundation model from the provided model identifier.
```

**Pattern hint.** Anchor on the exact `Could not resolve the foundation model
from the provided model identifier` marker. Do not turn every Bedrock
`ResourceNotFoundException` into a model-ID diagnosis; the account first-use
form and other missing-resource messages need different checks.

**Safe verification steps.** Record the exact model ID and Region, compare them
with the current Bedrock catalog and the model's supported API, then use the
correct base-model ID, inference-profile ID, provisioned-model ARN, or custom
model identifier for that hosting mode. Check the model lifecycle page if the
configured version has been retired.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/userguide/models.html>

**Suggested confidence.** medium.

---

## 21. Bedrock rejected an empty system prompt

**Status:** landed - the catalog now recognizes Botocore's minimum-length
marker for an empty Converse system content block.

**Failure family.** An integration or post-deploy smoke test builds a Converse
request with `system: [{"text": ""}]`. Botocore rejects it before the request
reaches Bedrock because `SystemContentBlock.text` has a minimum length of one;
the right fix is to omit the field when there is no system instruction.

**Sanitized signal line.**

```text
ParamValidationError: Invalid length for parameter system[0].text, value: 0, valid min length: 1
```

**Pattern hint.** Anchor on `Invalid length for parameter system[N].text`, not
on every `ParamValidationError`: tool descriptions and other request fields can
have different fixes.

**Safe verification steps.** Inspect the request builder and omit the entire
`system` field when the generated prompt is empty or whitespace-only. Preserve
non-empty system instructions, validate the serialized payload, and retry before
investigating model access or IAM.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_SystemContentBlock.html>

**Suggested confidence.** medium.

---

## 22. AWS rejected an unknown or invalid API action

**Status:** landed - the catalog now recognizes AWS `UnknownAction` and
`InvalidAction` responses that identify the rejected operation.

**Failure family.** A CLI, SDK, or emulator sends an operation the selected
endpoint does not recognize. The cause can be a misspelled operation, stale API
version or SDK, wrong Region or endpoint, or missing emulator support; the error
does not by itself indicate an IAM denial.

**Sanitized signal line.**

```text
An error occurred (UnknownAction) when calling the GetTemplateSummary operation: Action is not supported
```

**Pattern hint.** Anchor on `UnknownAction` or `InvalidAction` paired with
`when calling`; do not broaden this to every `InvalidAction` in prose.

**Safe verification steps.** Read the operation and endpoint from the exact
line, compare them with the current service API and selected Region, update the
CLI or SDK if needed, and confirm that a local emulator implements the action.
Correct the request and retry before changing IAM permissions.

**Documentation link.**
<https://docs.aws.amazon.com/ec2/latest/devguide/errors-overview.html>

**Suggested confidence.** low.

---

## 23. AWS endpoint does not implement the requested action

**Status:** landed - the catalog now recognizes `NotImplemented` paired with
`when calling` an AWS operation.

**Failure family.** A service endpoint, proxy, stale client, or local emulator
returns `NotImplemented` for an operation or request shape. The response may be
specific to that endpoint or compatibility layer; it does not prove that AWS
lacks the operation everywhere and is not an IAM denial.

**Sanitized signal line.**

```text
An error occurred (NotImplemented) when calling the ListSchedules operation: operation is not implemented
```

**Pattern hint.** Require both the `NotImplemented` marker and `when calling`
within the same line; do not match status prose or a report field by itself.

**Safe verification steps.** Preserve the operation, service, endpoint, Region,
and HTTP status. Compare the operation with the current API reference, then
check the SDK or CLI version and any proxy or emulator implementation. Retry
against the intended endpoint after correcting compatibility before changing IAM.

**Documentation link.**
<https://docs.aws.amazon.com/scheduler/latest/APIReference/API_ListSchedules.html>

**Suggested confidence.** low.

---

## 24. AWS could not identify the service for an operation

**Status:** landed - the catalog now recognizes `UnknownService` paired with
`when calling` an AWS operation.

**Failure family.** A custom endpoint, proxy, emulator, or client protocol sends
an operation to a service target that is not registered at that endpoint. A stale
service model or wrong endpoint can produce the same AWS-shaped response; this
does not establish an IAM denial or prove that AWS lacks the service.

**Sanitized signal line.**

```text
An error occurred (UnknownService) when calling the PutMetricData operation: Unknown service target
```

**Pattern hint.** Require both `UnknownService` and `when calling` on the same
line; do not match telemetry labels such as `aws.local.service=UnknownService`.

**Safe verification steps.** Preserve the service, operation, endpoint URL,
Region, SDK or CLI version, protocol target, and HTTP status. Confirm that the
endpoint is intended for the service and that any proxy or emulator registers
the service and wire protocol. Retry against the intended AWS endpoint or update
the client/emulator before changing IAM.

**Documentation link.**
<https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_PutMetricData.html>

**Suggested confidence.** low.

---

## 25. The deployment could not read the STS caller identity

**Status:** landed - the catalog now recognizes the `Error: reading STS Caller
Identity` wrapper and preserves the nested-cause handoff.

**Failure family.** A deployment or provider failed while calling STS
`GetCallerIdentity`. The wrapper is not the root cause: the nested response may
identify an endpoint, Region, signing, network, profile, or credential-source
mismatch. It does not by itself show that `sts:GetCallerIdentity` permission is
missing.

**Sanitized signal line.**

```text
Error: reading STS Caller Identity
operation error STS: GetCallerIdentity, https response error StatusCode: 403, api error SignatureDoesNotMatch: Credential should be scoped to a valid region.
```

**Pattern hint.** Match the wrapper or the explicit STS `GetCallerIdentity`
operation, then inspect the nested response; do not match generic prose about a
caller identity.

**Safe verification steps.** Preserve the nested HTTP status, endpoint, Region,
profile or role, and error code. In the same environment run
`aws sts get-caller-identity --region <region>` with the same credential source,
then correct the endpoint, Region, signing, network, profile, or credentials
shown by the nested cause. Do not add an IAM allow for this read-only check.

**Documentation link.**
<https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html>

**Suggested confidence.** low.

---

## 26. AWS Glue rejected a catalog database rename

**Status:** landed - the catalog now recognizes the exact
`Database cannot be renamed` marker from Glue `UpdateDatabase`.

**Failure family.** Glue treats the catalog database name as its identity. An
`UpdateDatabase` request may change supported metadata fields, but
`DatabaseInput.Name` must remain the existing database name. A real rename
requires a replacement database and migration of its tables and consumers.

**Sanitized signal line.**

```text
An error occurred (InvalidInputException) when calling the UpdateDatabase operation: Database cannot be renamed
```

**Pattern hint.** Match the exact `Database cannot be renamed` marker; do not
turn every `InvalidInputException` from Glue into a rename diagnosis.

**Safe verification steps.** Read the current definition with
`aws glue get-database --name <database-name>` in the same Region and CatalogId,
keep `DatabaseInput.Name` unchanged while updating other fields, and retry. If
the name must change, create a new database and move its tables and consumers
before removing the old one. This is a request validation error, not IAM.

**Documentation link.**
<https://docs.aws.amazon.com/glue/latest/webapi/API_UpdateDatabase.html>

**Suggested confidence.** high.

---

## 27. Cloud Control API operation did not complete

**Status:** landed - the catalog now recognizes the AWS SDK Go
`Service Operation Incomplete` wrapper and directs the handoff to the nested
Cloud Control `ProgressEvent`.

**Failure family.** Cloud Control API resource operations are asynchronous. An
SDK or provider waiter can stop with this wrapper while the actual cause lives
in `OperationStatus`, `StatusMessage`, `ErrorCode`, resource type, identifier,
or request token. The wrapper is not evidence of an IAM failure by itself.

**Sanitized signal line.**

```text
Error: AWS SDK Go Service Operation Incomplete
Waiting for Cloud Control API service CreateResource operation completion returned: waiter state transitioned to FAILED. StatusMessage: the resource handler rejected the request. ErrorCode: InvalidRequest
```

**Pattern hint.** Match the exact SDK wrapper, then preserve and diagnose the
nested ProgressEvent; do not infer a root cause from the wrapper alone.

**Safe verification steps.** Keep `OperationStatus`, `ErrorCode`,
`StatusMessage`, `TypeName`, identifier, Region, and `RequestToken`. When a
token is present, run `aws cloudcontrol get-resource-request-status
--request-token <token>` in the same account and Region. Follow the nested
handler, schema, service-role, or downstream-service cause before retrying.

**Documentation link.**
<https://docs.aws.amazon.com/cloudcontrolapi/latest/APIReference/API_GetResourceRequestStatus.html>

**Suggested confidence.** low.

---

## 28. EC2 could not create a network interface

**Status:** landed - the catalog now recognizes provider wrappers around the
EC2 `CreateNetworkInterface` operation and preserves the nested status and
error code.

**Failure family.** Terraform, a Kubernetes component, or another provider may
report only that it was creating an EC2 network interface when the API call
failed. The nested EC2 response distinguishes subnet address exhaustion,
security-group limits, missing `ec2:CreateNetworkInterface`, invalid request
parameters, and endpoint or emulator support. The wrapper alone is not a root
cause.

**Sanitized signal line.**

```text
Error: creating EC2 Network Interface: operation error EC2: CreateNetworkInterface, https response error StatusCode: 400, RequestID: request-id, api error InvalidParameterValue: There aren't sufficient free IPv4 addresses in the subnet
```

**Pattern hint.** Match the provider wrapper together with the explicit
`operation error EC2: CreateNetworkInterface` marker; do not turn every
`CreateNetworkInterface` API mention or generic EC2 error into this finding.

**Safe verification steps.** Preserve the nested HTTP status, request ID, error
code, Region, subnet, security groups, and request parameters. When the error
names subnet capacity, run `aws ec2 describe-subnets --subnet-ids <subnet-id>
--region <region>` and review `AvailableIpAddressCount`. When it names
`UnauthorizedOperation` or `AccessDenied`, inspect the least-privilege
`ec2:CreateNetworkInterface` grant; when it names `InvalidParameterValue`,
correct the request shape or quota named by the message. For custom endpoints
or emulators, verify that the operation is implemented before changing the
infrastructure configuration.

**Documentation link.**
<https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_CreateNetworkInterface.html>

**Suggested confidence.** low.

---

## 29. Bedrock rejected an empty `modelId`

**Status:** landed - the catalog now recognizes the runtime client's exact
serialization marker for an omitted InvokeModel identifier.

**Failure family.** An application selects the Bedrock model from an environment
variable, config file, or backend default, but the value reaches the SDK as an
empty string. The client rejects the request before inference, so this is a
request-shape problem rather than evidence of missing model access or IAM.

**Sanitized signal line.**

```text
operation error Bedrock Runtime: InvokeModel, serialization failed: serialization failed: input member modelId must not be empty
```

**Pattern hint.** Match the `InvokeModel` or `InvokeModelWithResponseStream`
operation together with `input member modelId must not be empty`; do not turn
generic model-not-found or validation errors into this request-builder finding.

**Safe verification steps.** Trace the environment variable, config key, and
backend selection that supplies `modelId`; correct missing names and empty
defaults. Set the exact base-model ID, inference-profile ID, provisioned-model
ARN, or custom-model ID supported in the target Region, then log only a
sanitized request shape before retrying. Investigate model access or IAM only
after a non-empty identifier reaches the SDK.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModel.html>

**Suggested confidence.** medium.

---

## 30. EKS could not create a pod sandbox through the VPC CNI

**Status:** landed - the catalog now recognizes the Kubernetes wrapper that
reports an `aws-cni` add failure while leaving the nested cause to the node's
`aws-node` or `ipamd` log.

**Failure family.** A Pod is stuck in `Pending` or `ContainerCreating` because
the Amazon VPC CNI could not set up its network namespace. The kubelet line does
not distinguish subnet or prefix exhaustion, ENI or instance limits, CNI IAM,
subnet selection, or an unhealthy add-on, so the safe handoff is to the matching
CNI log rather than a guessed infrastructure fix.

**Sanitized signal line.**

```text
Failed to create pod sandbox: rpc error: code = Unknown desc = failed to setup network for sandbox "pod-sandbox": plugin type="aws-cni" name="aws-cni" failed (add): add cmd: failed to assign an IP address to container
```

**Pattern hint.** Match `Failed to create pod sandbox` with `aws-cni` and a
following `failed` marker, or the specific `plugin type="aws-cni" ... failed`
line when a log formatter split the wrapper across lines. If the same log contains a complete
`operation error EC2: CreateNetworkInterface` response, the more specific EC2
network-interface rule should own that evidence instead.

**Safe verification steps.** Record the Pod, node, Availability Zone, and
timestamp, then inspect the matching `aws-node` DaemonSet or `ipamd` log. If the
nested message names unavailable IPs or prefixes, inspect the node subnet and
instance ENI/IP limits and review the VPC CNI prefix or secondary-IP mode. If it
names `UnauthorizedOperation` or `AccessDenied`, verify the VPC CNI or node
role's least-privilege EC2 actions; if `aws-node` is unhealthy, check the
DaemonSet, add-on version, and node readiness before changing workloads.

**Documentation links.**
<https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html>

<https://docs.aws.amazon.com/eks/latest/userguide/cni-increase-ip-addresses.html>

**Suggested confidence.** low.

---

## 31. Bedrock rejected a Claude request without `messages`

**Status:** landed - the catalog now recognizes Bedrock's model-specific
`ValidationException: messages: Field required` marker when it is tied to an
InvokeModel or Bedrock Runtime request.

**Failure family.** A caller selected an Anthropic Claude Messages API body but
omitted the required `messages` array, often because an OpenAI-style `prompt`
shape or an adapter for a different model was sent to `InvokeModel`. The error
is a request-shape or model/API compatibility problem, not a model-access or IAM
failure.

**Sanitized signal line.**

```text
failed to generate embedding: operation error Bedrock Runtime: InvokeModel, https response error StatusCode: 400, ValidationException: messages: Field required
```

**Pattern hint.** Match `messages: Field required` with an InvokeModel or
Bedrock `ValidationException` context. Do not turn a generic AWS
`ValidationException` or a different required field into this Claude body
diagnosis.

**Safe verification steps.** Confirm the selected model supports the Anthropic
Claude Messages API and inspect the serialized InvokeModel body. For Claude
Messages, include `anthropic_version` set to `bedrock-2023-05-31`, a positive
`max_tokens`, and a `messages` array whose turns contain `role` and `content`.
Do not send an OpenAI-style `prompt` body to a model expecting Messages fields;
if the model supports Converse, use its `messages` and `system` shape with the
matching operation. Log only sanitized field names and values before retrying.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-request-response.html>

**Suggested confidence.** medium.

---

## 32. Bedrock rejected a nested message content field

**Status:** landed - the catalog now recognizes an indexed missing-field path
such as `messages.1.content.0.thinking.signature: Field required`.

**Failure family.** A model-specific Anthropic Messages request contains a
content block with the wrong shape or a field dropped by an adapter. Bedrock's
indexed path identifies the conversation turn, content block, and nested field;
the correction is in the request body, not in model access or IAM.

**Sanitized signal lines.**

```text
botocore.errorfactory.ValidationException: An error occurred (ValidationException) when calling the InvokeModel operation: messages.0.content.1.image.source: Field required
ValidationException: The model returned the following errors: messages.1.content.0.thinking.signature: Field required
```

**Pattern hint.** Match `messages.N.content.N.<field>: Field required` with
numeric indexes and a nested field path. Do not broaden this to an unindexed
`messages: Field required` marker; that is the separate top-level request rule.

**Safe verification steps.** Use the indexed path to inspect the exact turn and
content block in the serialized request. Match the block type to the selected
model schema: text blocks need text, thinking blocks need their signed fields
when replayed, and image or document blocks need the required source object and
type. If an adapter converts between Anthropic Messages, Bedrock InvokeModel,
and Converse, log only sanitized content-block types and keys to find a dropped
or renamed field, then retry before changing access or IAM.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-request-response.html>

**Suggested confidence.** medium.

---

## 33. AWS CDK could not bundle an asset before deployment

**Status:** landed - the catalog now recognizes the CDK asset wrapper that names
the failed asset and its temporary bundle output directory.

**Failure family.** CDK builds local assets such as Lambda code before it can
finish synthesis or deploy the stack. Package-manager, compiler, permission, or
Docker failures are often wrapped in `Failed to bundle asset`, leaving the
underlying command as the useful evidence. Amplify Gen 2 and other CDK-backed
wrappers can surface the same asset-staging line.

**Sanitized signal line.**

```text
Failed to bundle asset amplify-app/function/Api/Code/Stage, bundle output is located at /tmp/cdk.out/bundling-temp-error: Error: esbuild exited with status 1
```

**Pattern hint.** Match `Failed to bundle asset` together with `bundle output is
located at`. The asset name alone is not enough, and the rule deliberately does
not guess whether the underlying failure is a dependency, compiler, permission,
or Docker problem. When the same log also contains `AssemblyError: Assembly
builder failed`, the asset finding owns the wrapper because it names the concrete
build stage.

**Safe verification steps.** Re-run `cdk synth --verbose` with the same app,
context, working directory, credentials, environment, and tool versions. Inspect
the first compiler or dependency error after the temporary `-error` path. For
Docker bundling, reproduce the exact image and command and verify that the runner
can read the asset input and write the output directory.

**Documentation link.**
<https://docs.aws.amazon.com/cdk/v2/guide/assets.html>

**Suggested confidence.** low.

---

## 34. A Bedrock model version reached end of life

**Status:** landed - the catalog now recognizes Bedrock's explicit
`This model version has reached the end of its life` response.

**Failure family.** Bedrock model versions move through Active, Legacy, and
End-of-Life states. Once a version reaches its end-of-life date, an invocation
fails with a `ResourceNotFoundException` even though the model ID was once valid.
The fix is to migrate the configured model, not to retry or change IAM.

**Sanitized signal line.**

```text
operation error Bedrock Runtime: InvokeModel, https response error StatusCode: 404, ResourceNotFoundException: This model version has reached the end of its life. Please refer to the AWS documentation for more details.
```

**Pattern hint.** Match the exact lifecycle marker. It is specific enough to
survive Botocore and Smithy wrappers that omit the `Bedrock Runtime` prefix;
generic missing model IDs and the first-use access form stay with their existing
rules.

**Safe verification steps.** Read the exact model ID and Region from the request,
then run `aws bedrock get-foundation-model --model-identifier <model-id>` and
inspect its lifecycle fields. Select an Active replacement supported by the same
Region and API, update the application or deployment configuration, and test its
request body before retrying. Bedrock does not migrate retired IDs automatically.

**Documentation link.**
<https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle.html>

**Suggested confidence.** high.

---

## 35. SAM build could not access its generated output directory

**Status:** landed - the catalog now recognizes permission errors naming
`.aws-sam/build` while keeping Git's tracked-file unlink errors unmatched.

**Failure family.** `sam build` writes transformed templates and packaged
artifacts under `.aws-sam/build`. A previous elevated run, another local user,
an editor or watcher, or antivirus can leave the generated directory locked or
owned by a different account. The failure happens before AWS receives a
deployment request, so IAM changes are unrelated.

**Sanitized signal lines.**

```text
sam build --debug failed: Error: [WinError 5] Access is denied: '.aws-sam\build'
```

```text
PermissionError: [Errno 13] Permission denied: '/workspace/.aws-sam/build'
```

**Pattern hint.** Match `PermissionError`, `Permission denied`, or `Access is
denied` with `.aws-sam/build`. Exclude `unable to unlink old` lines: those are
Git cleanup failures, not evidence that SAM itself could not build.

**Safe verification steps.** Close editors, file watchers, antivirus scans, and
other SAM processes, then rerun `sam build --debug`. Inspect ownership and
permissions with `icacls .aws-sam\build` on Windows or `ls -ld .aws-sam/build`
on Unix. After confirming source files are safe, move or remove only the
generated build directory and rebuild; do not delete source code or broaden AWS
permissions.

**Documentation link.**
<https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html>

**Suggested confidence.** medium.

---

## 36. EKS VPC CNI network-policy agent could not set up policy

**Status:** landed - the catalog recognizes the exact `failed to setup (default)
network policy` and `Network policy agent returned` markers and yields the generic
pod-sandbox wrapper when this stage is named.

**Failure family.** The VPC CNI network-policy agent failed while setting up a
pod's policy during sandbox creation. The useful evidence is in the
`aws-network-policy-agent` container and its node-level eBPF, veth, kernel, or
`PolicyEndpoint` messages, not in the application workload or IAM policy first.

**Sanitized signal line.**

```text
Failed to setup default network policy for Pod Name <pod> and NameSpace <ns>: GRPC returned - Network policy agent returned - <nil>
```

**Pattern hint.** Match the policy-agent stage markers, while keeping the generic
EKS CNI wrapper and nested EC2 `CreateNetworkInterface` rule separate.

**Safe verification steps.** Capture the pod, node, namespace, and timestamp;
inspect `kubectl -n kube-system logs daemonset/aws-node -c aws-network-policy-agent`;
then check the VPC CNI version and `enableNetworkPolicy` configuration, node
kernel/architecture support, and `PolicyEndpoint` resources. Preserve a transient
retry pair before changing policy rules or IAM.

**Documentation link.**
<https://docs.aws.amazon.com/eks/latest/userguide/network-policies-troubleshooting.html>

**Suggested confidence.** medium.

---

## What is still open

**Entries 13 to 15 are open.** They and the now-landed entry 12 came out of
`scripts/measure-field-detection.py`, which measures this catalog against
deployment logs real people pasted into public GitHub issues. They are failures
sam-doctor was handed and did not diagnose, rather than failures somebody expected
it to meet. Entry 14 in particular is worth reading before claiming — the sampled
log was truncated, so the first job is collecting a complete example.

The measurement prints every signature it missed, so a run of it is the fastest way
to find work that is definitely real. The latest follow-up run on 2026-08-10
diagnosed 430 of 446 excerpts (96%), with 16 misses after entry 37. It included dedicated
searches for SAM build permission markers, CDK assembly-wrapper and asset-bundling variants, Lambda `Invoke` target misses,
Bedrock first-use, model-identifier, end-of-life, empty-system-prompt, empty-model-id, and
missing-messages and nested message-content request-shape failures, ECS Exec
managed-agent failures, EKS VPC CNI pod-sandbox and network-policy-agent wrappers, bare Kubernetes pod-sandbox network wrappers, unknown or invalid AWS API actions, unimplemented AWS
API actions, unknown AWS services, STS caller-identity wrappers, Glue database
rename failures, and Cloud Control operation wrappers, plus the broader
change-set wording. Entry 28 adds the EC2 network-interface wrapper family
from a repeated public Terraform/provider failure shape. Entry 30 adds the
EKS VPC CNI pod-sandbox wrapper family from repeated public EKS and VPC CNI
failure reports, while yielding to the nested EC2 cause when it is present.
Entry 31 adds the model-specific Bedrock `messages: Field required` request
family from repeated public InvokeModel failures. Entry 32 adds the indexed
nested message-content field family from repeated Claude image, document, and
thinking-block validation failures.
That percentage is a moving sample,
not a release guarantee;
the misses that remain after entries 14 and 15 are mostly other tools' failures
(CDK, Terraform, CodeBuild) or the five held contributor requests that this project
leaves open for first-time contributors.

Entries 1 to 13 and 16 to 37 have landed. A fresh rule request from a real failure is
always welcome, and the
[open-rule-request search](https://github.com/jakegold1647/sam-doctor/issues?q=is%3Aissue+is%3Aopen+%22Rule+request%22)
is the available-work list. Five requests are ready for first-time contributors:
[#21](https://github.com/jakegold1647/sam-doctor/issues/21) (IAM policy size and
attachment quotas), [#25](https://github.com/jakegold1647/sam-doctor/issues/25)
(API Gateway `TooManyRequestsException`), and
[#64](https://github.com/jakegold1647/sam-doctor/issues/64)
(`sam validate --lint`),
[#65](https://github.com/jakegold1647/sam-doctor/issues/65) (deprecated Lambda
runtimes), and [#66](https://github.com/jakegold1647/sam-doctor/issues/66)
(CloudFormation stack-name collisions). They are labelled `good first issue`,
`status: ready`, and `mentor available`; please leave them for new contributors.

[#63](https://github.com/jakegold1647/sam-doctor/issues/63) is intentionally
`status: needs-repro`, so contribute a complete sanitized example there before
implementing a rule.

Nothing is currently claimed.

- Lambda code storage limit exceeded (`CodeStorageExceededException`) —
  landed in [#35](https://github.com/jakegold1647/sam-doctor/pull/35), closing
  [issue #24](https://github.com/jakegold1647/sam-doctor/issues/24).
- Tag-on-create denied, and a tag key or value failing validation (entry 11,
  [issue #33](https://github.com/jakegold1647/sam-doctor/issues/33)) — landed
  as **two** rules rather than one: `iam.tag.action-denied` and
  `cloudformation.tag.key-validation-failed`. The entry described a single
  family, but the two halves need different fixes — grant a tagging permission
  versus rename a tag key — and a finding that offers both next steps is
  weaker than two that each offer one. The suppression wiring the entry called
  for went only to the denial rule, per line rather than per log, so an
  unrelated denial in the same deployment still reports.

When an entry above is claimed, move it into this section with a link to its
issue so the roadmap stays honest about what is actually open.
