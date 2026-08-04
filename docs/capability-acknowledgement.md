# Fix `InsufficientCapabilities` in an AWS SAM deployment

If `sam deploy` ends with an error like this, CloudFormation found IAM or
another acknowledged capability in the template but the deployment did not
explicitly accept it:

```text
InsufficientCapabilitiesException: Requires capabilities : [CAPABILITY_IAM]
```

This is an acknowledgement gate, not proof that the deployment role lacks an
IAM permission. Review the resources and policies before accepting the change.

## Run SAM Doctor first

Save the smallest sanitized excerpt and run:

```bash
python -m pip install sam-doctor
sam-doctor diagnose failure-excerpt.txt --format markdown
```

Or use the bundled example:

```bash
sam-doctor demo --scenario capabilities --format markdown
```

SAM Doctor identifies the required acknowledgement and points you to the
capability named by the error. It does not inspect the AWS account or decide
whether the template is safe to deploy.

## Check the template before retrying

1. Identify the IAM or nested-application resources introduced by the template
   or change set.
2. Review their policies and names with the least-privilege change in mind.
3. Use `CAPABILITY_IAM` when the template creates IAM resources without custom
   names.
4. Use `CAPABILITY_NAMED_IAM` when IAM resources have custom names.
5. Use `CAPABILITY_AUTO_EXPAND` only when nested applications require it and
   the expanded application has been reviewed.

For a normal SAM deployment, the acknowledgement can be supplied explicitly:

```bash
sam deploy --capabilities CAPABILITY_IAM
```

If the template contains custom-named IAM resources, use the capability that
matches the error and the reviewed template:

```bash
sam deploy --capabilities CAPABILITY_NAMED_IAM
```

Do not add a capability blindly just to make the command continue. The
acknowledgement confirms that CloudFormation may create or modify resources that
can affect account permissions.

## What SAM Doctor does not prove

A capability finding does not prove that the IAM policy is correct, that the
caller is authorized to deploy, or that a resource will stabilize successfully.
After acknowledging the capability, inspect the next CloudFormation event if
the deployment fails again.

## Official references

- [SAM `deploy` capabilities](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html)
- [Acknowledge IAM resources in CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/control-access-with-iam.html)
- [Create IAM resources with CloudFormation](https://docs.aws.amazon.com/IAM/latest/UserGuide/creating-resources-with-cloudformation.html)