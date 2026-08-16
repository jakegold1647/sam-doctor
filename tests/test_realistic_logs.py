"""Whole-log behaviour on realistic multi-line failures.

Every other test feeds a rule the one line it was written for. Real
CloudFormation output wraps its status reason inside a `CreateChangeSet`
ValidationError, prints several failed resources for one stack, and mixes
progress lines through all of it - and precedence between rules only matters in
that shape. This file asserts the finding *set* for eight logs that look like
what a reader actually pastes in.

It was written after a single-line pass had already been declared clean, and it
immediately found a stack in ROLLBACK_COMPLETE reporting the precise
recreate-required diagnosis alongside the generic configuration finding, for one
event on one line.
"""

from __future__ import annotations

from sam_doctor.diagnostics import diagnose

OIDC_REJECTED = """Run aws-actions/configure-aws-credentials@v4
Assuming role with OIDC
Error: Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity
##[error]Process completed with exit code 1.
"""

STACK_IN_ROLLBACK_COMPLETE = """Deploying with following values
Waiting for changeset to be created..
Error: Failed to create changeset for the stack: my-app, An error occurred (ValidationError) when calling the CreateChangeSet operation: Stack:arn:aws:cloudformation:us-east-1:123456789012:stack/my-app/abc is in ROLLBACK_COMPLETE state and can not be updated.
"""

STACK_CREATE_NAME_CONFLICT = """Deploying with following values
Waiting for changeset to be created..
Error: Failed to create changeset for the stack: sam-app, An error occurred (ValidationError) when calling the CreateChangeSet operation: Stack [sam-app] already exists and cannot be created again with the changeSet [samcli-deploy-1700000000].
"""


INLINE_POLICY_SIZE_LIMIT = """CloudFormation events from stack operations
CREATE_IN_PROGRESS AWS::IAM::Policy FunctionPolicy
CREATE_FAILED AWS::IAM::Policy FunctionPolicy Maximum policy size of 10240 bytes exceeded for role orders-123456789012-role (Service: AmazonIdentityManagement; Status Code: 409; Error Code: LimitExceeded)
"""

THREE_FAILED_RESOURCES = """CloudFormation events from stack operations
CREATE_IN_PROGRESS  AWS::DynamoDB::Table  Orders
CREATE_FAILED  AWS::DynamoDB::Table  Orders  Resource handler returned message: "Subscriber limit exceeded"
CREATE_FAILED  AWS::Lambda::Function  Worker  Resource handler returned message: "Lambda was unable to configure access to your environment variables. KMS Exception: DisabledException"
CREATE_FAILED  AWS::IAM::Role  AppRole  API: iam:CreateRole User: arn:aws:iam::123456789012:user/deploy is not authorized to perform: iam:TagRole on resource: role my-app-AppRole
ROLLBACK_IN_PROGRESS  AWS::CloudFormation::Stack  my-app
"""

PIP_RESOLUTION_FAILED = """Building codeuri: /workspace/src runtime: python3.12 architecture: x86_64
Running PythonPipBuilder:ResolveDependencies
Build Failed
Error: PythonPipBuilder:ResolveDependencies - {pip_failure_reason: ERROR: Could not find a version that satisfies the requirement pydantic-core==2.18.4 (from versions: none)}
"""

CREDENTIALS_EXPIRED = """Initiating deployment
Uploading to my-app/abc123 (45.00%)
An error occurred (ExpiredToken) when calling the CreateChangeSet operation: The security token included in the request is expired
Error: Failed to create changeset for the stack: my-app
"""

THROTTLED = """Waiting for changeset to be created..
An error occurred (Throttling) when calling the DescribeStacks operation (reached max retries: 4): Rate exceeded
Error: Failed to create changeset for the stack: my-app
"""

REGISTRY_REFUSED = """Building image for WorkerFunction
Setting DockerBuildArgs for WorkerFunction
Error response from daemon: pull access denied for 123456789012.dkr.ecr.us-east-1.amazonaws.com/base, repository does not exist or may require 'docker login'
Build Failed
"""

UNRECOGNISED_FAILURE = """Deploying with following values
CREATE_FAILED  AWS::Chatbot::SlackChannelConfiguration  Notifier  Resource handler returned message: "Slack workspace authorization has been revoked for this account"
ROLLBACK_IN_PROGRESS  AWS::CloudFormation::Stack  my-app
"""

CLEAN_DEPLOY = """Building codeuri: /workspace/src runtime: python3.12 architecture: x86_64
Running PythonPipBuilder:ResolveDependencies
Running PythonPipBuilder:CopySource
Build Succeeded
Deploying with following values
Uploading to my-app/1a2b3c (100.00%)
Waiting for changeset to be created..
Changeset created successfully
CREATE_COMPLETE       AWS::IAM::Role           OrdersFunctionRole
CREATE_COMPLETE       AWS::Lambda::Function    OrdersFunction
UPDATE_COMPLETE       AWS::CloudFormation::Stack  my-app
Successfully created/updated stack - my-app in us-east-1
Deployment time: 62.91s
"""


