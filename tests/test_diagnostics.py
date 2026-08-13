import io
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from sam_doctor import __version__
from sam_doctor.cli import _read_demo, _read_text, _render_findings, _write_report, main
from sam_doctor.diagnostics import (
    diagnose,
    json_report,
    markdown_report,
    rules_report,
    terminal_report,
)
from sam_doctor.redaction import redact


def _load_schema(relative_path: str) -> dict[str, object]:
    schema_path = Path(__file__).resolve().parent.parent / relative_path
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _assert_object_shape(
    payload: object, schema: dict[str, object], *, required_key: str
) -> dict[str, object]:
    assert isinstance(payload, dict), f"{required_key} payload is not a JSON object"
    required = schema.get("required", [])
    assert all(
        key in payload for key in required
    ), f"{required_key} payload missing required keys"
    return payload


def _assert_json_schema_matches(
    schema_relative_path: str, payload: dict[str, object]
) -> None:
    schema = _load_schema(schema_relative_path)
    validator = Draft202012Validator(schema)
    validator.validate(payload)


def _finding_shape(
    finding: object, finding_schema: dict[str, object], index: int
) -> None:
    assert isinstance(finding, dict), f"finding {index} is not an object"
    required = finding_schema.get("required", [])
    assert all(
        key in finding for key in required
    ), f"finding {index} missing required keys"
    assert isinstance(finding["rule_id"], str)
    assert isinstance(finding["title"], str)
    assert isinstance(finding["confidence"], str)
    assert isinstance(finding["explanation"], str)
    assert isinstance(finding["verification"], list)
    assert isinstance(finding["documentation_url"], str)
    assert isinstance(finding["evidence"], list)
    assert isinstance(finding["line_number"], int)


def test_diagnose_json_payload_matches_schema_shape() -> None:
    output = json.loads(
        _render_findings(
            diagnose(
                "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
                "arn:aws:iam::123456789012:role/deploy owner@example.com"
            ),
            "failure.log",
            "json",
        )
    )
    diagnose_schema = _load_schema("docs/schemas/diagnose-report.schema.json")
    _assert_object_shape(output, diagnose_schema, required_key="diagnose")
    assert output["sam_doctor_version"] == __version__
    assert output["source"] == "failure.log"
    assert isinstance(output["finding_count"], int)
    assert output["finding_count"] == len(output["findings"])
    finding_schema = diagnose_schema["definitions"]["finding"]
    for index, finding in enumerate(output["findings"]):
        _finding_shape(finding, finding_schema, index)
    _assert_json_schema_matches("docs/schemas/diagnose-report.schema.json", output)


def test_batch_json_payload_matches_schema_shape() -> None:
    from sam_doctor.cli import _batch_render

    batch_schema = _load_schema("docs/schemas/batch-report.schema.json")
    diagnose_schema = _load_schema("docs/schemas/diagnose-report.schema.json")
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    report_text, _ = _batch_render(
        [
            str(docs_dir / "cloudformation-first-failure.md"),
            str(docs_dir / "oidc-deployment-debugging.md"),
        ],
        "json",
    )

    report = json.loads(report_text)
    _assert_object_shape(report, batch_schema, required_key="batch")
    _assert_json_schema_matches("docs/schemas/batch-report.schema.json", report)
    assert report["sam_doctor_version"] == __version__
    assert report["batch_count"] == len(report["results"])
    assert isinstance(report["results"], list)

    finding_schema = diagnose_schema["definitions"]["finding"]
    for index, result in enumerate(report["results"]):
        assert isinstance(result, dict)
        assert isinstance(result["source"], str)
        assert isinstance(result["finding_count"], int)
        assert isinstance(result["findings"], list)
        assert result["finding_count"] == len(result["findings"])
        for finding_index, finding in enumerate(result["findings"]):
            _finding_shape(finding, finding_schema, index=1000 * index + finding_index)


def test_package_version_matches_release() -> None:
    import re
    from pathlib import Path

    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r'^version = "(?P<version>\d+\.\d+\.\d+)"$', pyproject, re.MULTILINE
    )
    assert match is not None
    assert __version__ == match.group("version")


def test_oidc_failure_is_detected_and_redacted() -> None:
    findings = diagnose(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
        "arn:aws:iam::123456789012:role/deploy owner@example.com"
    )

    assert len(findings) == 1
    assert findings[0].title.startswith("GitHub Actions cannot assume")
    assert findings[0].line_number == 1
    report = markdown_report(findings, "failure.log")
    assert "[REDACTED_ARN]" in report
    assert "[REDACTED_EMAIL]" in report
    assert "123456789012" not in report
    assert "Matched on line: 1" in report


def test_unknown_log_has_no_finding() -> None:
    assert diagnose("Everything completed successfully.") == []


def test_no_finding_reports_include_a_sanitized_rule_request_path() -> None:
    markdown = markdown_report([], "unknown.log")
    terminal = terminal_report([], "unknown.log")

    assert "sam-doctor rules" in markdown
    assert "diagnostic rule request" in markdown
    assert "template=rule_request.yml" in markdown
    assert "sam-doctor request-packet unknown.log" in markdown
    assert "sam-doctor rules" in terminal
    assert "template=rule_request.yml" in terminal
    assert "sam-doctor request-packet unknown.log" in terminal


@pytest.mark.parametrize(
    ("log_line", "title_fragment"),
    (
        ("InvalidIdentityToken: Incorrect token audience", "token audience"),
        (
            "Unable to get ID Token: missing id-token: write permission",
            "cannot request an oidc token",
        ),
        (
            "No OpenIDConnect provider found in your account",
            "missing the github actions oidc provider",
        ),
        ("AccessDeniedException: action is not authorized", "AWS denied"),
        (
            "Error: Failed to create changeset for the stack: my-app, An error occurred (ValidationError) when calling the CreateChangeSet operation: S3 error: Access Denied",
            "deployment bucket denied access",
        ),
        (
            "Error uploading to my-deploy-bucket: An error occurred (AccessDenied) when calling the PutObject operation: Access Denied (Service: S3, Status Code: 403)",
            "deployment bucket denied access",
        ),
        (
            "property StageName: not defined for resource of type AWS::Serverless::Api",
            "SAM template property",
        ),
        (
            "InvalidSamDocumentException: Encountered unsupported property MemorySize",
            "schema validation",
        ),
        (
            "Resource with id [HelloFunction] is invalid. property Handler not defined for resource of type AWS::Serverless::StateMachine",
            "schema validation",
        ),
        ("Has prohibited field Resource", "trust policy contains"),
        (
            "Code signing is not supported for functions created with container images.",
            "code signing is incompatible",
        ),
        (
            "Lambda does not have permission to access the ECR image. Check the ECR permissions.",
            "cannot access the configured ecr image",
        ),
        (
            "The specified bucket is not valid. Error Code: InvalidBucketName",
            "S3 bucket name",
        ),
        (
            "An error occurred (UnrecognizedClientException) when calling the CreateChangeSet operation: The security token included in the request is invalid.",
            "invalid or wrong-account",
        ),
        (
            "Your access has been denied by S3, please make sure your request credentials have permission to GetObject for bucket layer-artifacts.",
            "cannot read a Lambda layer artifact",
        ),
        (
            "InsufficientCapabilitiesException: Requires capabilities : [CAPABILITY_NAMED_IAM]",
            "explicit capability acknowledgement",
        ),
        ("The REST API doesn't contain any methods", "API Gateway deployment started"),
        (
            "MyFunction CREATE_FAILED Resource handler returned message: denied",
            "resource creation",
        ),
        (
            "Stack: example is in ROLLBACK_COMPLETE state and can not be updated.",
            "terminal CloudFormation stack",
        ),
        (
            "Stack my-app is in UPDATE_ROLLBACK_FAILED state and can not be updated.",
            "rollback itself failed",
        ),
        (
            "Cannot use both --resolve-s3 and --s3-bucket parameters. Please use only one.",
            "managed and explicit S3 bucket",
        ),
        (
            "NodejsNpmEsbuildBuilder:EsbuildBundle - Esbuild Failed: Cannot find esbuild.",
            "cannot find the configured esbuild",
        ),
        (
            "PythonPipBuilder:ResolveDependencies - Binary validation failed: failed to build wheel for cryptography",
            "python dependency build validation failed",
        ),
        (
            "Error: PythonPipBuilder:ResolveDependencies - {pip_failure_reason: ERROR: Could not find a version that satisfies the requirement pydantic-core==2.18.4 (from versions: none)}",
            "python dependency resolution failed",
        ),
        (
            "Error: PythonPipBuilder:Validation - Binary validation failed for python, searched for python in following locations: ['/usr/local/bin/python3'] which did not satisfy constraints for runtime: python3.12 on your PATH?",
            "runtime binary is incompatible",
        ),
        ("Deploy this changeset? [y/N]:", "interactive changeset confirmation"),
        (
            "AWS::CloudFormation::Stack ROLLBACK_FAILED ... The following resource(s) failed to delete: [IAMRoleDeployment]",
            "rollback could not delete an iam role",
        ),
        ("UPDATE_ROLLBACK_IN_PROGRESS after a resource failure", "rollback"),
        ("Stack entered ROLLBACK_FAILED after a resource failure", "rollback"),
        ("Error: Failed to create changeset", "SAM deployment"),
        ("CORS conflict: duplicate OPTIONS method", "CORS preflight"),
        (
            "An error occurred (ExpiredTokenException) when calling the AssumeRole operation: The security token included in the request is expired",
            "credentials used by the deployment have expired",
        ),
        (
            "An error occurred (SignatureDoesNotMatch) when calling the DescribeStacks operation: Signature expired: 20260803T101500Z is now earlier than 20260803T104500Z (20260803T105000Z - 5 min.)",
            "credentials used by the deployment have expired",
        ),
        (
            "ResourceStatusReason: Rate exceeded (Service: CloudFormation, Status Code: 400, Request ID: 6f1c0e2a-example)",
            "throttled the deployment",
        ),
        (
            "An error occurred (ValidationError) when calling the DeleteStack operation: Stack [arn:aws:cloudformation:us-east-1:123456789012:stack/sam-app/1a2b3c4d] cannot be deleted while TerminationProtection is enabled",
            "blocked by termination protection",
        ),
        (
            "ArtifactBucket AWS::S3::Bucket DELETE_FAILED The bucket you tried to delete is not empty (Service: S3, Status Code: 409)",
            "could not delete one or more stack resources",
        ),
        (
            "denied: Your authorization token has expired. Reauthenticate and try again.",
            "could not authenticate to ECR",
        ),
        (
            'Error response from daemon: Head "https://123456789012.dkr.ecr.us-east-1.amazonaws.com/v2/sam-app/manifests/latest": no basic auth credentials',
            "could not authenticate to ECR",
        ),
        (
            "sam build --use-container failed: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?",
            "requires docker for containerized builds",
        ),
        (
            "Error: Docker is unavailable or not running. You can also refer to https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-docker.html",
            "requires docker for containerized builds",
        ),
        (
            "Error: Building image for HelloWorldFunction requires Docker. is Docker running?",
            "requires docker for containerized builds",
        ),
        (
            'sam build --use-container failed: exec: "docker": executable file not found in $PATH',
            "requires docker for containerized builds",
        ),
        (
            "sam build --use-container --cached failed: /bin/sh: docker: not found",
            "requires docker for containerized builds",
        ),
        (
            "An error occurred (InvalidParameterValueException) when calling the UpdateFunctionCode operation: Unzipped size must be smaller than 262144000 bytes",
            "package exceeds a per-function size limit",
        ),
        (
            "An error occurred (RequestEntityTooLargeException) when calling the UpdateFunctionCode operation: Request must be smaller than 70167211 bytes for the UpdateFunctionCode operation",
            "package exceeds a per-function size limit",
        ),
        (
            "An error occurred (CodeStorageExceededException) when calling the UpdateFunctionCode operation: Code storage limit exceeded.",
            "code storage limit exceeded",
        ),
        (
            "Stack my-service-prod is in UPDATE_IN_PROGRESS state and can not be updated.",
            "operation is already in progress",
        ),
        (
            "An error occurred (OperationInProgressException) when calling the UpdateStack operation",
            "operation is already in progress",
        ),
        (
            "Error: Unable to upload artifact HelloWorldFunction referenced by CodeUri parameter of HelloWorldFunction resource.",
            "could not upload a build artifact",
        ),
        (
            "Parameter CodeUri of resource HelloWorldFunction refers to a file or folder that does not exist",
            "could not upload a build artifact",
        ),
        (
            "MyBucket CREATE_FAILED my-app-logs already exists (Service: S3, Status Code: 409, Error Code: BucketAlreadyExists)",
            "already taken",
        ),
        (
            "MyBucket CREATE_FAILED my-app-logs already exists (Service: S3, Status Code: 409, Error Code: BucketAlreadyOwnedByYou)",
            "already taken",
        ),
        (
            'CREATE_FAILED AWS::S3::Bucket AssetBucket Resource handler returned message: "The requested bucket name is not available. The bucket namespace is shared by all users of the system..." (RequestToken: t-1, HandlerErrorCode: AlreadyExists)',
            "already taken",
        ),
        (
            "An error occurred (ValidationError) when calling the CreateChangeSet operation: 1 validation error detected: Value at 'templateBody' failed to satisfy constraint: Member must have length less than or equal to 51200",
            "size or count quota",
        ),
        (
            "Template format error: Number of resources, 501, is greater than maximum allowed, 500",
            "size or count quota",
        ),
    ),
)
def test_supported_failure_categories_are_detected(
    log_line: str, title_fragment: str
) -> None:
    findings = diagnose(log_line)

    assert any(title_fragment.lower() in finding.title.lower() for finding in findings)


@pytest.mark.parametrize(
    "log_line",
    (
        "sam deploy completed successfully",
        "AssumeRoleWithWebIdentity succeeded",
        "InvalidIdentityToken was handled by a retrying client",
        "Deployment values include Capabilities: [CAPABILITY_IAM]",
        "sam build completed after esbuild bundled the function",
        "Docker version 24.0.5, build 3713ee1",
        "Docker support is required for local tests, but our CI does not use container builds.",
        "SAM template property StageName is valid for AWS::Serverless::Api",
        "Configured CORS for the API",
        "The preflight request returned 204",
        "sam validate --lint completed with no errors",
    ),
)
def test_success_like_lines_do_not_create_false_findings(log_line: str) -> None:
    assert diagnose(log_line) == []


def test_normal_in_progress_events_do_not_report_a_concurrent_operation() -> None:
    log = (
        "sam-app UPDATE_IN_PROGRESS User Initiated\n"
        "HelloWorldFunction UPDATE_IN_PROGRESS -\n"
        "sam-app UPDATE_COMPLETE -"
    )

    assert diagnose(log) == []


def test_rollback_in_progress_states_stay_with_the_rollback_rules() -> None:
    log = "Stack my-app is in UPDATE_ROLLBACK_IN_PROGRESS state and can not be updated."

    titles = [finding.title for finding in diagnose(log)]
    assert (
        "Another CloudFormation operation is already in progress on the stack"
        not in titles
    )
    assert any("rollback" in title.lower() for title in titles)


