#!/usr/bin/env python3
"""Objective quality gate for the diagnostic-rule fixture registry.

`docs/contributing-a-diagnostic-rule.md` asks every rule for a sanitized
positive fixture and a nearby non-match. `RULE_FIXTURES` below is the
inventory: one entry per stable rule id, each entry a positive log line that
must trigger the rule and a negative log line that must not. Keys are the
rule ids from `docs/stability.md` - unlike titles, ids never change, so a
reworded rule cannot silently orphan its fixtures.

Checks:

- the fixture's rule id still exists in the catalog
- both a positive and a negative example are present
- the positive example triggers its rule; the negative example does not
- neither example contains an account id, ARN, access key, or email address

The registry covers the whole catalog; `check_fixtures()` also fails when a
catalog rule has no fixture entry, so a new rule cannot land without one.

Exit code 0 when every fixture is clean, 1 when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor.diagnostics import diagnose, supported_rules


@dataclass(frozen=True)
class RuleFixture:
    """A minimal, sanitized positive and nearby-negative pair for one rule."""

    positive: str
    negative: str


# One entry per rule, keyed by stable rule id. A negative only has to avoid
# its own rule - a nearby-negative legitimately may trigger a sibling (the
# code-storage line is exactly the line the package-size rule must ignore).
RULE_FIXTURES: dict[str, RuleFixture] = {
    "github.oidc.token-request-denied": RuleFixture(
        positive="Unable to get ID Token: missing id-token: write permission",
        negative=(
            "The job requested id-token: write and received a token without "
            "incident."
        ),
    ),
    "github.oidc.assume-role-rejected": RuleFixture(
        positive="Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        negative="AssumeRoleWithWebIdentity request succeeded after a brief retry",
    ),
    "github.oidc.audience-mismatch": RuleFixture(
        positive="InvalidIdentityToken: Incorrect token audience",
        negative="OIDC token audience was accepted after a handled retry",
    ),
    "github.oidc.provider-missing": RuleFixture(
        positive="No OpenIDConnect provider found in your account",
        negative=(
            "The GitHub Actions OpenIDConnect provider was already registered "
            "in the account"
        ),
    ),
    "lambda.ecr-image.access-denied": RuleFixture(
        positive=(
            "Lambda does not have permission to access the ECR image. Check "
            "the ECR permissions."
        ),
        negative="Lambda pulled the ECR image and started the container runtime.",
    ),
    "codebuild.codeconnections.access-denied": RuleFixture(
        positive=(
            'SourceProject CREATE_FAILED AWS::CodeBuild::Project '
            'Resource handler returned message: "User is not authorized to '
            'access connection [REDACTED_ARN] (Service: AWSCodeBuild; Status Code: '
            '400; Error Code: OAuthProviderException; Request ID: request-id)"'
        ),
        negative=(
            "CodeBuild used the configured CodeConnections source and the project "
            "entered CREATE_COMPLETE"
        ),
    ),
    "s3.lifecycle.abort-multipart-tag-filter": RuleFixture(
        positive=(
            "MyBucket UPDATE_FAILED Resource handler returned message: "
            '"AbortIncompleteMultipartUpload cannot be specified with Tags. '
            '(Service: S3, Status Code: 400, Error Code: InvalidRequest)"'
        ),
        negative=(
            "S3 lifecycle rule with AbortIncompleteMultipartUpload and a key-prefix "
            "filter was accepted"
        ),
    ),
    "imagebuilder.recipe.version-already-exists": RuleFixture(
        positive=(
            "ImageRecipe CREATE_FAILED Resource handler returned message: "
            '"The following resource \'ImageRecipe\' already exists: \'recipe/1.1.0\' '
            '(HandlerErrorCode: AlreadyExists)"'
        ),
        negative=(
            "ImageRecipe version 1.1.1 was created successfully after the recipe "
            "content changed"
        ),
    ),
    "cloudformation.api.service-unavailable": RuleFixture(
        positive=(
            "An error occurred (ServiceNotAvailable) when calling the CreateStack "
            "operation: CloudFormation is temporarily unavailable"
        ),
        negative=(
            "An error occurred (Throttling) when calling the DescribeStacks "
            "operation: Rate exceeded"
        ),
    ),
    "cloudformation.deploy.wrapper-failed": RuleFixture(
        positive=(
            "Failed to create/update the stack. Run the following command to fetch "
            "the list of events leading up to the failure."
        ),
        negative="CloudFormation created and updated the stack successfully.",
    ),
    "cdk.synth.assembly-failed": RuleFixture(
        positive=(
            "[BackendBuildError] Caused by: [_AssemblyError] "
            "Assembly builder failed"
        ),
        negative="CDK synthesized the cloud assembly and wrote it to cdk.out.",
    ),
    "cdk.asset.bundling-failed": RuleFixture(
        positive=(
            "Failed to bundle asset amplify-app/function/Api/Code/Stage, "
            "bundle output is located at /tmp/cdk.out/bundling-temp-error: "
            "Error: esbuild exited with status 1"
        ),
        negative="CDK bundled the Lambda asset and wrote it to cdk.out.",
    ),
    "lambda.invoke.function-not-found": RuleFixture(
        positive=(
            "An error occurred (ResourceNotFoundException) when calling the Invoke "
            "operation: Function not found"
        ),
        negative=(
            "An error occurred (ResourceNotFoundException) when calling the "
            "GetFunction operation: Function not found"
        ),
    ),
    "bedrock.model-access.first-use-form-required": RuleFixture(
        positive=(
            "An error occurred (ResourceNotFoundException) when calling the "
            "ConverseStream operation: Model use case details have not been "
            "submitted for this account."
        ),
        negative=(
            "An error occurred (ResourceNotFoundException) when calling the "
            "ConverseStream operation: The requested model ID is not found."
        ),
    ),
    "bedrock.model-identifier.unresolved": RuleFixture(
        positive=(
            "An error occurred (ResourceNotFoundException) when calling the "
            "InvokeModelWithResponseStream operation: Could not resolve the "
            "foundation model from the provided model identifier."
        ),
        negative=(
            "An error occurred (ResourceNotFoundException) when calling the "
            "InvokeModel operation: The requested model ID is not found."
        ),
    ),
    "bedrock.model-lifecycle.end-of-life": RuleFixture(
        positive=(
            "operation error Bedrock Runtime: InvokeModel, https response error "
            "StatusCode: 404, ResourceNotFoundException: This model version has "
            "reached the end of its life."
        ),
        negative=(
            "operation error Bedrock Runtime: InvokeModel, https response error "
            "StatusCode: 404, ResourceNotFoundException: The requested model ID "
            "is not found."
        ),
    ),
    "bedrock.request.empty-system-prompt": RuleFixture(
        positive=(
            "ParamValidationError: Invalid length for parameter system[0].text, "
            "value: 0, valid min length: 1"
        ),
        negative=(
            "Parameter validation failed: Invalid length for parameter "
            "toolConfig.tools[0].toolSpec.description, value: 0, valid min length: 1"
        ),
    ),
    "bedrock.request.empty-model-id": RuleFixture(
        positive=(
            "operation error Bedrock Runtime: InvokeModel, serialization failed: "
            "serialization failed: input member modelId must not be empty"
        ),
        negative=(
            "An error occurred (ValidationException) when calling the InvokeModel "
            "operation: The provided model identifier is invalid."
        ),
    ),
    "bedrock.request.messages-required": RuleFixture(
        positive=(
            "operation error Bedrock Runtime: InvokeModel, https response error "
            "StatusCode: 400, ValidationException: messages: Field required"
        ),
        negative=(
            "operation error Bedrock Runtime: InvokeModel, ValidationException: "
            "content: Field required"
        ),
    ),
    "bedrock.request.message-content-field-required": RuleFixture(
        positive=(
            "ValidationException: The model returned the following errors: "
            "messages.1.content.0.thinking.signature: Field required"
        ),
        negative="ValidationException: messages: Field required",
    ),
    "aws.api.action-invalid": RuleFixture(
        positive=(
            "An error occurred (UnknownAction) when calling the "
            "GetTemplateSummary operation: Action is not supported"
        ),
        negative=(
            "An error occurred (AccessDeniedException) when calling the "
            "DescribeStacks operation: User is not authorized to perform this action"
        ),
    ),
    "aws.api.action-not-implemented": RuleFixture(
        positive=(
            "An error occurred (NotImplemented) when calling the "
            "ListSchedules operation: operation is not implemented"
        ),
        negative=(
            "The deployment status is NotImplemented in the report"
        ),
    ),
    "aws.api.service-unknown": RuleFixture(
        positive=(
            "An error occurred (UnknownService) when calling the "
            "PutMetricData operation: Unknown service target"
        ),
        negative="OpenTelemetry exported aws.local.service=UnknownService",
    ),
    "aws.credentials.caller-identity-unavailable": RuleFixture(
        positive="Error: reading STS Caller Identity",
        negative="The caller identity was recorded successfully",
    ),
    "ec2.network-interface.create-failed": RuleFixture(
        positive=(
            "Error: creating EC2 Network Interface: operation error EC2: "
            "CreateNetworkInterface, https response error StatusCode: 400, "
            "RequestID: request-id, api error InvalidParameterValue: There "
            "aren't sufficient free IPv4 addresses in the subnet"
        ),
        negative=(
            "An error occurred (InvalidParameterValue) when calling the "
            "CreateNetworkInterface operation: there aren't sufficient free "
            "IPv4 addresses in the subnet"
        ),
    ),
    "lambda.vpc.execution-role-network-interface-permission": RuleFixture(
        positive=(
            "MyFunction CREATE_FAILED: Resource handler returned message: "
            '"The provided execution role does not have permissions to call '
            "CreateNetworkInterface on EC2 (Service: Lambda, Status Code: 400, "
            "Error Code: InvalidParameterValueException)"
        ),
        negative=(
            "The provided execution role has permissions to call "
            "CreateNetworkInterface on EC2"
        ),
    ),
    "eks.network-policy.agent-failed": RuleFixture(
        positive=(
            "Failed to setup default network policy for Pod Name <pod> and "
            "NameSpace <ns>: GRPC returned - Network policy agent returned - <nil>"
        ),
        negative="The network policy agent completed setup for the pod successfully",
    ),
    "eks.vpc-cni.pod-sandbox-network-failed": RuleFixture(
        positive=(
            'Failed to create pod sandbox: plugin type="aws-cni" name="aws-cni" '
            "failed (add): failed to assign an IP address to container"
        ),
        negative=(
            'Failed to create pod sandbox: plugin type="calico" name="calico" '
            "failed (add): network unavailable"
        ),
    ),
    "kubernetes.pod-sandbox.network-setup-failed": RuleFixture(
        positive=(
            "Warning FailedCreatePodSandBox: Failed to create pod sandbox: "
            "rpc error: code = Unknown desc = failed to setup network for sandbox "
            '"sandbox-id": plugin type="calico" name="calico" failed (add): '
            "network unavailable"
        ),
        negative=(
            "The pod sandbox was created successfully and the CNI network is ready"
        ),
    ),
    "glue.database.rename-rejected": RuleFixture(
        positive=(
            "An error occurred (InvalidInputException) when calling the "
            "UpdateDatabase operation: Database cannot be renamed"
        ),
        negative=(
            "An error occurred (InvalidInputException) when calling the "
            "UpdateDatabase operation: Description is invalid"
        ),
    ),
    "cloudcontrol.operation.incomplete": RuleFixture(
        positive="Error: AWS SDK Go Service Operation Incomplete",
        negative="AWS SDK Go Service Operation completed successfully",
    ),
    "ecs.execute-command.agent-unavailable": RuleFixture(
        positive=(
            "CannotStartManagedAgentError: failed to start managed agent inside "
            "container: the execute command agent is not running"
        ),
        negative="ECS ExecuteCommandAgent lastStatus: RUNNING",
    ),
    "ecr.auth.login-failed": RuleFixture(
        positive=(
            'Error response from daemon: Head "https://registry.example.test/'
            'v2/sam-app/manifests/latest": no basic auth credentials'
        ),
        negative="Login Succeeded",
    ),
    "iam.deny.explicit": RuleFixture(
        positive=(
            "User is not authorized to perform: iam:CreateRole with an "
            "explicit deny in an identity-based policy"
        ),
        negative="The role was created after the explicit allow statement took effect",
    ),
    "iam.deny.implicit": RuleFixture(
        positive=(
            "User is not authorized to perform: iam:PassRole because no "
            "identity-based policy allows the iam:PassRole action"
        ),
        negative="The identity-based policy allows iam:PassRole, and the call proceeded",
    ),
    "iam.access-denied.generic": RuleFixture(
        positive="AccessDeniedException: action is not authorized",
        negative="The API call completed without an access denial",
    ),
    "iam.tag.action-denied": RuleFixture(
        positive=(
            "An error occurred (AccessDenied) when calling the CreateRole "
            "operation: User is not authorized to perform: iam:TagRole on "
            "resource: role my-app-role"
        ),
        # A denial on the create action itself, not the tag: it must keep
        # producing the IAM denial findings rather than this one.
        negative=(
            "User is not authorized to perform: iam:CreateRole on resource: "
            "role my-app-role"
        ),
    ),
    "cloudformation.tag.key-validation-failed": RuleFixture(
        positive=(
            "1 validation error detected: Value 'aws:team' at "
            "'tags.1.member.key' failed to satisfy constraint: Member must "
            "satisfy regular expression pattern"
        ),
        negative="Tags: Environment=prod, Team=platform, CostCenter=1234",
    ),
    "docker.registry.image-unavailable": RuleFixture(
        positive=(
            "Error response from daemon: pull access denied for myco/base, "
            "repository does not exist or may require 'docker login'"
        ),
        negative="Status: Downloaded newer image for myco/base:latest",
    ),
    "build.host.disk-full": RuleFixture(
        positive="failed to write layer: no space left on device",
        negative="Filesystem 58G used 21G available /home/runner",
    ),
    "ssm.parameter.resolution-failed": RuleFixture(
        positive="Parameters: [ssm:/my-app/prod/db-password] cannot be found.",
        # The pre-existing generic parameter wording must keep its own finding:
        # this rule targets SSM-specific shapes only.
        negative="Parameter 'Stage' must have values",
    ),
    "lambda.env-vars.kms-key-inaccessible": RuleFixture(
        positive=(
            "CREATE_FAILED  AWS::Lambda::Function  Worker  Lambda was unable "
            "to configure access to your environment variables because the KMS "
            "key is invalid for CreateGrant. Please check your KMS key "
            "settings. KMS Exception: InvalidArnException (Service: Lambda, "
            "Status Code: 400; Error Code: InvalidParameterValueException)"
        ),
        negative=(
            "UPDATE_FAILED AWS::Lambda::Function Worker Lambda was unable to "
            "configure your environment variables because the environment "
            "variables contain reserved keys"
        ),
    ),
    "s3.artifact-bucket.access-denied": RuleFixture(
        positive=(
            "Error: Failed to create changeset for the stack: my-app, An "
            "error occurred (ValidationError) when calling the "
            "CreateChangeSet operation: S3 error: Access Denied"
        ),
        negative="Uploading to my-bucket/artifact.zip (100%)",
    ),
    "aws.credentials.expired": RuleFixture(
        positive=(
            "An error occurred (ExpiredTokenException) when calling the "
            "AssumeRole operation: The security token included in the "
            "request is expired"
        ),
        negative="The security token included in the request is valid for another hour",
    ),
    "aws.credentials.invalid": RuleFixture(
        positive=(
            "An error occurred (UnrecognizedClientException) when calling "
            "the CreateChangeSet operation: The security token included in "
            "the request is invalid."
        ),
        negative="An error occurred (ExpiredTokenException) when calling the AssumeRole operation: The security token included in the request is expired",
    ),
    "cloudformation.api.throttled": RuleFixture(
        positive=(
            "ResourceStatusReason: Rate exceeded (Service: CloudFormation, "
            "Status Code: 400)"
        ),
        negative="The deployment completed under the API rate limits",
    ),
    "sam.template.invalid-property": RuleFixture(
        positive=(
            "property StageName: not defined for resource of type "
            "AWS::Serverless::Api"
        ),
        negative="SAM template property StageName is valid for AWS::Serverless::Api",
    ),
    "sam.template.schema-validation-failed": RuleFixture(
        positive="InvalidSamDocumentException: Encountered unsupported property MemorySize",
        negative="sam validate --lint completed with no errors",
    ),
    "cloudformation.template.getatt-parameters-invalid": RuleFixture(
        positive=(
            "Template error: every Fn::GetAtt object requires two non-empty "
            "parameters, the resource name and the resource attribute"
        ),
        negative="Template validation accepted Fn::GetAtt: [WorkerFunction, Arn]",
    ),
    "cloudformation.template.unresolved-dependency": RuleFixture(
        positive=(
            "Template format error: Unresolved resource dependencies "
            "[Environment] in the Resources block of the template"
        ),
        negative=(
            "Template format error: Resource dependencies were resolved before "
            "the change set was created"
        ),
    ),
    "cloudformation.template.circular-dependency": RuleFixture(
        positive=(
            "ValidationError: Circular dependency between resources: "
            "[ApiFunction, ApiPermission, Api]"
        ),
        negative=(
            "The template change removed the circular dependency between "
            "resources."
        ),
    ),
    "iam.trust-policy.resource-field-invalid": RuleFixture(
        positive="Has prohibited field Resource",
        negative="The trust policy passed validation with no prohibited fields",
    ),
    "lambda.code-signing.image-incompatible": RuleFixture(
        positive=(
            "Code signing is not supported for functions created with "
            "container images."
        ),
        negative="Code signing configuration attached to the zip-packaged function",
    ),
    "s3.bucket-name.invalid": RuleFixture(
        positive="The specified bucket is not valid. Error Code: InvalidBucketName",
        negative="Creating the required S3 bucket if one does not exist",
    ),
    "s3.bucket-name.already-taken": RuleFixture(
        positive=(
            "MyBucket CREATE_FAILED my-app-logs already exists (Service: S3, "
            "Status Code: 409, Error Code: BucketAlreadyExists)"
        ),
        negative="Creating the required S3 bucket if one does not exist",
    ),
    "cloudformation.lambda-layer.artifact-unreadable": RuleFixture(
        positive=(
            "Your access has been denied by S3, please make sure your "
            "request credentials have permission to GetObject for bucket "
            "layer-artifacts."
        ),
        negative="The layer artifact downloaded from S3 without error",
    ),
    "sam.build.docker-required": RuleFixture(
        positive=(
            "Error: Building image for HelloWorldFunction requires Docker. "
            "is Docker running?"
        ),
        negative="Docker daemon responded and the container build started",
    ),
    "sam.build.output-permission-denied": RuleFixture(
        positive=(
            "sam build --debug failed: Error: [WinError 5] Access is denied: "
            "'.aws-sam\\build'"
        ),
        negative=(
            "error: unable to unlink old 'infra/.aws-sam/build/template.yaml': "
            "Permission denied"
        ),
    ),
    "lambda.package.size-limit-exceeded": RuleFixture(
        positive=(
            "An error occurred (InvalidParameterValueException) when calling "
            "the UpdateFunctionCode operation: Unzipped size must be smaller "
            "than 262144000 bytes"
        ),
        # The regional code-storage quota is the failure this rule must NOT
        # claim - it belongs to lambda.code-storage.limit-exceeded.
        negative=(
            "An error occurred (CodeStorageExceededException) when calling "
            "the UpdateFunctionCode operation: Code storage limit exceeded."
        ),
    ),
    "apigateway.deployment.no-methods": RuleFixture(
        positive="The REST API doesn't contain any methods",
        negative="The REST API contains three methods and deployed cleanly",
    ),
    "apigateway.security-policy.endpoint-access-required": RuleFixture(
        positive=(
            'MyApi CREATE_FAILED: Resource handler returned message: "Endpoint '
            'access mode is required for the specified security policy (Service: '
            'ApiGateway, Status Code: 400)"'
        ),
        negative="API Gateway accepted the enhanced security policy with STRICT endpoint access mode",
    ),
    "cloudformation.resource.stabilization-timeout": RuleFixture(
        positive="Resource handler returned message: Exceeded attempts to wait",
        negative="The resource reached CREATE_COMPLETE within the expected window",
    ),
    "cloudformation.resource.create-update-failed": RuleFixture(
        positive="MyFunction CREATE_FAILED Resource handler returned message: denied",
        negative="MyFunction CREATE_COMPLETE AWS::Lambda::Function",
    ),
    "cloudformation.resource.property-non-ascii": RuleFixture(
        positive=(
            "AppSecurityGroup CREATE_FAILED AWS::EC2::SecurityGroup Resource "
            "handler returned message: Value for parameter GroupDescription "
            "is invalid. Character sets beyond ASCII are not supported"
        ),
        negative=(
            "AppSecurityGroup CREATE_FAILED AWS::EC2::SecurityGroup Resource "
            "handler returned message: Value for parameter GroupDescription "
            "is invalid because it exceeds the maximum length"
        ),
    ),
    "cloudformation.nested-stack.propagation-failed": RuleFixture(
        positive=(
            "CREATE_FAILED AWS::CloudFormation::Stack DatabaseStack Embedded "
            "stack was not successfully created: The following resource(s) "
            "failed to create: [DBSubnetGroup]."
        ),
        negative="DatabaseStack CREATE_FAILED Resource handler returned message: denied",
    ),
    "lambda.code-storage.limit-exceeded": RuleFixture(
        positive=(
            "An error occurred (CodeStorageExceededException) when calling "
            "the UpdateFunctionCode operation: Code storage limit exceeded."
        ),
        # The per-function size limit is the nearby failure this rule must
        # leave to lambda.package.size-limit-exceeded.
        negative=(
            "An error occurred (RequestEntityTooLargeException) when calling "
            "the UpdateFunctionCode operation: Request must be smaller than "
            "70167211 bytes for the UpdateFunctionCode operation"
        ),
    ),
    "lambda.concurrency.reserved-below-minimum": RuleFixture(
        positive=(
            "CREATE_FAILED AWS::Lambda::Function ApiFunction Specified "
            "ReservedConcurrentExecutions for function decreases account's "
            "UnreservedConcurrentExecution below its minimum value of [100]. "
            "(Service: Lambda, Status Code: 400; Error Code: "
            "InvalidParameterValueException)"
        ),
        # A same-exception, unrelated InvalidParameterValueException must not
        # trip this rule - it must anchor on the concurrency wording, not the
        # exception name.
        negative=(
            "An error occurred (InvalidParameterValueException) when calling "
            "the CreateFunction operation: Environment variable "
            "AWS_REGION is a reserved key"
        ),
    ),
    "cloudformation.stack.operation-in-progress": RuleFixture(
        positive="Stack my-service-prod is in UPDATE_IN_PROGRESS state and can not be updated.",
        negative="MyStack UPDATE_IN_PROGRESS followed by UPDATE_COMPLETE",
    ),
    "cloudformation.stack.failed-recreate-required": RuleFixture(
        positive="Stack: example is in ROLLBACK_COMPLETE state and can not be updated.",
        negative="Stack reached UPDATE_COMPLETE after the change set executed",
    ),
    "cloudformation.stack.update-rollback-failed": RuleFixture(
        positive="Stack my-app is in UPDATE_ROLLBACK_FAILED state and can not be updated.",
        negative="Stack my-app is in UPDATE_ROLLBACK_IN_PROGRESS state and can not be updated.",
    ),
    "cloudformation.stack.rollback-complete": RuleFixture(
        positive="Stack entered ROLLBACK_FAILED after a resource failure",
        negative="The deploy completed with every resource in service",
    ),
    "cloudformation.rollback.iam-role-delete-failed": RuleFixture(
        positive=(
            "AWS::CloudFormation::Stack ROLLBACK_FAILED ... The following "
            "resource(s) failed to delete: [IAMRoleDeployment]"
        ),
        negative="Rollback removed every provisional resource without error",
    ),
    "cloudformation.stack.termination-protection": RuleFixture(
        positive=(
            "An error occurred (ValidationError) when calling the "
            "DeleteStack operation: Stack my-app cannot be deleted while "
            "TerminationProtection is enabled"
        ),
        negative="Termination protection was disabled before the delete request",
    ),
    "cloudformation.stack.delete-failed": RuleFixture(
        positive=(
            "ArtifactBucket AWS::S3::Bucket DELETE_FAILED The bucket you "
            "tried to delete is not empty (Service: S3, Status Code: 409)"
        ),
        negative="DELETE_COMPLETE The stack and all resources were removed",
    ),
    "cloudformation.export.in-use": RuleFixture(
        positive="Export my-app-api-url cannot be updated as it is in use by consumer-stack",
        negative="The export value changed once no stack imported it",
    ),
    "cloudformation.export.not-found": RuleFixture(
        positive="No export named shared-vpc-id found",
        negative="The export named shared-vpc-id was found and imported successfully",
    ),
    "cloudformation.capabilities.required": RuleFixture(
        positive="InsufficientCapabilitiesException: Requires capabilities : [CAPABILITY_NAMED_IAM]",
        negative="Change set executed with the acknowledged capabilities",
    ),
    "cloudformation.template.quota-exceeded": RuleFixture(
        positive=(
            "Template format error: Number of resources, 501, is greater "
            "than maximum allowed, 500"
        ),
        # An ordinary missing-parameter ValidationError belongs to the
        # generic change-set rule, not the quota rule.
        negative=(
            "An error occurred (ValidationError) when calling the "
            "CreateChangeSet operation: Parameters: [DbPassword] must have "
            "values"
        ),
    ),
    "sam.deploy.bucket-config-conflict": RuleFixture(
        positive="Cannot use both --resolve-s3 and --s3-bucket parameters. Please use only one.",
        negative="Resolved the managed S3 bucket for deployment artifacts",
    ),
    "sam.build.esbuild-missing": RuleFixture(
        positive="NodejsNpmEsbuildBuilder:EsbuildBundle - Esbuild Failed: Cannot find esbuild.",
        negative="esbuild bundled the handler in 240ms",
    ),
    "sam.build.python-dependency-resolution-failed": RuleFixture(
        positive=(
            "Error: PythonPipBuilder:ResolveDependencies - "
            "{pip_failure_reason: ERROR: Could not find a version that "
            "satisfies the requirement pydantic-core==2.18.4 (from versions: "
            "none)}"
        ),
        negative="pip resolved every requirement without conflicts",
    ),
    "sam.build.python-runtime-mismatch": RuleFixture(
        positive=(
            "Error: PythonPipBuilder:Validation - Binary validation failed "
            "for python, searched for python in following locations: "
            "['/usr/local/bin/python3'] which did not satisfy constraints "
            "for runtime: python3.12 on your PATH?"
        ),
        negative="Binary validation confirmed python3.12 on PATH",
    ),
    "sam.build.python-dependency-validation-failed": RuleFixture(
        positive=(
            "PythonPipBuilder:ResolveDependencies - Binary validation "
            "failed: failed to build wheel for cryptography"
        ),
        negative="Built wheels for every dependency in the requirements file",
    ),
    "cloudformation.deploy.no-changes": RuleFixture(
        positive="Error: No changes to deploy. Stack my-app is up to date",
        negative="Changeset created successfully with three resource changes",
    ),
    "sam.deploy.artifact-upload-failed": RuleFixture(
        positive=(
            "Parameter CodeUri of resource HelloWorldFunction refers to a "
            "file or folder that does not exist"
        ),
        negative="Uploading to my-bucket/artifact.zip (100%)",
    ),
    "sam.deploy.configuration-resolution-failed": RuleFixture(
        positive="Error: Failed to create changeset",
        negative="Changeset created successfully",
    ),
    "sam.deploy.interactive-confirmation-required": RuleFixture(
        positive="Deploy this changeset? [y/N]:",
        negative="Automatically applied the changeset with --no-confirm-changeset",
    ),
    "apigateway.cors.preflight-conflict": RuleFixture(
        positive="CORS conflict: duplicate OPTIONS method",
        negative="The preflight request returned 204",
    ),
}

# Identifier shapes the fixture text must never contain, independent of the
# report-time redaction rules in `sam_doctor.redaction` - a fixture should be
# clean before a rule ever runs on it.
_DISALLOWED_PATTERNS = {
    "AWS account id": re.compile(r"(?<!\d)\d{12}(?!\d)"),
    "ARN": re.compile(r"arn:aws"),
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def check_fixtures(
    fixtures: dict[str, RuleFixture] | None = None,
) -> list[str]:
    """Return every fixture registry problem as a human-readable string."""

    checking_full_registry = fixtures is None
    fixtures = RULE_FIXTURES if fixtures is None else fixtures
    rules_by_id = {rule.id: rule for rule in supported_rules()}
    problems: list[str] = []

    if checking_full_registry:
        for rule_id in rules_by_id:
            if rule_id not in fixtures:
                problems.append(
                    f"{rule_id!r}: catalog rule has no fixture registry entry."
                )

    for rule_id, fixture in fixtures.items():
        if rule_id not in rules_by_id:
            problems.append(
                f"{rule_id!r}: no rule in the catalog carries this id."
            )
            continue

        if not fixture.positive.strip():
            problems.append(f"{rule_id!r}: fixture has no positive example.")
        if not fixture.negative.strip():
            problems.append(f"{rule_id!r}: fixture has no nearby-negative example.")
        if not fixture.positive.strip() or not fixture.negative.strip():
            continue

        for label, text in (("positive", fixture.positive), ("negative", fixture.negative)):
            for kind, pattern in _DISALLOWED_PATTERNS.items():
                if pattern.search(text):
                    problems.append(
                        f"{rule_id!r}: {label} fixture looks like it contains a {kind}."
                    )

        positive_ids = {finding.rule_id for finding in diagnose(fixture.positive)}
        if rule_id not in positive_ids:
            problems.append(f"{rule_id!r}: positive fixture does not trigger this rule.")

        negative_ids = {finding.rule_id for finding in diagnose(fixture.negative)}
        if rule_id in negative_ids:
            problems.append(f"{rule_id!r}: negative fixture still triggers this rule.")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rule",
        help="only check fixtures whose rule id contains this text (case-insensitive)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="github emits one ::error workflow command per problem",
    )
    args = parser.parse_args()

    fixtures = None
    if args.rule:
        needle = args.rule.lower()
        fixtures = {
            rule_id: fixture
            for rule_id, fixture in RULE_FIXTURES.items()
            if needle in rule_id.lower()
        }
        if not fixtures:
            print(f"No fixture registry entry matches --rule {args.rule!r}.")
            return 1

    problems = check_fixtures(fixtures)
    checked = len(fixtures) if fixtures is not None else len(RULE_FIXTURES)
    total_rules = len(supported_rules())
    if not problems:
        print(
            f"Rule fixture registry OK: {checked} checked, "
            f"{len(RULE_FIXTURES)} of {total_rules} catalog rules registered."
        )
        return 0

    for problem in problems:
        if args.format == "github":
            print(f"::error title=Rule fixture check::{problem}")
        else:
            print(f"ERROR: {problem}")
    print(f"{len(problems)} problem(s) across {checked} checked fixture(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
