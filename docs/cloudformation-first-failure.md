# Find the first useful error in a CloudFormation rollback

A `ROLLBACK_IN_PROGRESS` or `ROLLBACK_COMPLETE` entry explains what the stack
is doing now. It usually does not explain why deployment first failed. Look for
the earliest relevant `CREATE_FAILED` or `UPDATE_FAILED` resource event and
preserve its status reason before retrying.

Try the bundled example:

```bash
sam-doctor demo --scenario cloudformation --format markdown
```

## Start with the resource event

CloudFormation stack events include a logical resource ID, resource type, status,
and status reason. The console and `describe-stack-events` command show the most
recent events first, so work backward within the failed operation until you find
the first failed resource event.

```bash
aws cloudformation describe-stack-events --stack-name my-stack
```

For the first relevant `CREATE_FAILED` or `UPDATE_FAILED`, record:

1. The logical resource ID.
2. The resource type.
3. The complete `ResourceStatusReason`.
4. The AWS Region and stack operation that produced the event.

Those details let you distinguish an IAM denial, invalid service request,
missing dependency, quota issue, or stabilization timeout. A later rollback
entry is useful context, but it is rarely the first clue to change.

## Use the console's root-cause support when it is available

CloudFormation can mark a failed event as the likely root cause in the stack's
**Events** tab. Review that event's status reason and, where available, the
linked CloudTrail event for more detail. Nested stacks do not support this
root-cause feature, so inspect their resource events directly.

## Keep a small evidence bundle

Before changing a template or policy, save a sanitized record containing:

```text
Logical resource: MyApiDeployment
Resource type: AWS::ApiGateway::Deployment
First failed status: CREATE_FAILED
Status reason: API Gateway deployment cannot be created because the stage already exists.
```

Then run the relevant error excerpt through SAM Doctor:

```bash
sam-doctor diagnose failure-excerpt.txt --format markdown
```

The report should help identify the failure family, but the resource status
reason remains the source of truth for the next investigation.

## Avoid these common detours

- Do not change IAM permissions solely because a rollback happened.
- Do not retry repeatedly before recording the first failure; later attempts can
  overwrite the most useful context.
- Do not share a full stack-event export without reviewing ARNs, account IDs,
  parameters, and resource identifiers.

## Official references

- [Determine the cause of a stack failure](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/determine-root-cause-for-stack-failures.html)
- [View CloudFormation stack events](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/view-stack-events.html)