def test_update_rollback_in_progress_does_not_report_the_failed_rollback_finding() -> None:
    log = "Stack my-app is in UPDATE_ROLLBACK_IN_PROGRESS state and can not be updated."

    titles = [finding.title for finding in diagnose(log)]
    assert "Stack rollback itself failed and must be continued or skipped" not in titles


def test_rollback_complete_as_a_bare_status_event_does_not_trigger_the_recreate_finding() -> (
    None
):
    log = "sam-app ROLLBACK_COMPLETE -"

    titles = [finding.title for finding in diagnose(log)]
    assert (
        "A terminal CloudFormation stack must be recreated before deployment"
        not in titles
    )


def test_delete_complete_update_refusal_reports_the_terminal_stack_finding() -> None:
    log = (
        "ValidationError: Stack:arn:aws:cloudformation:us-east-1:123456789012:"
        "stack/my-app/example is in DELETE_COMPLETE state and can not be updated."
    )

    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.stack.failed-recreate-required"
    ]


def test_cloudformation_wrapper_failure_routes_to_stack_events() -> None:
    log = (
        "Failed to create/update the stack. Run the following command to fetch "
        "the list of events leading up to the failure."
    )

    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.deploy.wrapper-failed"
    ]
    assert findings[0].confidence == "low"


@pytest.mark.parametrize(
    "log",
    (
        "300 | 14:42:23.544 | error | toolkit | AssemblyError: Assembly builder failed",
        "[BackendBuildError] Caused by: [_AssemblyError] Assembly builder failed",
    ),
)
def test_cdk_assembly_failure_routes_to_verbose_synthesis(log: str) -> None:

    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == ["cdk.synth.assembly-failed"]
    assert findings[0].confidence == "low"


def test_cdk_asset_bundle_failure_routes_to_asset_build_output() -> None:
    log = (
        "Failed to bundle asset amplify-app/function/Api/Code/Stage, "
        "bundle output is located at /tmp/cdk.out/bundling-temp-error: "
        "Error: esbuild exited with status 1\n"
        "[BackendBuildError] Caused by: [_AssemblyError] Assembly builder failed"
    )

    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == ["cdk.asset.bundling-failed"]
    assert findings[0].confidence == "low"


def test_cdk_asset_bundle_rule_requires_the_temporary_output_marker() -> None:
    findings = diagnose("Failed to bundle asset ApiFunction")

    assert "cdk.asset.bundling-failed" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        "sam build --debug failed: Error: [WinError 5] Access is denied: '.aws-sam\\build'",
        "PermissionError: [Errno 13] Permission denied: '/workspace/.aws-sam/build'",
    ),
)
def test_sam_build_generated_directory_permission_failures_route_to_local_checks(
    log: str,
) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "sam.build.output-permission-denied"
    ]
    assert findings[0].confidence == "medium"


def test_sam_build_permission_rule_does_not_claim_a_git_unlink_error() -> None:
    findings = diagnose(
        "error: unable to unlink old 'infra/.aws-sam/build/template.yaml': "
        "Permission denied"
    )

    assert "sam.build.output-permission-denied" not in {
        finding.rule_id for finding in findings
    }


def test_sam_build_permission_rule_requires_the_generated_directory() -> None:
    findings = diagnose("sam build failed: Permission denied reading source.py")

    assert "sam.build.output-permission-denied" not in {
        finding.rule_id for finding in findings
    }


def test_lambda_invoke_missing_target_routes_to_read_only_function_check() -> None:
    findings = diagnose(
        "An error occurred (ResourceNotFoundException) when calling the Invoke "
        "operation: Function not found"
    )

    assert [finding.rule_id for finding in findings] == [
        "lambda.invoke.function-not-found"
    ]
    assert findings[0].confidence == "medium"


def test_lambda_invoke_missing_target_is_still_detected_when_the_line_is_truncated() -> None:
    findings = diagnose(
        "An error occurred (ResourceNotFoundException) when calling the Invoke"
    )

    assert [finding.rule_id for finding in findings] == [
        "lambda.invoke.function-not-found"
    ]


def test_lambda_get_function_not_found_does_not_look_like_an_invoke_failure() -> None:
    findings = diagnose(
        "An error occurred (ResourceNotFoundException) when calling the GetFunction "
        "operation: Function not found"
    )

    assert "lambda.invoke.function-not-found" not in {
        finding.rule_id for finding in findings
    }


def test_bedrock_model_end_of_life_routes_to_model_migration() -> None:
    findings = diagnose(
        "Couldn't invoke ai21.j2-ultra-v1 model: operation error Bedrock Runtime: "
        "InvokeModel, https response error StatusCode: 404, "
        "ResourceNotFoundException: This model version has reached the end of its life."
    )

    assert [finding.rule_id for finding in findings] == [
        "bedrock.model-lifecycle.end-of-life"
    ]
    assert findings[0].confidence == "high"


def test_bedrock_model_end_of_life_rule_uses_the_exact_lifecycle_marker() -> None:
    findings = diagnose(
        "botocore.errorfactory.ResourceNotFoundException: This model version has "
        "reached the end of its life."
    )

    assert [finding.rule_id for finding in findings] == [
        "bedrock.model-lifecycle.end-of-life"
    ]


def test_bedrock_model_end_of_life_rule_does_not_match_a_different_lifecycle_phrase() -> None:
    findings = diagnose("This model version is still active and available.")

    assert "bedrock.model-lifecycle.end-of-life" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        (
            "An error occurred (ResourceNotFoundException) when calling the "
            "ConverseStream operation: Model use case details have not been "
            "submitted for this account. Fill out the Anthropic use case details "
            "form before using the model."
        ),
        "API Error: 404 Model use case details have not been submitted for this account.",
        "AWS-side. Bedrock returns: Model use case details have not been submitted for this account.",
    ),
)
def test_bedrock_model_access_gate_routes_to_first_use_form(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "bedrock.model-access.first-use-form-required"
    ]
    assert findings[0].confidence == "medium"


def test_bedrock_resource_not_found_without_access_phrase_is_not_this_rule() -> None:
    findings = diagnose(
        "An error occurred (ResourceNotFoundException) when calling the "
        "ConverseStream operation: The requested model ID is not found."
    )

    assert "bedrock.model-access.first-use-form-required" not in {
        finding.rule_id for finding in findings
    }


def test_bedrock_unresolved_model_identifier_routes_to_catalog_check() -> None:
    findings = diagnose(
        "An error occurred (ResourceNotFoundException) when calling the "
        "InvokeModelWithResponseStream operation: Could not resolve the foundation "
        "model from the provided model identifier."
    )

    assert [finding.rule_id for finding in findings] == [
        "bedrock.model-identifier.unresolved"
    ]
    assert findings[0].confidence == "medium"


def test_bedrock_unresolved_model_identifier_does_not_match_other_model_not_found() -> None:
    findings = diagnose(
        "An error occurred (ResourceNotFoundException) when calling the "
        "InvokeModel operation: The requested model ID is not found."
    )

    assert "bedrock.model-identifier.unresolved" not in {
        finding.rule_id for finding in findings
    }


def test_bedrock_empty_system_prompt_routes_to_request_builder_check() -> None:
    findings = diagnose(
        "ParamValidationError: Invalid length for parameter system[0].text,\n"
        "value: 0, valid min length: 1"
    )

    assert [finding.rule_id for finding in findings] == [
        "bedrock.request.empty-system-prompt"
    ]
    assert findings[0].confidence == "medium"


def test_bedrock_empty_system_prompt_does_not_match_empty_tool_description() -> None:
    findings = diagnose(
        "Parameter validation failed: Invalid length for parameter "
        "toolConfig.tools[0].toolSpec.description, value: 0, valid min length: 1"
    )

    assert "bedrock.request.empty-system-prompt" not in {
        finding.rule_id for finding in findings
    }


def test_bedrock_empty_model_id_routes_to_request_shape_check() -> None:
    findings = diagnose(
        "failed while calling AI provider amazonbedrock: operation error "
        "Bedrock Runtime: InvokeModel, serialization failed: serialization failed: "
        "input member modelId must not be empty"
    )

    assert [finding.rule_id for finding in findings] == [
        "bedrock.request.empty-model-id"
    ]
    assert findings[0].confidence == "medium"


def test_bedrock_empty_model_id_accepts_a_shortened_provider_wrapper() -> None:
    findings = diagnose("skipped: bedrock converse (): ... input member modelId must not be empty")

    assert [finding.rule_id for finding in findings] == [
        "bedrock.request.empty-model-id"
    ]


def test_bedrock_empty_model_id_does_not_match_generic_invoke_model_failure() -> None:
    findings = diagnose(
        "An error occurred (ValidationException) when calling the InvokeModel "
        "operation: The provided model identifier is invalid."
    )

    assert "bedrock.request.empty-model-id" not in {
        finding.rule_id for finding in findings
    }


def test_eks_vpc_cni_pod_sandbox_wrapper_routes_to_cni_logs() -> None:
    findings = diagnose(
        'Failed to create pod sandbox: rpc error: code = Unknown desc = '
        'failed to setup network for sandbox "pod-sandbox": plugin type="aws-cni" '
        'name="aws-cni" failed (add): add cmd: failed to assign an IP address to container'
    )

    assert [finding.rule_id for finding in findings] == [
        "eks.vpc-cni.pod-sandbox-network-failed"
    ]
    assert findings[0].confidence == "low"


def test_eks_network_policy_agent_failure_routes_to_agent_checks() -> None:
    findings = diagnose(
        'Failed to create pod sandbox: plugin type="aws-cni" name="aws-cni" '
        "failed (add): failed to setup network policy\n"
        "Failed to setup default network policy for Pod Name <pod> and NameSpace <ns>: "
        "Network policy agent returned - <nil>"
    )

    assert [finding.rule_id for finding in findings] == [
        "eks.network-policy.agent-failed"
    ]
    assert findings[0].confidence == "medium"


def test_eks_network_policy_rule_does_not_match_an_unrelated_network_failure() -> None:
    findings = diagnose("failed to setup network for sandbox: interface unavailable")

    assert "eks.network-policy.agent-failed" not in {
        finding.rule_id for finding in findings
    }


def test_kubernetes_pod_sandbox_network_fallback_covers_bare_cni_wrapper() -> None:
    findings = diagnose(
        "Warning FailedCreatePodSandBox: Failed to create pod sandbox: "
        'rpc error: code = Unknown desc = failed to setup network for sandbox "id": '
        'plugin type="calico" name="calico" failed (add): network unavailable'
    )

    assert [finding.rule_id for finding in findings] == [
        "kubernetes.pod-sandbox.network-setup-failed"
    ]
    assert findings[0].confidence == "low"


def test_kubernetes_pod_sandbox_fallback_yields_to_aws_cni_finding() -> None:
    findings = diagnose(
        "Failed to create pod sandbox: rpc error: code = Unknown desc = "
        'failed to setup network for sandbox "id": plugin type="aws-cni" '
        'name="aws-cni" failed (add): failed to assign an IP address to container'
    )

    assert [finding.rule_id for finding in findings] == [
        "eks.vpc-cni.pod-sandbox-network-failed"
    ]


def test_apigateway_security_policy_requires_endpoint_access_mode() -> None:
    findings = diagnose(
        'MyApi CREATE_FAILED: Resource handler returned message: "Endpoint access mode is required for '
        'the specified security policy (Service: ApiGateway, Status Code: 400)"'
    )

    assert [finding.rule_id for finding in findings] == [
        "apigateway.security-policy.endpoint-access-required"
    ]
    assert findings[0].confidence == "high"


def test_apigateway_security_policy_rule_ignores_unrelated_endpoint_text() -> None:
    findings = diagnose(
        "API Gateway endpoint access mode is configured and the security policy is valid"
    )

    assert "apigateway.security-policy.endpoint-access-required" not in {
        finding.rule_id for finding in findings
    }


def test_lambda_vpc_execution_role_requires_network_interface_permissions() -> None:
    findings = diagnose(
        'MyFunction CREATE_FAILED: Resource handler returned message: "The provided '
        'execution role does not have permissions to call CreateNetworkInterface on EC2 '
        '(Service: Lambda, Status Code: 400, Error Code: InvalidParameterValueException)"'
    )

    assert [finding.rule_id for finding in findings] == [
        "lambda.vpc.execution-role-network-interface-permission"
    ]
    assert findings[0].confidence == "high"


def test_lambda_vpc_execution_role_rule_accepts_singular_permission_wording() -> None:
    findings = diagnose(
        "The provided execution role does not have permission to call "
        "CreateNetworkInterface on EC2"
    )

    assert [finding.rule_id for finding in findings] == [
        "lambda.vpc.execution-role-network-interface-permission"
    ]


def test_lambda_vpc_execution_role_rule_ignores_near_match() -> None:
    findings = diagnose(
        "The provided execution role has permissions to call "
        "CreateNetworkInterface on EC2"
    )

    assert "lambda.vpc.execution-role-network-interface-permission" not in {
        finding.rule_id for finding in findings
    }


def test_lambda_vpc_execution_role_rule_keeps_unrelated_resource_failure() -> None:
    findings = diagnose(
        'MyFunction CREATE_FAILED: Resource handler returned message: "The provided '
        'execution role does not have permissions to call CreateNetworkInterface on EC2"\n'
        "MyBucket CREATE_FAILED: Resource handler returned message: unrelated bucket failure"
    )

    rule_ids = {finding.rule_id for finding in findings}
    assert "lambda.vpc.execution-role-network-interface-permission" in rule_ids
    assert "cloudformation.resource.create-update-failed" in rule_ids


def test_eks_vpc_cni_wrapper_yields_to_nested_ec2_cause() -> None:
    findings = diagnose(
        'Failed to create pod sandbox: plugin type="aws-cni" name="aws-cni" failed (add)\n'
        "Failed to CreateNetworkInterface operation error EC2: CreateNetworkInterface, "
        "https response error StatusCode: 400, api error InvalidParameterValue: "
        "There aren't sufficient free IPv4 addresses in the subnet"
    )

    rule_ids = {finding.rule_id for finding in findings}
    assert "eks.vpc-cni.pod-sandbox-network-failed" not in rule_ids
    assert "ec2.network-interface.create-failed" in rule_ids


def test_eks_vpc_cni_plugin_line_is_enough_when_wrapper_is_split() -> None:
    findings = diagnose(
        'plugin type="aws-cni" name="aws-cni" failed (add): '
        "failed to assign an IP address to container"
    )

    assert [finding.rule_id for finding in findings] == [
        "eks.vpc-cni.pod-sandbox-network-failed"
    ]


def test_eks_vpc_cni_wrapper_does_not_match_another_plugin() -> None:
    findings = diagnose(
        'Failed to create pod sandbox: plugin type="calico" name="calico" '
        "failed (add): network unavailable"
    )

    assert "eks.vpc-cni.pod-sandbox-network-failed" not in {
        finding.rule_id for finding in findings
    }


def test_bedrock_messages_required_routes_to_request_body_check() -> None:
    findings = diagnose(
        "failed to generate embedding: operation error Bedrock Runtime: InvokeModel, "
        "https response error StatusCode: 400, ValidationException: messages: Field required"
    )

    assert [finding.rule_id for finding in findings] == [
        "bedrock.request.messages-required"
    ]
    assert findings[0].confidence == "medium"