def _rule_ids(log: str) -> set[str]:
    return {finding.rule_id for finding in diagnose(log)}


def test_oidc_rejection_reports_only_the_oidc_rule() -> None:
    assert _rule_ids(OIDC_REJECTED) == {"github.oidc.assume-role-rejected"}


def test_rollback_complete_reports_only_the_recreate_diagnosis() -> None:
    # One line carries both the generic CreateChangeSet wrapper and the specific
    # status reason. Reporting both means telling the reader to check
    # `samconfig.toml` for a stack that simply has to be deleted first.
    assert _rule_ids(STACK_IN_ROLLBACK_COMPLETE) == {
        "cloudformation.stack.failed-recreate-required"
    }


def test_stack_create_name_conflict_reports_only_the_specific_diagnosis() -> None:
    assert _rule_ids(STACK_CREATE_NAME_CONFLICT) == {
        "cloudformation.stack.create-name-conflict"
    }



def test_inline_policy_size_limit_reports_only_the_specific_iam_diagnosis() -> None:
    assert _rule_ids(INLINE_POLICY_SIZE_LIMIT) == {
        "iam.role.inline-policy-size-limit"
    }

def test_three_failed_resources_each_get_their_own_finding() -> None:
    # The case whole-log suppression used to ruin: a stack rarely fails exactly
    # one resource, and the other failures are what the reader needs next.
    assert _rule_ids(THREE_FAILED_RESOURCES) == {
        "cloudformation.resource.create-update-failed",
        "lambda.env-vars.kms-key-inaccessible",
        "iam.tag.action-denied",
        "cloudformation.stack.rollback-complete",
    }


def test_pip_resolution_failure_reports_only_the_build_rule() -> None:
    # The progress line above the failure must not add a second finding.
    assert _rule_ids(PIP_RESOLUTION_FAILED) == {
        "sam.build.python-dependency-resolution-failed"
    }


def test_expired_credentials_outrank_the_generic_changeset_failure() -> None:
    assert _rule_ids(CREDENTIALS_EXPIRED) == {"aws.credentials.expired"}


def test_throttling_outranks_the_generic_changeset_failure() -> None:
    assert _rule_ids(THROTTLED) == {"cloudformation.api.throttled"}


def test_registry_refusal_is_not_an_unavailable_daemon() -> None:
    assert _rule_ids(REGISTRY_REFUSED) == {"docker.registry.image-unavailable"}


def test_an_unrecognised_reason_still_names_the_failed_resource() -> None:
    # No rule covers a revoked Slack authorization, and none should invent one.
    # Pointing at the failed resource and the rollback is honest and still useful.
    assert _rule_ids(UNRECOGNISED_FAILURE) == {
        "cloudformation.resource.create-update-failed",
        "cloudformation.stack.rollback-complete",
    }


def test_a_clean_deployment_reports_nothing_at_all() -> None:
    assert list(diagnose(CLEAN_DEPLOY)) == []


_INTERACTIVE_ID = "sam.deploy.interactive-confirmation-required"
_CORS_ID = "apigateway.cors.preflight-conflict"


def test_the_interactive_prompt_is_the_signal_not_the_word_aborted() -> None:
    # `Aborted!` was a pattern in its own right, so every interrupted tool in the
    # job was reported as a SAM interactive-confirmation problem - and told to set
    # --no-confirm-changeset, which would not have helped any of them.
    real = "Deploy this changeset? [y/N]: N\nAborted!\n"
    assert _INTERACTIVE_ID in _rule_ids(real)

    for unrelated in (
        "Sending build context to Docker daemon  2.5MB\nAborted!\n",
        "Collecting boto3\nAborted!\n",
        "terraform plan interrupted\nAborted!\n",
        "Waiting for stack rollback to complete...\nAborted!\n",
    ):
        assert _INTERACTIVE_ID not in _rule_ids(unrelated), unrelated


def test_cors_rule_needs_a_conflict_word_not_just_the_word_error() -> None:
    # `error` and `failed` were in the alternation, and across an 80-character
    # window from "CORS" they matched ordinary configuration output.
    for benign in (
        "Configuring CORS for ApiGateway: allowOrigins=[*] - no errors",
        "The preflight request returned 204",
    ):
        assert _CORS_ID not in _rule_ids(benign), benign

    for real in (
        "CORS conflict: duplicate OPTIONS method",
        "CREATE_FAILED AWS::ApiGateway::Method OPTIONS already exists",
        "Error: preflight configuration overlap on /orders",
    ):
        assert _CORS_ID in _rule_ids(real), real


def test_a_completed_rollback_is_still_worth_reporting() -> None:
    # UPDATE_ROLLBACK_COMPLETE is not a success: an update failed and the stack
    # rolled back. Reporting it is correct, and this pins that on purpose so the
    # pattern is not "tightened" away as a false positive later.
    assert "cloudformation.stack.rollback-complete" in _rule_ids(
        "UPDATE_ROLLBACK_COMPLETE  AWS::CloudFormation::Stack  my-app"
    )