def test_bedrock_messages_required_does_not_match_other_validation_fields() -> None:
    findings = diagnose(
        "operation error Bedrock Runtime: InvokeModel, ValidationException: "
        "content: Field required"
    )

    assert "bedrock.request.messages-required" not in {
        finding.rule_id for finding in findings
    }


def test_messages_validation_without_bedrock_context_is_not_this_rule() -> None:
    findings = diagnose(
        "An error occurred (ValidationException) when calling the GetThing operation: "
        "messages: Field required"
    )

    assert "bedrock.request.messages-required" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        (
            "botocore.errorfactory.ValidationException: An error occurred "
            "(ValidationException) when calling the InvokeModel operation: "
            "messages.0.content.1.image.source: Field required"
        ),
        (
            "ValidationException: The model returned the following errors: "
            "messages.1.content.0.thinking.signature: Field required"
        ),
        "ValidationException: messages.0.content.0.document.source.type: Field required",
    ),
)
def test_bedrock_message_content_field_required_routes_to_nested_body_check(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "bedrock.request.message-content-field-required"
    ]
    assert findings[0].confidence == "medium"


def test_bedrock_message_content_field_rule_does_not_match_unindexed_text() -> None:
    findings = diagnose(
        "ValidationException: messages: Field required"
    )

    assert "bedrock.request.message-content-field-required" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        "An error occurred (UnknownAction) when calling the GetTemplateSummary operation: Action is not supported",
        "An error occurred (InvalidAction) when calling the DescribeLaunchConfigurations operation: invalid action",
    ),
)
def test_invalid_aws_action_routes_to_operation_and_endpoint_checks(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == ["aws.api.action-invalid"]
    assert findings[0].confidence == "low"


def test_invalid_aws_action_does_not_match_an_iam_denial() -> None:
    findings = diagnose(
        "An error occurred (AccessDeniedException) when calling the "
        "DescribeStacks operation: User is not authorized to perform this action"
    )

    assert "aws.api.action-invalid" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        "An error occurred (NotImplemented) when calling the ListSchedules operation: operation is not implemented",
        "HTTP 501 NotImplemented when calling the ListSchedules operation",
    ),
)
def test_unimplemented_aws_action_routes_to_endpoint_compatibility_checks(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "aws.api.action-not-implemented"
    ]
    assert findings[0].confidence == "low"


def test_unimplemented_aws_action_does_not_match_generic_not_implemented_text() -> None:
    findings = diagnose("The deployment status is NotImplemented in the report")

    assert "aws.api.action-not-implemented" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        "An error occurred (UnknownService) when calling the PutMetricData operation: Unknown service target",
        "Unknown service target when calling the PutMetricData operation: UnknownService",
    ),
)
def test_unknown_aws_service_routes_to_endpoint_routing_checks(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == ["aws.api.service-unknown"]
    assert findings[0].confidence == "low"


def test_unknown_aws_service_does_not_match_telemetry_label() -> None:
    findings = diagnose("OpenTelemetry exported aws.local.service=UnknownService")

    assert "aws.api.service-unknown" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        "Error: reading STS Caller Identity\noperation error STS: GetCallerIdentity, https response error StatusCode: 403, api error SignatureDoesNotMatch: Credential should be scoped to a valid region.",
        "Error: reading STS Caller Identity",
    ),
)
def test_sts_caller_identity_wrapper_routes_to_nested_cause_checks(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "aws.credentials.caller-identity-unavailable"
    ]
    assert findings[0].confidence == "low"


def test_sts_caller_identity_rule_does_not_match_unrelated_identity_text() -> None:
    findings = diagnose("The caller identity was recorded successfully")

    assert "aws.credentials.caller-identity-unavailable" not in {
        finding.rule_id for finding in findings
    }


def test_ec2_network_interface_wrapper_routes_to_nested_create_cause_checks() -> None:
    findings = diagnose(
        "Error: creating EC2 Network Interface: operation error EC2: "
        "CreateNetworkInterface, https response error StatusCode: 400, "
        "RequestID: request-id, api error InvalidParameterValue: There aren't "
        "sufficient free IPv4 addresses in the subnet"
    )

    assert [finding.rule_id for finding in findings] == [
        "ec2.network-interface.create-failed"
    ]
    assert findings[0].confidence == "low"


def test_ec2_network_interface_rule_requires_the_provider_wrapper() -> None:
    findings = diagnose(
        "An error occurred (InvalidParameterValue) when calling the "
        "CreateNetworkInterface operation: there aren't sufficient free IPv4 "
        "addresses in the subnet"
    )

    assert "ec2.network-interface.create-failed" not in {
        finding.rule_id for finding in findings
    }


def test_glue_database_rename_routes_to_immutable_name_checks() -> None:
    findings = diagnose(
        "An error occurred (InvalidInputException) when calling the "
        "UpdateDatabase operation: Database cannot be renamed"
    )

    assert [finding.rule_id for finding in findings] == [
        "glue.database.rename-rejected"
    ]
    assert findings[0].confidence == "high"


def test_glue_database_rule_does_not_match_other_update_input_errors() -> None:
    findings = diagnose(
        "An error occurred (InvalidInputException) when calling the "
        "UpdateDatabase operation: Description is invalid"
    )

    assert "glue.database.rename-rejected" not in {
        finding.rule_id for finding in findings
    }


def test_cloudcontrol_operation_wrapper_routes_to_progress_status_checks() -> None:
    findings = diagnose(
        "Error: AWS SDK Go Service Operation Incomplete\n"
        "Waiting for Cloud Control API service CreateResource operation completion "
        "returned: waiter state transitioned to FAILED. StatusMessage: handler failed"
    )

    assert [finding.rule_id for finding in findings] == [
        "cloudcontrol.operation.incomplete"
    ]
    assert findings[0].confidence == "low"


def test_cloudcontrol_rule_does_not_match_a_successful_sdk_operation() -> None:
    findings = diagnose("AWS SDK Go Service Operation completed successfully")

    assert "cloudcontrol.operation.incomplete" not in {
        finding.rule_id for finding in findings
    }


@pytest.mark.parametrize(
    "log",
    (
        "CannotStartManagedAgentError: failed to start managed agent inside container",
        "An error occurred (InvalidParameterException) when calling the ExecuteCommand operation:",
        (
            "An error occurred (InvalidParameterException) when calling the ExecuteCommand "
            "operation: The execute command failed because execute command was not enabled "
            "when the task was run or the execute command agent isn't running"
        ),
    ),
)
def test_ecs_exec_agent_failures_route_to_prerequisite_checks(log: str) -> None:
    findings = diagnose(log)

    assert [finding.rule_id for finding in findings] == [
        "ecs.execute-command.agent-unavailable"
    ]
    assert findings[0].confidence == "medium"


def test_update_rollback_failed_suppresses_the_generic_rollback_finding() -> None:
    log = "Stack my-app is in UPDATE_ROLLBACK_FAILED state and can not be updated."

    titles = [finding.title for finding in diagnose(log)]
    assert "Stack rollback itself failed and must be continued or skipped" in titles
    assert (
        "CloudFormation stack entered rollback after an earlier resource failure"
        not in titles
    )


def test_nested_stack_create_failure_is_detected() -> None:
    log = (
        "CREATE_FAILED  AWS::CloudFormation::Stack  DatabaseStack  "
        "Embedded stack arn:aws:cloudformation:us-east-1:123456789012:"
        "stack/my-app-DatabaseStack-ABC123/... was not successfully created: "
        "The following resource(s) failed to create: [DBSubnetGroup]."
    )

    titles = [finding.title for finding in diagnose(log)]
    assert (
        "A nested (embedded) stack failed - the root cause is in the child stack's events"
        in titles
    )


def test_nested_stack_update_failure_is_detected() -> None:
    log = (
        "UPDATE_FAILED  AWS::CloudFormation::Stack  ApiStack  "
        "Embedded stack ... was not successfully updated. Currently in "
        "UPDATE_ROLLBACK_IN_PROGRESS with reason: The following resource(s) "
        "failed to update: [UsagePlan]."
    )

    titles = [finding.title for finding in diagnose(log)]
    assert (
        "A nested (embedded) stack failed - the root cause is in the child stack's events"
        in titles
    )


def test_nested_stack_failure_suppresses_the_generic_create_update_finding() -> None:
    log = (
        "CREATE_FAILED  AWS::CloudFormation::Stack  DatabaseStack  "
        "Embedded stack arn:aws:cloudformation:us-east-1:123456789012:"
        "stack/my-app-DatabaseStack-ABC123/... was not successfully created: "
        "The following resource(s) failed to create: [DBSubnetGroup]."
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "CloudFormation resource creation or update failed" not in titles


def test_nested_stack_update_failure_suppresses_the_generic_rollback_finding() -> None:
    log = (
        "UPDATE_FAILED  AWS::CloudFormation::Stack  ApiStack  "
        "Embedded stack ... was not successfully updated. Currently in "
        "UPDATE_ROLLBACK_IN_PROGRESS with reason: The following resource(s) "
        "failed to update: [UsagePlan]."
    )

    titles = [finding.title for finding in diagnose(log)]
    assert (
        "CloudFormation stack entered rollback after an earlier resource failure"
        not in titles
    )


def test_plain_create_failed_without_an_embedded_stack_still_reports_the_generic_finding() -> (
    None
):
    log = "MyFunction CREATE_FAILED Resource handler returned message: denied"

    titles = [finding.title for finding in diagnose(log)]
    assert "CloudFormation resource creation or update failed" in titles
    assert (
        "A nested (embedded) stack failed - the root cause is in the child stack's events"
        not in titles
    )


def test_successful_artifact_upload_does_not_report_a_missing_artifact() -> None:
    log = "Uploading to my-deploy-bucket/artifact.zip (100%)"

    titles = [finding.title for finding in diagnose(log)]
    assert (
        "SAM could not upload a build artifact referenced by the template" not in titles
    )


def test_concurrent_operation_finding_suppresses_the_generic_changeset_rule() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app, "
        "An error occurred (OperationInProgressException) when calling the "
        "UpdateStack operation"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "Another CloudFormation operation is already in progress on the stack" in titles
    assert "AWS SAM deployment configuration or parameter resolution failed" not in titles


def test_missing_artifact_finding_suppresses_the_generic_changeset_rule() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app\n"
        "Error: Unable to upload artifact HelloWorldFunction referenced by "
        "CodeUri parameter of HelloWorldFunction resource.\n"
        "Parameter CodeUri of resource HelloWorldFunction refers to a file or "
        "folder that does not exist"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "SAM could not upload a build artifact referenced by the template" in titles
    assert "AWS SAM deployment configuration or parameter resolution failed" not in titles


def test_bucket_progress_output_does_not_report_a_name_collision() -> None:
    log = "Creating the required S3 bucket if one does not exist"

    assert diagnose(log) == []


def test_an_invalid_bucket_name_keeps_the_validation_finding() -> None:
    log = (
        "MyBucket CREATE_FAILED The specified bucket is not valid. "
        "(Service: S3, Status Code: 400, Error Code: InvalidBucketName)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "An S3 bucket name failed AWS validation" in titles
    assert "An S3 bucket name in the template is already taken" not in titles


def test_bucket_name_collision_suppresses_the_generic_resource_failure() -> None:
    log = (
        "MyBucket CREATE_FAILED my-app-logs already exists "
        "(Service: S3, Status Code: 409, Error Code: BucketAlreadyExists)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "An S3 bucket name in the template is already taken" in titles
    assert "CloudFormation resource creation or update failed" not in titles
    assert "An S3 bucket name failed AWS validation" not in titles


def test_bucket_already_owned_by_you_suppresses_the_generic_changeset_rule() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app\n"
        "MyBucket CREATE_FAILED my-app-logs already exists "
        "(Service: S3, Status Code: 409, Error Code: BucketAlreadyOwnedByYou)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "An S3 bucket name in the template is already taken" in titles
    assert "AWS SAM deployment configuration or parameter resolution failed" not in titles


def test_resource_handler_wording_is_read_as_a_bucket_name_collision() -> None:
    log = (
        "CREATE_FAILED AWS::S3::Bucket AssetBucket Resource handler returned "
        'message: "The requested bucket name is not available. The bucket '
        'namespace is shared by all users of the system..." '
        "(RequestToken: t-1, HandlerErrorCode: AlreadyExists)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "An S3 bucket name in the template is already taken" in titles
    assert "An S3 bucket name failed AWS validation" not in titles


def test_a_non_bucket_already_exists_handler_error_is_not_a_bucket_collision() -> None:
    log = (
        "CREATE_FAILED AWS::IAM::Role AppRole Resource handler returned "
        'message: "Role with name my-app-role already exists." '
        "(RequestToken: t-2, HandlerErrorCode: AlreadyExists)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "An S3 bucket name in the template is already taken" not in titles
    assert "CloudFormation resource creation or update failed" in titles


def test_handler_wording_collision_keeps_unrelated_resource_failures_visible() -> None:
    log = (
        "CREATE_FAILED AWS::S3::Bucket AssetBucket Resource handler returned "
        'message: "The requested bucket name is not available. The bucket '
        'namespace is shared by all users of the system..." '
        "(RequestToken: t-1, HandlerErrorCode: AlreadyExists)\n"
        "CREATE_FAILED AWS::SQS::Queue WorkQueue Resource handler returned "
        'message: "The specified queue does not exist."\n'
        "CREATE_FAILED AWS::DynamoDB::Table Orders Resource handler returned "
        'message: "Subscriber limit exceeded."'
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "An S3 bucket name in the template is already taken" in titles
    assert "CloudFormation resource creation or update failed" in titles


def test_non_ascii_property_rejection_suppresses_the_generic_resource_failure() -> None:
    log = (
        "AppSecurityGroup CREATE_FAILED AWS::EC2::SecurityGroup Resource "
        'handler returned message: "Value (Pre-deploy Lambda -> RDS plus '
        'VPC endpoints) for parameter GroupDescription is invalid. '
        'Character sets beyond ASCII are not supported"'
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "A resource property was rejected for non-ASCII characters" in titles
    assert "CloudFormation resource creation or update failed" not in titles


def test_a_different_invalid_value_keeps_the_generic_resource_failure() -> None:
    log = (
        "AppSecurityGroup CREATE_FAILED AWS::EC2::SecurityGroup Resource "
        'handler returned message: "Value for parameter GroupDescription is '
        'invalid because it exceeds the maximum length"'
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "A resource property was rejected for non-ASCII characters" not in titles
    assert "CloudFormation resource creation or update failed" in titles


def test_non_ascii_rejection_keeps_unrelated_resource_failures_visible() -> None:
    log = (
        "AppSecurityGroup CREATE_FAILED AWS::EC2::SecurityGroup Resource "
        'handler returned message: "Value for parameter GroupDescription is '
        'invalid. Character sets beyond ASCII are not supported"\n'
        "WorkQueue CREATE_FAILED AWS::SQS::Queue Resource handler returned "
        'message: "The specified queue does not exist."'
    )

    findings = diagnose(log)
    titles = [finding.title for finding in findings]
    assert "A resource property was rejected for non-ASCII characters" in titles
    assert "CloudFormation resource creation or update failed" in titles

    generic_finding = next(
        f
        for f in findings
        if f.title == "CloudFormation resource creation or update failed"
    )
    assert not any("AppSecurityGroup" in line for line in generic_finding.evidence)
    assert any("WorkQueue" in line for line in generic_finding.evidence)


def test_a_missing_parameter_validation_error_is_not_a_schema_validation_failure() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app\n"
        "An error occurred (ValidationError) when calling the CreateChangeSet "
        "operation: Parameters: [DbPassword] must have values"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The template failed SAM or CloudFormation schema validation" not in titles


def test_sam_lint_summary_reports_the_exact_wrapper() -> None:
    summary = (
        "Error: Linting failed. At least one linting rule was matched to the "
        "provided template."
    )

    findings = diagnose(summary)

    assert len(findings) == 1
    assert findings[0].rule_id == "sam.validate.lint-rule-matched"
    assert findings[0].title == "SAM lint validation found one or more cfn-lint matches"
    assert findings[0].confidence == "medium"
    assert findings[0].evidence == (summary,)
    assert findings[0].line_number == 1


def test_sam_lint_summary_keeps_the_summary_as_second_line_evidence() -> None:
    summary = (
        "Error: Linting failed. At least one linting rule was matched to the "
        "provided template."
    )
    log = (
        "[[E1031: ToJsonString validation of parameters] "
        "(Fn::ToJsonString is not supported without "
        "'AWS::LanguageExtensions' transform) matched 17]\n"
        f"{summary}"
    )

    findings = diagnose(log)

    assert len(findings) == 1
    assert findings[0].rule_id == "sam.validate.lint-rule-matched"
    assert findings[0].evidence == (summary,)
    assert findings[0].line_number == 2


@pytest.mark.parametrize(
    "log",
    (
        (
            "SAM template is valid. This is according to basic SAM Validation, "
            "additional validations are available by running with --lint option."
        ),
        "W3005 Obsolete DependsOn on resource (ApiFunction)",
        "InvalidSamDocumentException: Encountered unsupported property MemorySize",
        "property StageName: not defined for resource of type AWS::Serverless::Api",
    ),
)
def test_sam_lint_summary_ignores_nearby_non_matches(log: str) -> None:
    rule_ids = {finding.rule_id for finding in diagnose(log)}

    assert "sam.validate.lint-rule-matched" not in rule_ids


def test_colon_variant_property_mismatch_keeps_only_the_specific_finding() -> None:
    log = "property StageName: not defined for resource of type AWS::Serverless::Api"

    titles = [finding.title for finding in diagnose(log)]
    assert "A SAM template property is not valid for its resource type" in titles
    assert "The template failed SAM or CloudFormation schema validation" not in titles


def test_unsupported_property_wording_reports_schema_validation() -> None:
    log = "InvalidSamDocumentException: Encountered unsupported property MemorySize"

    titles = [finding.title for finding in diagnose(log)]
    assert "The template failed SAM or CloudFormation schema validation" in titles
    assert "A SAM template property is not valid for its resource type" not in titles


def test_property_mismatch_without_a_colon_reports_schema_validation() -> None:
    log = (
        "Resource with id [HelloFunction] is invalid. property Handler not "
        "defined for resource of type AWS::Serverless::StateMachine"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The template failed SAM or CloudFormation schema validation" in titles
    assert "A SAM template property is not valid for its resource type" not in titles


def test_detects_fn_getatt_with_the_wrong_parameter_count() -> None:
    log = (
        "An error occurred (ValidationError) when calling the CreateChangeSet "
        "operation: Template error: every Fn::GetAtt object requires two "
        "non-empty parameters, the resource name and the resource attribute"
    )

    findings = diagnose(log)

    assert len(findings) == 1
    assert findings[0].rule_id == "cloudformation.template.getatt-parameters-invalid"
    assert findings[0].confidence == "high"
    assert findings[0].line_number == 1


@pytest.mark.parametrize(
    "log",
    (
        "Template validation accepted Fn::GetAtt: [WorkerFunction, Arn]",
        "Template error: instance of Fn::Select requires two non-empty parameters",
    ),
)
def test_fn_getatt_parameter_count_rule_ignores_nearby_non_matches(log: str) -> None:
    rule_ids = {finding.rule_id for finding in diagnose(log)}

    assert "cloudformation.template.getatt-parameters-invalid" not in rule_ids


def test_fn_getatt_reason_outranks_a_same_line_generic_changeset_wrapper() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app, An error "
        "occurred (ValidationError) when calling the CreateChangeSet operation: "
        "Template error: every Fn::GetAtt object requires two non-empty "
        "parameters, the resource name and the resource attribute"
    )

    rule_ids = [finding.rule_id for finding in diagnose(log)]

    assert rule_ids == ["cloudformation.template.getatt-parameters-invalid"]


def test_fn_getatt_reason_does_not_hide_a_different_changeset_failure() -> None:
    log = (
        "Deploy alpha: Error: Failed to create changeset because a required "
        "parameter is missing\n"
        "Deploy beta: An error occurred (ValidationError) when calling the "
        "CreateChangeSet operation: Template error: every Fn::GetAtt object "
        "requires two non-empty parameters, the resource name and the resource "
        "attribute"
    )

    rule_ids = {finding.rule_id for finding in diagnose(log)}

    assert rule_ids == {
        "cloudformation.template.getatt-parameters-invalid",
        "sam.deploy.configuration-resolution-failed",
    }


def test_a_missing_parameter_validation_error_is_not_a_template_quota_failure() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app\n"
        "An error occurred (ValidationError) when calling the CreateChangeSet "
        "operation: Parameters: [DbPassword] must have values"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The template exceeds a CloudFormation size or count quota" not in titles
    assert "AWS SAM deployment configuration or parameter resolution failed" in titles


def test_template_quota_finding_suppresses_the_generic_changeset_rule() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app\n"
        "An error occurred (ValidationError) when calling the CreateChangeSet "
        "operation: 1 validation error detected: Value at 'templateBody' failed "
        "to satisfy constraint: Member must have length less than or equal to 51200"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert titles == ["The template exceeds a CloudFormation size or count quota"]


def test_lambda_package_size_rule_does_not_match_code_storage_quota_errors() -> None:
    log = (
        "An error occurred (CodeStorageExceededException) when calling the "
        "UpdateFunctionCode operation: Code storage limit exceeded."
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert (
        "The Lambda deployment package exceeds a per-function size limit" not in titles
    )


@pytest.mark.parametrize(
    ("log_line", "expected_titles"),
    (
        ("AssumeRoleWithWebIdentity request succeeded on retry", ()),
        ("OIDC token audience was accepted after a handled retry", ()),
        (
            "AccessDeniedException: iam:GetRole is not authorized",
            ("AWS denied an API action required by the deployment",),
        ),
    ),
)
def test_oidc_near_matches_do_not_trigger_oidc_findings(
    log_line: str, expected_titles: tuple[str, ...]
) -> None:
    findings = diagnose(log_line)

    assert all("oidc" not in finding.title.lower() for finding in findings)
    assert tuple(finding.title for finding in findings) == expected_titles


def test_packaged_demo_is_available() -> None:
    assert "AssumeRoleWithWebIdentity" in _read_demo()


def test_capability_error_does_not_add_the_generic_sam_finding() -> None:
    findings = diagnose(
        "Error: Failed to create changeset: InsufficientCapabilitiesException: "
        "Requires capabilities : [CAPABILITY_IAM]"
    )

    assert len(findings) == 1
    assert "explicit capability acknowledgement" in findings[0].title.lower()


def test_findings_follow_the_order_of_the_supporting_log_lines() -> None:
    findings = diagnose(
        "CORS conflict: duplicate OPTIONS method\n"
        "AccessDeniedException: action is not authorized"
    )

    assert [finding.title for finding in findings] == [
        "API Gateway CORS preflight configuration conflicts with an existing OPTIONS method",
        "AWS denied an API action required by the deployment",
    ]
    assert findings[0].line_number == 1
    assert findings[1].line_number == 2


@pytest.mark.parametrize(
    ("log", "title_fragment"),
    (
        (
            "Error: Failed to create changeset\nCannot use both --resolve-s3 and --s3-bucket parameters.",
            "managed and explicit S3 bucket",
        ),
        (
            "Error: Failed to create changeset\nEsbuild Failed: Cannot find esbuild.",
            "cannot find the configured esbuild",
        ),
        (
            "ROLLBACK_COMPLETE\nStack is in ROLLBACK_COMPLETE state and can not be updated.",
            "terminal CloudFormation stack",
        ),
        (
            "MyFunction CREATE_FAILED\nCode signing is not supported for functions created with container images.",
            "code signing is incompatible",
        ),
        (
            "MyFunction CREATE_FAILED\nLambda does not have permission to access the ECR image.",
            "cannot access the configured ecr image",
        ),
        (
            "MyLayer CREATE_FAILED\nYour access has been denied by S3, please make sure your request credentials have permission to GetObject for bucket layer-artifacts.",
            "cannot read a Lambda layer artifact",
        ),
        (
            "MyStack DELETE_FAILED The following resource(s) failed to delete: [MyRole].\n"
            + "Failed to delete AWS::IAM::Role MyRole",
            "rollback could not delete an iam role",
        ),
        (
            "Error: Failed to create changeset for the stack sam-app: An error occurred (ExpiredToken) when calling the CreateChangeSet operation: The security token included in the request is expired",
            "credentials used by the deployment have expired",
        ),
        (
            "Error: Failed to create changeset for the stack sam-app: An error occurred (Throttling) when calling the CreateChangeSet operation (reached max retries: 4): Rate exceeded",
            "throttled the deployment",
        ),
        (
            "Error: Failed to create changeset for the stack sam-app: PythonPipBuilder:ResolveDependencies - Binary validation failed: Python executable not found",
            "runtime binary is incompatible",
        ),
    ),
)
def test_specific_findings_suppress_broader_diagnostics(
    log: str, title_fragment: str
) -> None:
    findings = diagnose(log)

    assert len(findings) == 1
    assert title_fragment.lower() in findings[0].title.lower()


def test_detects_sam_empty_changeset_failure() -> None:
    findings = diagnose(
        "Error: Failed to create changeset for the stack sam-app: Waiter ChangeSetCreateComplete "
        'failed: Waiter encountered a terminal failure state: For expression "Status" we matched '
        'expected path: "FAILED" Status: FAILED. Reason: The submitted information didn\'t contain '
        "changes. Submit different information to create a change set."
    )

    assert len(findings) == 1
    assert (
        findings[0].title
        == "The deployment failed only because there were no changes to deploy"
    )


def test_changeset_wrapper_with_the_prefix_keeps_generic_handoff() -> None:
    findings = diagnose(
        "Failed to create the changeset: Waiter ChangeSetCreateComplete failed: "
        "Waiter encountered a terminal failure state: the complete reason was "
        "redacted from this excerpt"
    )

    assert [finding.rule_id for finding in findings] == [
        "sam.deploy.configuration-resolution-failed"
    ]


def test_unresolved_resource_dependency_routes_to_template_reference_check() -> None:
    findings = diagnose(
        "Failed to create the changeset: Waiter ChangeSetCreateComplete failed: "
        "Waiter encountered a terminal failure state: Template format error: "
        "Unresolved resource dependencies [Environment] in the Resources block "
        "of the template"
    )

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.template.unresolved-dependency"
    ]
    assert findings[0].confidence == "high"


def test_detects_cloudformation_deploy_empty_changeset_failure() -> None:
    findings = diagnose("No changes to deploy. Stack my-service-prod is up to date")

    assert len(findings) == 1
    assert "no changes to deploy" in findings[0].title.lower()


def test_changed_stack_deploy_output_is_not_an_empty_changeset_finding() -> None:
    assert (
        diagnose(
            "Successfully created/updated stack - my-service-prod. Changes deployed."
        )
        == []
    )
    assert (
        diagnose(
            "Changeset created successfully; waiting for stack update to complete."
        )
        == []
    )


def test_expired_wording_alone_is_not_a_credential_finding() -> None:
    assert (
        diagnose("The CloudFront distribution's TLS certificate expired last week.")
        == []
    )
    assert (
        diagnose(
            "Waiting for the changeset to be created; the rate of progress is slow."
        )
        == []
    )


def test_invalid_credentials_are_distinguished_from_expired_credentials() -> None:
    invalid_findings = diagnose(
        "Error: The security token included in the request is invalid"
    )
    assert len(invalid_findings) == 1
    assert "invalid or wrong-account" in invalid_findings[0].title.lower()

    expired_findings = diagnose(
        "An error occurred (ExpiredTokenException) when calling the AssumeRole "
        "operation: The security token included in the request is expired"
    )
    assert len(expired_findings) == 1
    assert "have expired" in expired_findings[0].title.lower()


def test_invalid_credentials_finding_defers_to_expired_credentials_when_both_appear() -> (
    None
):
    findings = diagnose(
        "Error: The security token included in the request is invalid\n"
        "An error occurred (ExpiredTokenException) when calling the AssumeRole "
        "operation: The security token included in the request is expired"
    )

    assert len(findings) == 1
    assert "have expired" in findings[0].title.lower()


def test_successful_identity_check_is_not_a_credential_finding() -> None:
    assert (
        diagnose(
            "aws sts get-caller-identity: {\n"
            '  "UserId": "AIDAEXAMPLE",\n'
            '  "Account": "REDACTED",\n'
            '  "Arn": "arn:aws:iam::123456789012:user/deploy"\n'
            "}"
        )
        == []
    )


def test_delete_wording_alone_is_not_a_deletion_finding() -> None:
    assert (
        diagnose(
            "DELETE_IN_PROGRESS then DELETE_COMPLETE; termination protection was already off."
        )
        == []
    )
    assert diagnose("Login Succeeded; pushed all layers to the registry.") == []


def test_iam_role_deletion_blocker_still_wins_over_general_delete_failed() -> None:
    log = (
        "MyStack DELETE_FAILED The following resource(s) failed to delete: [MyRole].\n"
        "Failed to delete AWS::IAM::Role MyRole"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert "CloudFormation rollback could not delete an IAM role" in titles
    assert "CloudFormation could not delete one or more stack resources" not in titles


def test_ecr_auth_denial_does_not_fire_the_generic_access_denied_rule() -> None:
    log = (
        "An error occurred (AccessDeniedException) when calling the GetAuthorizationToken "
        "operation: User: arn:aws:sts::123456789012:assumed-role/deploy-role/GitHubActions "
        "is not authorized to perform: ecr:GetAuthorizationToken on resource: * because no "
        "identity-based policy allows the ecr:GetAuthorizationToken action"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == ["The CI runner could not authenticate to ECR to push the image"]


def test_multiline_s3_denial_still_suppresses_generic_access_denied() -> None:
    log = (
        "MyLayer CREATE_FAILED AccessDeniedException\n"
        "Your access has been denied by S3, please make sure your request credentials\n"
        "have permission to GetObject\n"
        "for bucket layer-artifacts."
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert "AWS denied an API action required by the deployment" not in titles
    assert "CloudFormation resource creation or update failed" not in titles


def test_all_declarative_rule_patterns_compile() -> None:
    import re as _re

    from sam_doctor.diagnostics import supported_rules

    for rule in supported_rules():
        for pattern in rule.patterns + rule.suppressed_by + rule.excluded_line_patterns:
            _re.compile(pattern)


def test_packaged_cloudformation_demo_is_available() -> None:
    findings = diagnose(_read_demo("cloudformation"))

    assert any("resource creation" in finding.title.lower() for finding in findings)


def test_packaged_capability_demo_is_available() -> None:
    findings = diagnose(_read_demo("capabilities"))

    assert len(findings) == 1
    assert any(
        "explicit capability acknowledgement" in finding.title.lower()
        for finding in findings
    )


@pytest.mark.parametrize(
    ("scenario", "title_fragment"),
    (
        ("api-gateway", "API Gateway deployment started"),
        ("s3-bucket-conflict", "managed and explicit S3 bucket"),
        ("esbuild", "configured esbuild"),
        ("python-pip", "python dependency build validation"),
        ("interactive-changeset", "interactive changeset confirmation"),
    ),
)
def test_packaged_scenario_demos_are_available(
    scenario: str, title_fragment: str
) -> None:
    findings = diagnose(_read_demo(scenario))

    assert any(title_fragment.lower() in finding.title.lower() for finding in findings)


@pytest.mark.parametrize(
    "scenario",
    (
        "oidc",
        "cloudformation",
        "capabilities",
        "api-gateway",
        "s3-bucket-conflict",
        "esbuild",
        "python-pip",
        "interactive-changeset",
    ),
)
def test_demo_command_supports_scenarios(
    tmp_path, scenario: str, capsys: pytest.CaptureFixture[str]
) -> None:
    output_file = tmp_path / f"{scenario}.md"

    assert (
        main(
            [
                "demo",
                "--scenario",
                scenario,
                "--format",
                "json",
                "--output",
                output_file,
            ]
        )
        == 0
    )
    assert output_file.exists()

    captured = capsys.readouterr().out
    assert "Wrote json report" in captured


def test_redaction_covers_common_ci_credentials() -> None:
    text = (
        "AKIAIOSFODNN7EXAMPLE ghp_123456789012345678901234567890123456 "
        "AWS_SECRET_ACCESS_KEY=not-a-real-secret token: another-secret"
    )

    result = redact(text)

    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "ghp_123456789012345678901234567890123456" not in result
    assert "not-a-real-secret" not in result
    assert "another-secret" not in result
    assert "[REDACTED_AWS_ACCESS_KEY]" in result
    assert "[REDACTED_GITHUB_TOKEN]" in result
    assert result.count("[REDACTED_SECRET]") == 2


def test_redaction_covers_bare_session_tokens() -> None:
    token = "IQoJb3JpZ2luX2VjENr" + "A1b2C3d4" * 12
    # Assembled at runtime so secret scanners don't flag a literal key in source.
    access_key_id = "ASIA" + "IOSFODNN7EXAMPLE"
    result = redact(f"Credentials: AccessKeyId={access_key_id} SessionToken={token}")

    assert token not in result
    assert "[REDACTED_AWS_SESSION_TOKEN]" in result
    # A short base64-looking word with the same prefix is left alone.
    assert redact("IQoJb3JpZ2lu is a prefix") == "IQoJb3JpZ2lu is a prefix"


def test_redaction_covers_quoted_secret_values() -> None:
    text = (
        'password="hunter2" '
        "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' "
        "api_key: `topsecret123` "
        '"github_token": "not-a-real-token"'
    )

    result = redact(text)

    assert "hunter2" not in result
    assert "wJalrXUtnFEMI" not in result
    assert "topsecret123" not in result
    assert "not-a-real-token" not in result
    assert result.count("[REDACTED_SECRET]") == 4


def test_redaction_leaves_non_secret_identifiers_alone() -> None:
    text = (
        "secretsmanager:GetSecretValue failed for MyStack-TokenRotator "
        "while reading parameter /app/password-policy"
    )

    assert redact(text) == text


@pytest.mark.parametrize(
    "line",
    [
        "DB_PASSWORD=hunter2",
        "DATABASE_PASSWORD: hunter2",
        "MY_API_KEY=abc123xyz456",
        "APP_SECRET=shhhhhhh",
        "x-api-key=abc123xyz456",
        "STRIPE_SECRET=sk_live_abcdef123456",
    ],
)
def test_redaction_covers_prefixed_secret_variable_names(line: str) -> None:
    # Environment variables are conventionally UPPER_SNAKE_CASE with a prefix,
    # and `_` is a word character - so a leading \b on the keyword never matched
    # between the prefix and the keyword. The bare `password=` form was redacted
    # while `DB_PASSWORD=` was not, which is the spelling that actually shows up
    # in a Lambda environment-variable failure.
    result = redact(line)

    assert "hunter2" not in result
    assert "abc123xyz456" not in result
    assert "shhhhhhh" not in result
    assert "sk_live_abcdef123456" not in result
    assert "[REDACTED_SECRET]" in result


def test_redaction_keeps_the_variable_name_it_redacts() -> None:
    # The name is the useful half: it says which secret to rotate.
    assert redact("DB_PASSWORD=hunter2").startswith("DB_PASSWORD=")


@pytest.mark.parametrize(
    ("line", "secret"),
    [
        (
            "fetch failed https://user:p4ssw0rd@artifacts.internal/app.zip",
            "p4ssw0rd",
        ),
        # A single-label internal host has no dot, so the email pattern that used
        # to catch this incidentally does not match - the credential leaked in
        # full. `git clone https://oauth2:$TOKEN@host/repo` is ordinary in CI.
        ("fetch failed https://user:p4ssw0rd@localhost/app.zip", "p4ssw0rd"),
        (
            "git clone https://oauth2:glpat-abcdefghijklmnopqrst@gitlab/team/repo.git",
            "glpat-abcdefghijklmnopqrst",
        ),
        # Token-as-username: the single value *is* the credential.
        (
            "git clone https://glpat-abcdefghijklmnopqrst@gitlab/team/repo.git",
            "glpat-abcdefghijklmnopqrst",
        ),
        (
            "Error connecting: postgres://admin:S3cr3tPass@db.internal:5432/orders",
            "S3cr3tPass",
        ),
    ],
)
def test_redaction_covers_credentials_embedded_in_a_url(line: str, secret: str) -> None:
    result = redact(line)

    assert secret not in result
    assert "[REDACTED_URL_CREDENTIAL]" in result
    # Mislabelling a credential as an email address hides what actually leaked.
    assert "[REDACTED_EMAIL]" not in result


_DOCKER_UNAVAILABLE_TITLE = "SAM build requires Docker for containerized builds"
_REGISTRY_TITLE = "The build could not pull a container image from the registry"
_DISK_FULL_TITLE = "The build host ran out of disk space"


def test_an_unreachable_docker_daemon_still_reports_the_docker_rule() -> None:
    log = (
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. "
        "Is the docker daemon running?"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _DOCKER_UNAVAILABLE_TITLE in titles


@pytest.mark.parametrize(
    ("log", "expected"),
    [
        (
            (
                "Error response from daemon: pull access denied for myco/base, "
                "repository does not exist or may require 'docker login'"
            ),
            _REGISTRY_TITLE,
        ),
        (
            (
                "Error response from daemon: manifest for myco/base:v9 not "
                "found: manifest unknown"
            ),
            _REGISTRY_TITLE,
        ),
        ("failed to write layer: no space left on device", _DISK_FULL_TITLE),
        ("npm ERR! nospc ENOSPC: no space left on device", _DISK_FULL_TITLE),
    ],
)
def test_a_daemon_response_is_not_reported_as_an_unavailable_daemon(
    log: str, expected: str
) -> None:
    # `Error response from daemon` means the daemon replied, so it is running.
    # Matching that phrase reported a pull denial, a missing tag and a full disk
    # as "Docker is unavailable", each with the wrong fix.
    titles = [finding.title for finding in diagnose(log)]
    assert expected in titles
    assert _DOCKER_UNAVAILABLE_TITLE not in titles


def test_a_login_failure_keeps_the_ecr_auth_finding() -> None:
    # The two rules cannot match the same line, so no suppression is needed
    # between them: an unauthenticated push reports the ECR finding and nothing
    # from the registry rule.
    titles = [finding.title for finding in diagnose("no basic auth credentials")]
    assert "The CI runner could not authenticate to ECR to push the image" in titles
    assert _REGISTRY_TITLE not in titles


def test_a_push_auth_failure_and_a_pull_refusal_both_report() -> None:
    # Two real failures in one job: the runner could not authenticate to push,
    # and a pull was refused. Neither should hide the other.
    log = (
        "no basic auth credentials\n"
        "Error response from daemon: pull access denied for myco/base, "
        "repository does not exist or may require 'docker login'"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The CI runner could not authenticate to ECR to push the image" in titles
    assert _REGISTRY_TITLE in titles


def test_a_successful_image_pull_reports_nothing() -> None:
    log = (
        "Status: Downloaded newer image for public.ecr.aws/sam/build-python3.12:latest\n"
        "Filesystem 58G used 21G available /home/runner"
    )

    assert list(diagnose(log)) == []


_PY_DEP_TITLE = "SAM Python dependency resolution failed"


def test_a_successful_python_build_reports_no_dependency_failure() -> None:
    # `Running PythonPipBuilder:ResolveDependencies` is ordinary progress output
    # printed by every successful Python build. Matching the bare token reported
    # a high-confidence dependency failure for a clean build.
    log = (
        "Building codeuri: /workspace/src runtime: python3.12 architecture: x86_64\n"
        "Running PythonPipBuilder:ResolveDependencies\n"
        "Running PythonPipBuilder:CopySource\n"
        "Build Succeeded\n"
        "Successfully created/updated stack - my-app in us-east-1"
    )

    assert list(diagnose(log)) == []


def test_a_successful_python_build_does_not_hide_a_later_deploy_failure() -> None:
    # The same token was also a whole-log `suppressed_by` pattern, so merely
    # having built with pip switched the change-set rule off - the tool reported
    # a failure that had not happened and hid the one that had.
    log = (
        "Running PythonPipBuilder:ResolveDependencies\n"
        "Build Succeeded\n"
        "Error: Failed to create changeset for the stack: my-app\n"
        "Parameter 'Stage' must have values"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _PY_DEP_TITLE not in titles
    assert "AWS SAM deployment configuration or parameter resolution failed" in titles


@pytest.mark.parametrize(
    "log",
    [
        (
            "Error: PythonPipBuilder:ResolveDependencies - {pip_failure_reason: "
            "ERROR: Could not find a version that satisfies the requirement "
            "pydantic-core==2.18.4}"
        ),
        "Could not find a version that satisfies the requirement pydantic-core==2.18.4",
    ],
)
def test_a_real_python_dependency_failure_is_still_detected(log: str) -> None:
    titles = [finding.title for finding in diagnose(log)]
    assert _PY_DEP_TITLE in titles


def test_redaction_leaves_ordinary_urls_alone() -> None:
    for text in (
        "see https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html",
        "https://github.com/jakegold1647/sam-doctor",
        "Uploading to my-bucket/artifact.zip (100%)",
        "tokenizer=fast",
    ):
        assert redact(text) == text


def test_redaction_covers_bearer_and_jwt_style_tokens() -> None:
    bearer_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJydW4ifQ.signaturevalue123"
    result = redact(f"Authorization: Bearer {bearer_token} standalone {bearer_token}")

    assert bearer_token not in result
    assert "Authorization: Bearer [REDACTED_BEARER_TOKEN]" in result
    assert "standalone [REDACTED_JWT]" in result


def test_markdown_report_escapes_log_markup() -> None:
    findings = diagnose("AccessDeniedException: <script>alert('x')</script>")

    report = markdown_report(findings, "failed`<log>.txt")

    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "failed`<log>.txt" not in report
    assert "failed`&lt;log&gt;.txt" in report


def test_reports_redact_sensitive_source_names() -> None:
    findings = diagnose("AccessDeniedException: action is not authorized")
    source_name = "owner@example.com-123456789012-deployment.log"

    markdown = markdown_report(findings, source_name)
    terminal = terminal_report(findings, source_name)
    report = json.loads(json_report(findings, source_name))

    assert "owner@example.com" not in markdown + terminal
    assert "123456789012" not in markdown + terminal
    assert report["source"] == "[REDACTED_EMAIL]-[REDACTED_ACCOUNT_ID]-deployment.log"


def test_dash_reads_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("a deployment log"))

    assert _read_text(Path("-")) == "a deployment log"


def test_write_report_wraps_os_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Could not write"):
        _write_report(tmp_path / "missing" / "report.md", "report")


def test_json_report_is_redacted_and_machine_readable() -> None:
    findings = diagnose(
        "AccessDeniedException for arn:aws:iam::123456789012:role/deploy owner@example.com"
    )

    report = json.loads(json_report(findings, "failure.log"))

    assert report["finding_count"] == 1
    assert report["findings"][0]["line_number"] == 1
    assert report["sam_doctor_version"] == __version__
    assert report["source"] == "failure.log"
    assert "[REDACTED_ARN]" in report["findings"][0]["evidence"][0]
    assert "123456789012" not in json_report(findings, "failure.log")


def test_long_evidence_is_bounded() -> None:
    findings = diagnose(
        "prefix " + ("x" * 500) + " AccessDeniedException " + ("y" * 500)
    )

    evidence = findings[0].evidence[0]

    assert len(evidence) <= 360
    assert "..." in evidence


def test_rule_catalog_is_machine_readable() -> None:
    catalog = json.loads(rules_report("json"))
    _assert_json_schema_matches("docs/schemas/rules-report.schema.json", catalog)

    assert catalog["rule_count"] >= 7
    assert catalog["sam_doctor_version"] == __version__
    assert any("CloudFormation resource" in rule["title"] for rule in catalog["rules"])


def test_rules_command_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["rules", "--format", "json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["rule_count"] >= 7


def test_schemas_command_prints_schema_locations(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["schemas"]) == 0
    output = capsys.readouterr().out

    assert "diagnose:" in output
    assert "batch:" in output
    assert "rules:" in output
    assert "docs/schemas/" in output


def test_schemas_command_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["schemas", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["diagnose"].endswith("diagnose-report.schema.json")
    assert output["batch"].endswith("batch-report.schema.json")
    assert output["rules"].endswith("rules-report.schema.json")


def test_batch_command_analyzes_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "first.log").write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8"
    )
    (logs / "second.txt").write_text(
        "Everything completed successfully.", encoding="utf-8"
    )

    assert main(["batch", str(logs), "--format", "terminal"]) == 0
    output = capsys.readouterr().out

    assert "first.log" in output
    assert "second.log" not in output
    assert "second.txt" in output
    assert "AccessDenied" not in output
    assert "GitHub Actions cannot assume the configured AWS role through OIDC" in output


def test_batch_command_json_has_aggregate_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.txt").write_text(
        "The REST API doesn't contain any methods", encoding="utf-8"
    )
    (tmp_path / "b.log").write_text(
        "sam deploy completed successfully", encoding="utf-8"
    )

    assert (
        main(
            [
                "batch",
                str(tmp_path / "a.txt"),
                str(tmp_path / "b.log"),
                "--format",
                "json",
            ]
        )
        == 0
    )

    report = json.loads(capsys.readouterr().out)
    assert report["batch_count"] == 2
    assert any(entry["finding_count"] == 1 for entry in report["results"])


def test_batch_command_analyzes_overlapping_inputs_once(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    log = logs / "deploy.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert main(["batch", "logs", str(log), "--format", "json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["batch_count"] == 1
    assert len(report["results"]) == 1
    assert report["results"][0]["source"] == "logs/deploy.log"
    assert report["results"][0]["finding_count"] == 1


def test_batch_command_analyzes_symlink_alias_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "deploy.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )
    alias = tmp_path / "linked.log"
    try:
        alias.symlink_to(log)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    assert main(["batch", str(alias), str(log), "--format", "json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["batch_count"] == 1
    assert len(report["results"]) == 1
    assert report["results"][0]["source"] == alias.as_posix()


def test_batch_render_github_emits_annotations_only_for_findings(
    tmp_path: Path,
) -> None:
    from sam_doctor.cli import _batch_render

    finding_log = tmp_path / "with_finding.log"
    clean_log = tmp_path / "clean.log"
    finding_log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8"
    )
    clean_log.write_text("sam deploy completed successfully", encoding="utf-8")

    report, has_findings = _batch_render(
        [str(finding_log), str(clean_log)],
        "github",
    )

    assert has_findings
    lines = [line for line in report.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("::notice ")
    assert "with_finding.log" in lines[0]


def test_github_notices_from_json_payload_skips_noise() -> None:
    from sam_doctor.cli import github_notices_from_payload

    payload = {
        "sam_doctor_version": __version__,
        "batch": True,
        "results": [
            {
                "source": "with-finding.log",
                "finding_count": 1,
                "findings": [
                    {
                        "title": "SAM deployment prompt",
                        "confidence": "high",
                        "explanation": "A prompt blocked automation.",
                        "verification": ["Set --no-confirm-changeset."],
                        "documentation_url": "https://docs.aws.com/",
                        "evidence": ["Deploy this changeset? [y/N]:"],
                        "line_number": 12,
                    }
                ],
            },
            {
                "source": "clean.log",
                "finding_count": 0,
                "findings": [],
            },
        ],
    }

    output = github_notices_from_payload(payload, True)

    assert output.count("\n") == 1
    assert "with-finding.log" in output
    assert "clean.log" not in output


def test_batch_command_does_not_fail_without_fail_on_findings(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text(
        "The REST API doesn't contain any methods", encoding="utf-8"
    )
    (tmp_path / "b.log").write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "batch",
                str(tmp_path / "a.txt"),
                str(tmp_path / "b.log"),
                "--format",
                "json",
            ],
        )
        == 0
    )


def test_batch_command_fails_with_fail_on_findings(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text(
        "The REST API doesn't contain any methods", encoding="utf-8"
    )
    (tmp_path / "b.log").write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "batch",
                str(tmp_path / "a.txt"),
                str(tmp_path / "b.log"),
                "--format",
                "json",
                "--fail-on-findings",
            ]
        )
        == 1
    )


def test_main_returns_exit_code_2_for_usage_and_input_errors(tmp_path: Path) -> None:
    assert main([]) == 2
    assert main(["diagnose"]) == 2

    missing = tmp_path / "missing.log"
    assert main(["diagnose", str(missing)]) == 2


def test_init_command_writes_starter_workflow(tmp_path: Path, capsys) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sam-doctor.yml"

    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(workflow),
            ]
        )
        == 0
    )

    assert workflow.exists()
    assert "Wrote workflow file" in capsys.readouterr().out
    text = workflow.read_text(encoding="utf-8")
    assert "uses: jakegold1647/sam-doctor@v0" in text
    assert "sam deploy --no-confirm-changeset" in text
    assert "has-findings" in text
    assert "summary: true" in text
    assert "annotations: true" in text
    assert "batch: false" in text
    assert "fail-on-findings: false" in text
    assert "workflow_dispatch" in text
    assert "push:" not in text
    assert "branches: [main]" not in text


def test_init_command_defaults_to_no_push_trigger(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sam-doctor.yml"

    assert main(["init", "--workflow-file", str(workflow)]) == 0

    text = workflow.read_text(encoding="utf-8")
    assert "on:\n  # Manual only" in text
    assert "workflow_dispatch: {}" in text
    assert "push:" not in text


def test_init_command_on_push_opts_into_push_trigger(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sam-doctor.yml"

    assert main(["init", "--workflow-file", str(workflow), "--on-push"]) == 0

    text = workflow.read_text(encoding="utf-8")
    assert "push:\n    branches: [main]" in text
    assert "workflow_dispatch: {}" in text


@pytest.mark.parametrize("extra_args", [[], ["--on-push"]])
def test_init_emits_a_usable_github_expression(
    extra_args: list[str], tmp_path: Path
) -> None:
    # The template is rendered with str.format(), which collapses `{{` to `{`.
    # Writing the expression as `${{ ... }}` therefore emitted `${ ... }`, which
    # GitHub does not interpolate - and that line is commented out for the user
    # to uncomment, so it has to be right when they do.
    workflow = tmp_path / "sam-doctor.yml"

    assert main(["init", "--workflow-file", str(workflow), *extra_args]) == 0

    text = workflow.read_text(encoding="utf-8")
    assert "${{ steps.sam-doctor.outputs.finding-count }}" in text
    # No single-brace expression anywhere: that is the shape that silently fails.
    assert not re.search(r"\$\{(?!\{)", text)


def test_init_command_rejects_existing_file_without_force(
    tmp_path: Path, capsys
) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sam-doctor.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text("existing", encoding="utf-8")

    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(workflow),
            ]
        )
        == 2
    )
    assert "already exists" in capsys.readouterr().err


def test_init_command_custom_deploy_command(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sam-doctor.yml"
    custom = "sam sync --no-confirm-changeset"

    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(workflow),
                "--deploy-command",
                custom,
                "--force",
            ]
        )
        == 0
    )
    assert custom in workflow.read_text(encoding="utf-8")


def test_init_command_supports_ci_options(tmp_path: Path) -> None:
    workflow = tmp_path / ".github" / "workflows" / "sam-doctor.yml"
    custom = "sam sync --no-confirm-changeset"

    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(workflow),
                "--deploy-command",
                custom,
                "--no-summary",
                "--no-annotations",
                "--batch",
                "--fail-on-findings",
                "--force",
            ]
        )
        == 0
    )

    text = workflow.read_text(encoding="utf-8")
    assert "summary: false" in text
    assert "annotations: false" in text
    assert "batch: true" in text
    assert "fail-on-findings: true" in text
    assert custom in text


def test_main_returns_zero_for_help_request() -> None:
    assert main(["--help"]) == 0
    assert main(["batch", "--help"]) == 0


def test_help_includes_exit_code_guide(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    assert "Exit codes:" in output
    assert "GitHub Action behavior:" in output
    assert "Command behavior:" in output
    assert (
        "diagnose: default exit 0 (no enforced failure), 1 with --fail-on-findings"
        in output
    )
    assert (
        "batch: default exit 0 (no enforced failure), 1 with --fail-on-findings"
        in output
    )
    assert "--fail-on-confidence threshold" in output


def test_batch_command_preserves_path_for_duplicate_filenames(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first_dir = tmp_path / "run1"
    second_dir = tmp_path / "run2"
    first_dir.mkdir()
    second_dir.mkdir()

    first_file = first_dir / "duplicate.log"
    second_file = second_dir / "duplicate.log"
    first_file.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8"
    )
    second_file.write_text("The REST API doesn't contain any methods", encoding="utf-8")

    assert main(["batch", str(first_dir), str(second_dir), "--format", "terminal"]) == 0

    output = capsys.readouterr().out
    assert first_file.as_posix() in output
    assert second_file.as_posix() in output


def test_batch_markdown_output_includes_file_sections(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first_file = tmp_path / "first.log"
    second_file = tmp_path / "second.log"
    first_file.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8"
    )
    second_file.write_text(
        "AccessDeniedException: action is not authorized", encoding="utf-8"
    )

    assert (
        main(["batch", str(first_file), str(second_file), "--format", "markdown"]) == 0
    )

    output = capsys.readouterr().out
    assert "## Source:" in output
    assert first_file.as_posix() in output
    assert second_file.as_posix() in output


def test_diagnose_can_fail_on_findings_after_writing_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "failure.log"
    report = tmp_path / "diagnosis.json"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "diagnose",
                log,
                "--format",
                "json",
                "--output",
                report,
                "--fail-on-findings",
            ]
        )
        == 1
    )
    assert report.exists()
    assert "Wrote json report" in capsys.readouterr().out


def test_diagnose_fail_on_findings_stays_zero_for_unknown_logs(
    tmp_path: Path,
) -> None:
    log = tmp_path / "success.log"
    log.write_text("Deployment completed successfully.", encoding="utf-8")

    assert main(["diagnose", log, "--fail-on-findings"]) == 0


def test_render_findings_matches_report_format_selection() -> None:
    findings = diagnose("AccessDeniedException: action is not authorized")

    assert "## 1." in _render_findings(findings, "failure.log", "markdown")
    assert '"finding_count": 1' in _render_findings(findings, "failure.log", "json")
    assert "SAM Doctor found 1 possible issue" in _render_findings(
        findings, "failure.log", "terminal"
    )


def test_render_findings_github_emits_one_or_more_annotations() -> None:
    findings = diagnose("Not authorized to perform: sts:AssumeRoleWithWebIdentity")

    output = _render_findings(findings, "deployment.log", "github")

    assert output.count("::notice") >= 1
    assert "file=deployment.log" in output
    assert "line=1" in output
    assert "GitHub Actions cannot assume the configured AWS role through OIDC" in output


def test_render_findings_github_escapes_workflow_command_delimiters() -> None:
    findings = diagnose("Not authorized to perform: sts:AssumeRoleWithWebIdentity")

    output = _render_findings(
        findings, "C:\\logs\\deploy,percent 100%\nrun.log", "github"
    )

    assert "file=C%3A\\logs\\deploy%2Cpercent 100%25%0Arun.log" in output
    # One annotation line per finding: the raw newline in the source name must
    # not split the workflow command.
    assert output.count("\n") == len(findings)
    assert all(
        line.startswith("::notice ") for line in output.rstrip("\n").splitlines()
    )


def test_explicit_scp_deny_gets_the_specific_finding_with_parsed_context() -> None:
    log = (
        "An error occurred (AccessDeniedException) when calling the CreateRole operation: "
        "User: arn:aws:sts::123456789012:assumed-role/deploy-role/GitHubActions is not "
        "authorized to perform: iam:CreateRole on resource: "
        "arn:aws:iam::123456789012:role/app-role with an explicit deny in a service "
        "control policy"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == ["An explicit deny blocked a deployment action"]
    explanation = findings[0].explanation
    assert "Denial context parsed from the evidence" in explanation
    assert "`iam:CreateRole`" in explanation
    assert "service control policy" in explanation
    assert "123456789012" not in explanation
    assert all("123456789012" not in evidence for evidence in findings[0].evidence)


def test_implicit_deny_gets_the_specific_finding_and_names_the_layer() -> None:
    log = (
        "An error occurred (AccessDeniedException) when calling the PutObject operation: "
        "User: arn:aws:iam::123456789012:user/deploy is not authorized to perform: "
        "s3:PutObject on resource: arn:aws:s3:::artifact-bucket/app.zip because no "
        "identity-based policy allows the s3:PutObject action"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == ["A deployment action was denied because no policy allows it"]
    explanation = findings[0].explanation
    assert "Denial context parsed from the evidence" in explanation
    assert "`s3:PutObject`" in explanation
    assert "no identity-based policy allows it" in explanation


def test_bare_access_denied_still_reports_the_generic_rule_without_context() -> None:
    log = (
        "Deployment step reached AWS\n"
        "An error occurred (AccessDenied) when calling the DescribeStacks operation"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == ["AWS denied an API action required by the deployment"]
    assert "Denial context parsed from the evidence" not in findings[0].explanation


def test_mixed_denials_report_the_specific_and_generic_rules_side_by_side() -> None:
    log = (
        "User: arn:aws:iam::123456789012:user/deploy is not authorized to perform: "
        "cloudformation:CreateChangeSet with an explicit deny\n"
        "Later: An error occurred (AccessDenied) when calling the DescribeStacks operation"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert "An explicit deny blocked a deployment action" in titles
    assert "AWS denied an API action required by the deployment" in titles


def test_changeset_readback_denial_names_the_deployment_bucket() -> None:
    log = (
        "Error: Failed to create changeset for the stack: my-app, An error "
        "occurred (ValidationError) when calling the CreateChangeSet "
        "operation: S3 error: Access Denied"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == ["The deployment bucket denied access to the packaged artifacts"]
    explanation = findings[0].explanation
    assert "Readback" in explanation
    assert "Upload" in explanation


def test_artifact_upload_denial_gets_the_deployment_bucket_finding() -> None:
    log = (
        "Error uploading to my-deploy-bucket: An error occurred (AccessDenied) "
        "when calling the PutObject operation: Access Denied "
        "(Service: S3, Status Code: 403)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert titles == ["The deployment bucket denied access to the packaged artifacts"]


def test_a_non_s3_access_denial_keeps_the_iam_denial_findings() -> None:
    log = (
        "An error occurred (AccessDenied) when calling the CreateChangeSet "
        "operation: User: arn:aws:iam::123456789012:user/deploy is not "
        "authorized to perform: cloudformation:CreateChangeSet on resource: "
        "arn:aws:cloudformation:us-east-1:123456789012:stack/my-app/* with an "
        "explicit deny in an identity-based policy"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The deployment bucket denied access to the packaged artifacts" not in titles
    assert titles == ["An explicit deny blocked a deployment action"]


def test_an_iam_worded_s3_denial_stays_with_the_policy_layer_finding() -> None:
    log = (
        "An error occurred (AccessDenied) when calling the PutObject operation: "
        "User: arn:aws:iam::123456789012:user/deploy is not authorized to "
        "perform: s3:PutObject on resource: arn:aws:s3:::my-deploy-bucket/app.zip "
        "with an explicit deny in a resource-based policy"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The deployment bucket denied access to the packaged artifacts" not in titles
    assert "An explicit deny blocked a deployment action" in titles


_TAG_DENIED_TITLE = "AWS denied a tagging action required by the deployment"
_TAG_VALIDATION_TITLE = "A tag key or value was rejected by validation"


def test_tag_on_create_denial_gets_the_tagging_finding() -> None:
    log = (
        "An error occurred (AccessDenied) when calling the CreateRole "
        "operation: User: arn:aws:iam::123456789012:user/deploy is not "
        "authorized to perform: iam:TagRole on resource: role my-app-role"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _TAG_DENIED_TITLE in titles
    # The denied action is the tag, so the generic denial would only restate it
    # less usefully.
    assert "AWS denied an API action required by the deployment" not in titles


def test_tag_denial_names_the_denied_action_in_its_context() -> None:
    log = (
        "An error occurred (AccessDenied) when calling the CreateFunction "
        "operation: User is not authorized to perform: lambda:TagResource on "
        "resource: function my-app-fn"
    )

    findings = [f for f in diagnose(log) if f.title == _TAG_DENIED_TITLE]
    assert findings, "the tagging rule did not fire"
    assert "lambda:TagResource" in findings[0].explanation


@pytest.mark.parametrize(
    "action",
    (
        "application-autoscaling:TagResource",
        "application-autoscaling:UntagResource",
        "iam:TagRole",
        "iam:UntagRole",
        "lambda:TagResource",
        "ec2:CreateTags",
        "ec2:DeleteTags",
        "rds:AddTagsToResource",
        "rds:RemoveTagsFromResource",
    ),
)
def test_tagging_action_variants_get_the_specific_finding(action: str) -> None:
    log = (
        "An error occurred (AccessDenied) when calling the resource operation: "
        f"User is not authorized to perform: {action} on resource: example"
    )

    findings = diagnose(log)
    assert [finding.rule_id for finding in findings] == ["iam.tag.action-denied"]
    assert action in findings[0].explanation


@pytest.mark.parametrize(
    "policy_reason",
    (
        "with an explicit deny in a service control policy",
        "because no identity-based policy allows the ec2:CreateTags action",
    ),
)
def test_tag_denial_outranks_each_generic_iam_shape(policy_reason: str) -> None:
    log = (
        "User is not authorized to perform: ec2:CreateTags on resource: * "
        f"{policy_reason}"
    )

    assert [finding.rule_id for finding in diagnose(log)] == [
        "iam.tag.action-denied"
    ]


@pytest.mark.parametrize(
    "denial",
    (
        "not authorized to perform APPLICATION-AUTOSCALING:tagresource",
        "not authorized to perform: application-autoscaling:TagResource,",
    ),
)
def test_tag_denial_accepts_runtime_format_variants(denial: str) -> None:
    log = f"AccessDenied: User is {denial} on resource: example"

    assert [finding.rule_id for finding in diagnose(log)] == [
        "iam.tag.action-denied"
    ]


@pytest.mark.parametrize(
    "action",
    (
        "application-autoscaling:ListTagsForResource",
        "iam:ListRoleTags",
        "ec2:DescribeTags",
        "ec2:UpdateCapacityManagerMonitoredTagKeys",
        "servicecatalog:CreateTagOption",
        "ec2:CreateTagsExtra",
        "iam:CreateRole",
    ),
)
def test_a_non_mutating_tags_action_keeps_the_generic_iam_finding(
    action: str,
) -> None:
    log = (
        "An error occurred (AccessDenied) when calling an operation: User is "
        f"not authorized to perform: {action} on resource: *"
    )

    rule_ids = [finding.rule_id for finding in diagnose(log)]
    assert "iam.tag.action-denied" not in rule_ids
    assert "iam.access-denied.generic" in rule_ids


def test_a_tag_action_mention_without_denial_wording_is_not_a_finding() -> None:
    log = "Grant application-autoscaling:TagResource with RegisterScalableTarget."

    assert diagnose(log) == []


def test_a_non_tag_denial_in_the_same_log_still_reports_the_iam_denial() -> None:
    # The roadmap requirement for this rule: claiming the tag line must not
    # silence an unrelated denial that happens to share the log.
    log = (
        "An error occurred (AccessDenied) when calling the CreateRole "
        "operation: User is not authorized to perform: iam:TagRole on "
        "resource: role my-app-role\n"
        "An error occurred (AccessDenied) when calling the CreateChangeSet "
        "operation: User is not authorized to perform: "
        "cloudformation:CreateChangeSet because no identity-based policy "
        "allows the cloudformation:CreateChangeSet action"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _TAG_DENIED_TITLE in titles
    assert "A deployment action was denied because no policy allows it" in titles


def test_a_denial_on_the_create_action_is_not_reported_as_a_tagging_problem() -> None:
    log = (
        "An error occurred (AccessDenied) when calling the CreateRole "
        "operation: User is not authorized to perform: iam:CreateRole on "
        "resource: role my-app-role"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _TAG_DENIED_TITLE not in titles
    assert "AWS denied an API action required by the deployment" in titles


def test_a_benign_tag_listing_does_not_report_a_tag_finding() -> None:
    log = "Tags: Environment=prod, Team=platform, CostCenter=1234"

    titles = [finding.title for finding in diagnose(log)]
    assert _TAG_DENIED_TITLE not in titles
    assert _TAG_VALIDATION_TITLE not in titles


def test_reserved_tag_prefix_reports_the_validation_finding() -> None:
    log = (
        "1 validation error detected: Value 'aws:team' at "
        "'tags.1.member.key' failed to satisfy constraint: Member must "
        "satisfy regular expression pattern"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _TAG_VALIDATION_TITLE in titles
    # A rejected tag key is a template problem; reporting it as a permission
    # failure would send the reader to the wrong place entirely.
    assert _TAG_DENIED_TITLE not in titles
    assert "AWS denied an API action required by the deployment" not in titles


def test_tag_value_validation_failure_reports_the_validation_finding() -> None:
    log = (
        "1 validation error detected: Value 'build 12:34' at "
        "'tags.3.member.value' failed to satisfy constraint: Member must "
        "satisfy regular expression pattern"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _TAG_VALIDATION_TITLE in titles


_KMS_ENV_TITLE = "Lambda could not use the KMS key for its environment variables"


def test_kms_env_var_failure_gets_the_kms_finding() -> None:
    log = (
        "CREATE_FAILED  AWS::Lambda::Function  Worker  Lambda was unable to "
        "configure access to your environment variables because the KMS key is "
        "invalid for CreateGrant. Please check your KMS key settings. KMS "
        "Exception: InvalidArnException (Service: Lambda, Status Code: 400; "
        "Error Code: InvalidParameterValueException)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _KMS_ENV_TITLE in titles
    # CloudFormation prints the status reason on the same line as the event, so
    # the generic resource-failure rule would restate this one less usefully.
    assert "CloudFormation resource creation or update failed" not in titles


def test_a_kms_denial_is_not_routed_to_the_generic_iam_denial() -> None:
    # The point of the rule: this line contains AccessDeniedException, and the
    # generic denial would send the reader to the IAM policy simulator when the
    # thing to review is the KMS key policy.
    log = (
        "KMS Exception: AccessDeniedException The ciphertext refers to a "
        "customer master key that does not exist, does not exist in this "
        "region, or you are not allowed to access."
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _KMS_ENV_TITLE in titles
    assert "AWS denied an API action required by the deployment" not in titles


def test_a_disabled_kms_key_gets_the_kms_finding() -> None:
    log = (
        "UPDATE_FAILED  AWS::Lambda::Function  Worker  Lambda was unable to "
        "configure your environment variables because the environment "
        "variables you have provided contains reserved keys or the KMS key "
        "provided is disabled. KMS Exception: DisabledException (Error Code: "
        "InvalidParameterValueException)"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _KMS_ENV_TITLE in titles


def test_a_non_lambda_kms_exception_keeps_the_generic_findings() -> None:
    log = (
        "CREATE_FAILED AWS::S3::Bucket ArtifactBucket "
        "KMS Exception: AccessDeniedException"
    )

    rule_ids = [finding.rule_id for finding in diagnose(log)]
    assert "lambda.env-vars.kms-key-inaccessible" not in rule_ids
    assert "iam.access-denied.generic" in rule_ids
    assert "cloudformation.resource.create-update-failed" in rule_ids


def test_reserved_lambda_environment_keys_are_not_a_kms_failure() -> None:
    log = (
        "UPDATE_FAILED AWS::Lambda::Function Worker Lambda was unable to "
        "configure your environment variables because the environment "
        "variables you have provided contain reserved keys."
    )

    rule_ids = [finding.rule_id for finding in diagnose(log)]
    assert "lambda.env-vars.kms-key-inaccessible" not in rule_ids
    assert "cloudformation.resource.create-update-failed" in rule_ids


@pytest.mark.parametrize(
    "near_miss",
    (
        "KMS Exception: DisabledException",
        "KMS Exception: AccessDeniedException while decrypting an unrelated key",
        (
            "The ciphertext refers to a customer master key that does not exist, "
            "does not exist in this region, or you are not allowed to access."
        ),
    ),
)
def test_kms_signals_without_lambda_context_do_not_claim_the_rule(
    near_miss: str,
) -> None:
    assert "lambda.env-vars.kms-key-inaccessible" not in {
        finding.rule_id for finding in diagnose(near_miss)
    }


def test_lambda_kms_failure_keeps_unrelated_generic_failures_visible() -> None:
    log = (
        "CREATE_FAILED AWS::Lambda::Function Worker Lambda was unable to "
        "configure access to your environment variables. KMS Exception: "
        "AccessDeniedException\n"
        "AccessDeniedException when calling the sqs:ListQueues operation\n"
        "CREATE_FAILED AWS::DynamoDB::Table Orders Resource handler returned "
        "message: throughput exceeded"
    )

    assert {finding.rule_id for finding in diagnose(log)} >= {
        "lambda.env-vars.kms-key-inaccessible",
        "iam.access-denied.generic",
        "cloudformation.resource.create-update-failed",
    }


def test_kms_guidance_covers_both_roles_and_redeployment() -> None:
    log = (
        "KMS Exception: AccessDeniedException The ciphertext refers to a "
        "customer master key that does not exist, does not exist in this "
        "region, or you are not allowed to access."
    )

    finding = next(
        finding
        for finding in diagnose(log)
        if finding.rule_id == "lambda.env-vars.kms-key-inaccessible"
    )
    guidance = " ".join(finding.verification)
    assert "deploying principal and the function's execution role" in guidance
    assert "kms:CreateGrant" in guidance
    assert "kms:Decrypt" in guidance
    assert "redeploy" in guidance


def test_a_successful_env_var_configuration_reports_no_kms_finding() -> None:
    log = (
        "Environment variables encrypted with the customer managed key were "
        "configured for Worker"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _KMS_ENV_TITLE not in titles


_SSM_TITLE = "An SSM parameter referenced by the template could not be resolved"
_SAM_CONFIG_TITLE = "AWS SAM deployment configuration or parameter resolution failed"


def test_unresolvable_ssm_reference_gets_the_ssm_finding() -> None:
    log = "Parameters: [ssm:/my-app/prod/db-password] cannot be found."

    titles = [finding.title for finding in diagnose(log)]
    assert _SSM_TITLE in titles


@pytest.mark.parametrize(
    ("separator", "reason"),
    (
        ("\n", "Parameters: [ssm:/my-app/prod/db-password] cannot be found."),
        ("\r\n", "Parameters: [ssm-secure:/my-app/prod/token] cannot be found."),
        ("\n", "SSM parameter /my-app/prod/api-key not found."),
    ),
)
def test_ssm_finding_suppresses_the_generic_configuration_rule(
    separator: str, reason: str
) -> None:
    # CloudFormation prints the generic changeset wrapper on its own line, so
    # this rule suppresses the generic finding for the whole log rather than
    # excluding a line - both lines describe one failure.
    log = f"Error: Failed to create changeset for the stack: my-app{separator}{reason}"

    titles = [finding.title for finding in diagnose(log)]
    assert _SSM_TITLE in titles
    assert _SAM_CONFIG_TITLE not in titles


@pytest.mark.parametrize(
    "incomplete_reason",
    (
        "Parameters: [ssm:/my-app/prod/db-password] output truncated",
        "Parameters: [ssm:/my-app/prod/db-password cannot be found",
        "Parameters: [ssm:] cannot be found",
        "Parameters: [ssm:/my-app/prod/db-password] could not be resolved",
        "Parameters: [ssm:/my-app/prod/db-password]\ncannot be found",
        "SSM parameter /my-app/prod/api-key\nnot found",
        "SSM parameter /my-app/prod/api-key not foundational",
    ),
)
def test_an_incomplete_ssm_reason_keeps_the_generic_configuration_finding(
    incomplete_reason: str,
) -> None:
    log = f"Error: Failed to create changeset for the stack: my-app\n{incomplete_reason}"

    rule_ids = [finding.rule_id for finding in diagnose(log)]
    assert "ssm.parameter.resolution-failed" not in rule_ids
    assert "sam.deploy.configuration-resolution-failed" in rule_ids


def test_ssm_parameter_not_found_wording_also_matches() -> None:
    log = "SSM parameter /my-app/prod/api-key not found."

    titles = [finding.title for finding in diagnose(log)]
    assert _SSM_TITLE in titles


def test_a_generic_missing_parameter_is_not_reported_as_an_ssm_failure() -> None:
    # The pre-existing wording must keep its own finding: this rule targets
    # SSM-specific shapes only.
    log = "Parameter 'Stage' must have values"

    titles = [finding.title for finding in diagnose(log)]
    assert _SSM_TITLE not in titles
    assert _SAM_CONFIG_TITLE in titles


def test_kms_env_var_failure_keeps_an_unrelated_resource_failure_visible() -> None:
    log = (
        "CREATE_FAILED  AWS::Lambda::Function  Worker  Lambda was unable to "
        "configure access to your environment variables. KMS Exception: "
        "DisabledException\n"
        "CREATE_FAILED  AWS::DynamoDB::Table  Orders  Resource handler "
        "returned message: throughput exceeded"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert _KMS_ENV_TITLE in titles
    # Excluding the KMS line must not silence the other failed resource.
    assert "CloudFormation resource creation or update failed" in titles


def test_artifact_bucket_denial_keeps_unrelated_resource_failures_visible() -> None:
    log = (
        "Error uploading to my-deploy-bucket: An error occurred (AccessDenied) "
        "when calling the PutObject operation: Access Denied "
        "(Service: S3, Status Code: 403)\n"
        "CREATE_FAILED AWS::SQS::Queue WorkQueue Resource handler returned "
        'message: "The specified queue does not exist."\n'
        "CREATE_FAILED AWS::DynamoDB::Table Orders Resource handler returned "
        'message: "Subscriber limit exceeded."'
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "The deployment bucket denied access to the packaged artifacts" in titles
    assert "CloudFormation resource creation or update failed" in titles


def test_layer_artifact_denial_still_wins_over_the_deployment_bucket_rule() -> None:
    log = (
        "MyLayer CREATE_FAILED Your access has been denied by S3, please make "
        "sure your request credentials have permission to GetObject for "
        "my-deploy-bucket/layer.zip"
    )

    titles = [finding.title for finding in diagnose(log)]
    assert "CloudFormation cannot read a Lambda layer artifact from S3" in titles
    assert "The deployment bucket denied access to the packaged artifacts" not in titles


def test_denial_rules_never_recommend_administrator_access_as_a_fix() -> None:
    from sam_doctor.diagnostics import supported_rules

    for rule in supported_rules():
        for step in rule.verification:
            assert "attach AdministratorAccess" not in step or "never" in step


def test_ecr_auth_denial_does_not_fire_the_new_denial_rules() -> None:
    log = (
        "An error occurred (AccessDeniedException) when calling the GetAuthorizationToken "
        "operation: User: arn:aws:sts::123456789012:assumed-role/deploy-role/GitHubActions "
        "is not authorized to perform: ecr:GetAuthorizationToken on resource: * because no "
        "identity-based policy allows the ecr:GetAuthorizationToken action"
    )

    titles = [finding.title for finding in diagnose(log)]

    assert "A deployment action was denied because no policy allows it" not in titles
    assert "An explicit deny blocked a deployment action" not in titles


def test_not_stabilized_surfaces_the_nested_handler_reason_first() -> None:
    log = (
        "MyDistribution CREATE_FAILED AWS::CloudFront::Distribution "
        'Resource handler returned message: "Resource of type '
        "'AWS::CloudFront::Distribution' did not stabilize.\" "
        "(RequestToken: 3f1a2b, HandlerErrorCode: NotStabilized)"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == [
        "A resource was accepted by its service but never reached a stable state"
    ]
    explanation = findings[0].explanation
    assert explanation.startswith("Underlying status reason parsed from the evidence")
    assert "did not stabilize" in explanation
    assert "`AWS::CloudFront::Distribution`" in explanation
    assert "propagate globally" in explanation


def test_exceeded_wait_attempts_without_handler_message_reports_generic_guidance() -> (
    None
):
    log = "MyPeering CREATE_FAILED Exceeded attempts to wait"

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == [
        "A resource was accepted by its service but never reached a stable state"
    ]
    assert not findings[0].explanation.startswith("Underlying status reason")


def test_not_stabilized_with_nested_denial_reports_both_denial_first() -> None:
    log = (
        "MyResource CREATE_FAILED Custom::Provisioner "
        'Resource handler returned message: "User: '
        "arn:aws:iam::123456789012:user/deploy is not authorized to perform: "
        'iam:CreateRole with an explicit deny" '
        "(HandlerErrorCode: NotStabilized)"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == [
        "An explicit deny blocked a deployment action",
        "A resource was accepted by its service but never reached a stable state",
    ]
    assert all(
        "123456789012" not in evidence
        for finding in findings
        for evidence in finding.evidence
    )


def test_export_in_use_reports_the_staged_migration_not_the_delete_failure() -> None:
    log = (
        "MyStack DELETE_FAILED "
        "Export shared-vpc-id cannot be deleted as it is in use by consumer-service-prod"
    )

    findings = diagnose(log)

    titles = [finding.title for finding in findings]
    assert titles == ["A stack export cannot change while another stack imports it"]
    steps = " ".join(findings[0].verification)
    assert "list-imports" in steps
    assert "Do not delete or force-update the consumer stacks" in steps


def test_export_update_refusal_suppresses_the_generic_update_failure() -> None:
    log = (
        "MyStack UPDATE_FAILED "
        "Export api-endpoint cannot be updated as it is in use by web-frontend"
    )

    titles = [finding.title for finding in diagnose(log)]

    assert titles == ["A stack export cannot change while another stack imports it"]


def test_missing_stack_export_routes_to_cross_stack_dependency_checks() -> None:
    findings = diagnose(
        "An error occurred (ValidationError) when calling the CreateChangeSet "
        "operation: No export named shared-vpc-id found"
    )

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.export.not-found"
    ]
    assert findings[0].confidence == "high"
    assert "list-exports" in " ".join(findings[0].verification)


def test_missing_stack_export_can_be_found_wording_is_supported() -> None:
    findings = diagnose("No export named NetworkStack-SubnetId can be found")

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.export.not-found"
    ]


def test_missing_stack_export_rule_ignores_export_prose() -> None:
    findings = diagnose(
        "The export named shared-vpc-id was found and imported successfully"
    )

    assert "cloudformation.export.not-found" not in {
        finding.rule_id for finding in findings
    }


def test_missing_stack_export_keeps_unrelated_resource_failure() -> None:
    findings = diagnose(
        "Consumer UPDATE_FAILED No export named shared-vpc-id found\n"
        "Bucket UPDATE_FAILED unrelated bucket failure"
    )

    rule_ids = {finding.rule_id for finding in findings}
    assert "cloudformation.export.not-found" in rule_ids
    assert "cloudformation.resource.create-update-failed" in rule_ids


def test_circular_cloudformation_dependency_routes_to_template_graph_checks() -> None:
    findings = diagnose(
        "ValidationError: Circular dependency between resources: "
        "[ApiFunction, ApiPermission, Api]"
    )

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.template.circular-dependency"
    ]
    assert findings[0].confidence == "high"
    verification = " ".join(findings[0].verification)
    assert "Fn::GetAtt" in verification
    assert "DependsOn" in verification


def test_circular_dependency_without_resource_list_is_supported() -> None:
    findings = diagnose("ValidationError: Circular dependency between resources")

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.template.circular-dependency"
    ]


def test_circular_dependency_rule_ignores_prose() -> None:
    findings = diagnose(
        "The template change removed the circular dependency between resources."
    )

    assert "cloudformation.template.circular-dependency" not in {
        finding.rule_id for finding in findings
    }


def test_circular_dependency_keeps_unrelated_resource_failure() -> None:
    findings = diagnose(
        "ApiFunction CREATE_FAILED Circular dependency between resources: [Api, ApiFunction]\n"
        "Bucket CREATE_FAILED unrelated bucket failure"
    )

    rule_ids = {finding.rule_id for finding in findings}
    assert "cloudformation.template.circular-dependency" in rule_ids
    assert "cloudformation.resource.create-update-failed" in rule_ids


def test_circular_dependency_owns_rollback_and_changeset_wrappers() -> None:
    findings = diagnose(
        "ROLLBACK_IN_PROGRESS\n"
        "Error: Failed to create changeset\n"
        "ValidationError: Circular dependency between resources: [A, B]"
    )

    assert [finding.rule_id for finding in findings] == [
        "cloudformation.template.circular-dependency"
    ]


def test_lambda_code_storage_limit_exceeded_positive() -> None:
    sample_log = (
        "CREATE_FAILED AWS::Lambda::Version ApiFunctionVersion Code storage limit exceeded. "
        "(Service: Lambda, Status Code: 400; Error Code: CodeStorageExceededException)"
    )
    findings = diagnose(
        sample_log
    )

    rule_titles = [f.title for f in findings]
    assert "AWS Lambda code storage limit exceeded" in rule_titles


def test_lambda_code_storage_limit_exceeded_suppression() -> None:
    log = (
        "CREATE_FAILED AWS::Lambda::Version ApiFunctionVersion Code storage limit exceeded. "
        "(Service: Lambda, Status Code: 400; Error Code: CodeStorageExceededException)"
    )
    findings = diagnose(log)

    rule_titles = [f.title for f in findings]

    assert "AWS Lambda code storage limit exceeded" in rule_titles

    assert "CloudFormation resource creation or update failed" not in rule_titles


def test_code_storage_wording_alone_is_not_a_quota_finding() -> None:
    assert diagnose("Code storage cleanup finished; usage is well below the limit.") == []


@pytest.mark.parametrize(
    "log",
    [
        (
            "CREATE_FAILED AWS::Lambda::Function HelloWorldFunction Resource "
            "handler returned message: The runtime parameter of python3.8 is no "
            "longer supported for creating or updating AWS Lambda functions"
        ),
        (
            "An error occurred (InvalidParameterValueException) when calling the "
            "CreateFunction operation: The runtime parameter of nodejs14.x is no "
            "longer supported for creating or updating AWS Lambda functions"
        ),
    ],
)
def test_lambda_deprecated_runtime_is_reported_without_generic_noise(log: str) -> None:
    assert [finding.rule_id for finding in diagnose(log)] == [
        "lambda.runtime.deprecated"
    ]


def test_lambda_deprecated_runtime_does_not_match_quoted_documentation() -> None:
    log = (
        "The migration guide quotes: The runtime parameter of python3.8 is no "
        "longer supported for creating or updating AWS Lambda functions"
    )

    assert diagnose(log) == []


def test_reserved_concurrency_below_minimum_positive() -> None:
    log = (
        "CREATE_FAILED  AWS::Lambda::Function  ApiFunction  Specified "
        "ReservedConcurrentExecutions for function decreases account's "
        "UnreservedConcurrentExecution below its minimum value of [100]. "
        "(Service: Lambda, Status Code: 400; Error Code: "
        "InvalidParameterValueException)"
    )

    rule_titles = [f.title for f in diagnose(log)]

    assert (
        "Reserved concurrency would drop the account below its minimum unreserved value"
        in rule_titles
    )


def test_reserved_concurrency_below_minimum_matches_the_resource_handler_wrapper() -> None:
    log = (
        'Resource handler returned message: "Specified '
        "ReservedConcurrentExecutions for function decreases account's "
        'UnreservedConcurrentExecution below its minimum value of [100]." '
        "(HandlerErrorCode: InvalidRequest)"
    )

    rule_titles = [f.title for f in diagnose(log)]

    assert (
        "Reserved concurrency would drop the account below its minimum unreserved value"
        in rule_titles
    )


def test_reserved_concurrency_rule_does_not_match_unrelated_invalid_parameter_errors() -> (
    None
):
    log = (
        "An error occurred (InvalidParameterValueException) when calling "
        "the CreateFunction operation: Environment variable AWS_REGION is a "
        "reserved key"
    )

    rule_titles = [f.title for f in diagnose(log)]

    assert (
        "Reserved concurrency would drop the account below its minimum unreserved value"
        not in rule_titles
    )


def test_reserved_concurrency_below_minimum_suppresses_the_generic_create_failed_finding() -> (
    None
):
    log = (
        "CREATE_FAILED  AWS::Lambda::Function  ApiFunction  Specified "
        "ReservedConcurrentExecutions for function decreases account's "
        "UnreservedConcurrentExecution below its minimum value of [100]. "
        "(Service: Lambda, Status Code: 400; Error Code: "
        "InvalidParameterValueException)"
    )

    rule_titles = [f.title for f in diagnose(log)]

    assert (
        "Reserved concurrency would drop the account below its minimum unreserved value"
        in rule_titles
    )
    assert "CloudFormation resource creation or update failed" not in rule_titles


def test_github_notices_from_single_log_payload() -> None:
    """The Action's default mode is a single log, not a batch.

    The batch branch had a test; this one did not, despite being the path most
    workflows take when the Action renders its annotations.
    """
    from sam_doctor.cli import github_notices_from_payload

    payload = {
        "sam_doctor_version": __version__,
        "source": "deployment.log",
        "finding_count": 1,
        "findings": [
            {
                "rule_id": "github.oidc.assume-role-rejected",
                "title": "GitHub Actions cannot assume the configured AWS role through OIDC",
                "confidence": "high",
                "explanation": "The trust policy rejected the token.",
                "verification": ["Check the trust policy subject."],
                "documentation_url": "https://docs.github.com/actions",
                "evidence": ["Not authorized to perform: sts:AssumeRoleWithWebIdentity"],
                "line_number": 2,
            }
        ],
    }

    output = github_notices_from_payload(payload, False)
    assert output.startswith("::notice file=deployment.log,line=2,title=SAM Doctor::")
    assert "cannot assume the configured AWS role" in output


def test_github_notices_from_single_log_payload_without_findings() -> None:
    from sam_doctor.cli import github_notices_from_payload

    payload = {
        "sam_doctor_version": __version__,
        "source": "clean.log",
        "finding_count": 0,
        "findings": [],
    }

    assert github_notices_from_payload(payload, False) == ""


def test_nested_stack_failure_does_not_hide_other_failed_resources() -> None:
    """A parent stack that fails a child usually fails other resources too.

    Suppressing the generic resource rule for the whole log would drop those
    other failures entirely, which is the opposite of what someone debugging a
    nested deployment needs. The embedded-stack line is excluded per line
    instead, so its own rule explains it and everything else still reports.
    """
    log = (
        "ChildStack CREATE_FAILED Embedded stack "
        "arn:aws:cloudformation:us-east-1:123456789012:stack/child/abc "
        "was not successfully created: The following resource(s) failed to create: [MyFn].\n"
        'MyQueue CREATE_FAILED Resource handler returned message: '
        '"Invalid request provided: queue attribute name is invalid"'
    )

    findings = {finding.rule_id: finding for finding in diagnose(log)}
    assert "cloudformation.nested-stack.propagation-failed" in findings
    assert "cloudformation.resource.create-update-failed" in findings

    generic_evidence = " ".join(findings["cloudformation.resource.create-update-failed"].evidence)
    assert "MyQueue" in generic_evidence
    assert "Embedded stack" not in generic_evidence


def test_nested_stack_failure_alone_reports_one_finding() -> None:
    log = (
        "ChildStack CREATE_FAILED Embedded stack "
        "arn:aws:cloudformation:us-east-1:123456789012:stack/child/abc "
        "was not successfully created: The following resource(s) failed to create: [MyFn]."
    )

    assert [f.rule_id for f in diagnose(log)] == [
        "cloudformation.nested-stack.propagation-failed"
    ]


# Every status reason that overlaps the generic resource-failure rule, paired
# with a nearby unrelated failure. A stack rarely fails exactly one resource,
# so hiding the rest of them is the opposite of useful.
_OVERLAPPING_STATUS_REASONS = (
    "MyBucket CREATE_FAILED my-app-logs already exists (Service: S3, Status Code: 409, Error Code: BucketAlreadyExists)",
    "MyBucket CREATE_FAILED The specified bucket is not valid. Error Code: InvalidBucketName",
    "MyFn CREATE_FAILED An error occurred (CodeStorageExceededException): Code storage limit exceeded.",
    "MyCert CREATE_FAILED Resource did not stabilize",
    "MyExport UPDATE_FAILED Export my-api-url cannot be updated as it is in use by consumer-stack",
    "MyFn CREATE_FAILED Specified ReservedConcurrentExecutions for function decreases account's UnreservedConcurrentExecution below its minimum value",
    "MyDeployment CREATE_FAILED The REST API doesn't contain any methods",
    "MyRole CREATE_FAILED Has prohibited field Resource",
    "MyBucket UPDATE_FAILED Resource handler returned message: \"AbortIncompleteMultipartUpload cannot be specified with Tags.\"",
    "ImageRecipe CREATE_FAILED Resource handler returned message: \"The following resource 'ImageRecipe' already exists: 'recipe/1.1.0' (HandlerErrorCode: AlreadyExists)\"",
    "MyStack CREATE_FAILED An error occurred (ServiceNotAvailable) when calling the CreateStack operation: CloudFormation is temporarily unavailable",
    "MyFn CREATE_FAILED The runtime parameter of python3.8 is no longer supported for creating or updating AWS Lambda functions",
)

_UNRELATED_RESOURCE_FAILURE = (
    'MyQueue CREATE_FAILED Resource handler returned message: '
    '"Invalid request provided: queue attribute name is invalid"'
)


@pytest.mark.parametrize("specific_failure", _OVERLAPPING_STATUS_REASONS)
def test_a_specific_reason_alone_reports_exactly_one_finding(specific_failure: str) -> None:
    assert len(diagnose(specific_failure)) == 1


@pytest.mark.parametrize("specific_failure", _OVERLAPPING_STATUS_REASONS)
def test_a_specific_reason_does_not_hide_other_failed_resources(
    specific_failure: str,
) -> None:
    findings = {f.rule_id: f for f in diagnose(specific_failure + "\n" + _UNRELATED_RESOURCE_FAILURE)}
    generic = findings.get("cloudformation.resource.create-update-failed")
    assert generic is not None, (
        "the unrelated MyQueue failure must still be reported alongside "
        f"{specific_failure[:60]!r}"
    )
    assert "MyQueue" in " ".join(generic.evidence)
