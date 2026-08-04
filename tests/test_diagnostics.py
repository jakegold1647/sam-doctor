import io
import json
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


def _assert_object_shape(payload: object, schema: dict[str, object], *, required_key: str) -> dict[str, object]:
    assert isinstance(payload, dict), f"{required_key} payload is not a JSON object"
    required = schema.get("required", [])
    assert all(key in payload for key in required), f"{required_key} payload missing required keys"
    return payload


def _assert_json_schema_matches(schema_relative_path: str, payload: dict[str, object]) -> None:
    schema = _load_schema(schema_relative_path)
    validator = Draft202012Validator(schema)
    validator.validate(payload)


def _finding_shape(finding: object, finding_schema: dict[str, object], index: int) -> None:
    assert isinstance(finding, dict), f"finding {index} is not an object"
    required = finding_schema.get("required", [])
    assert all(key in finding for key in required), f"finding {index} missing required keys"
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
    match = re.search(r'^version = "(?P<version>\d+\.\d+\.\d+)"$', pyproject, re.M)
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
    assert "sam-doctor rules" in terminal
    assert "template=rule_request.yml" in terminal


@pytest.mark.parametrize(
    ("log_line", "title_fragment"),
    (
        ("InvalidIdentityToken: Incorrect token audience", "token audience"),
        ("Unable to get ID Token: missing id-token: write permission", "cannot request an oidc token"),
        ("No OpenIDConnect provider found in your account", "missing the github actions oidc provider"),
        ("AccessDeniedException: action is not authorized", "AWS denied"),
        (
            "property StageName: not defined for resource of type AWS::Serverless::Api",
            "SAM template property",
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
        ("The specified bucket is not valid. Error Code: InvalidBucketName", "S3 bucket name"),
        (
            "Your access has been denied by S3, please make sure your request credentials have permission to GetObject for bucket layer-artifacts.",
            "cannot read a Lambda layer artifact",
        ),
        (
            "InsufficientCapabilitiesException: Requires capabilities : [CAPABILITY_NAMED_IAM]",
            "explicit capability acknowledgement",
        ),
        ("The REST API doesn't contain any methods", "API Gateway deployment started"),
        ("MyFunction CREATE_FAILED Resource handler returned message: denied", "resource creation"),
        ("Stack: example is in ROLLBACK_COMPLETE state and can not be updated.", "failed initial stack"),
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
    ),
)
def test_supported_failure_categories_are_detected(log_line: str, title_fragment: str) -> None:
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
    ),
)
def test_success_like_lines_do_not_create_false_findings(log_line: str) -> None:
    assert diagnose(log_line) == []


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
            "failed initial stack",
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
def test_specific_findings_suppress_broader_diagnostics(log: str, title_fragment: str) -> None:
    findings = diagnose(log)

    assert len(findings) == 1
    assert title_fragment.lower() in findings[0].title.lower()


def test_expired_wording_alone_is_not_a_credential_finding() -> None:
    assert diagnose("The CloudFront distribution's TLS certificate expired last week.") == []
    assert diagnose("Waiting for the changeset to be created; the rate of progress is slow.") == []


def test_delete_wording_alone_is_not_a_deletion_finding() -> None:
    assert diagnose("DELETE_IN_PROGRESS then DELETE_COMPLETE; termination protection was already off.") == []
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
    assert any("explicit capability acknowledgement" in finding.title.lower() for finding in findings)


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
def test_packaged_scenario_demos_are_available(scenario: str, title_fragment: str) -> None:
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
def test_demo_command_supports_scenarios(tmp_path, scenario: str, capsys: pytest.CaptureFixture[str]) -> None:
    output_file = tmp_path / f"{scenario}.md"

    assert main(["demo", "--scenario", scenario, "--format", "json", "--output", output_file]) == 0
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
    result = redact(f"Credentials: AccessKeyId=ASIAIOSFODNN7EXAMPLE SessionToken={token}")

    assert token not in result
    assert "[REDACTED_AWS_SESSION_TOKEN]" in result
    # A short base64-looking word with the same prefix is left alone.
    assert redact("IQoJb3JpZ2lu is a prefix") == "IQoJb3JpZ2lu is a prefix"


def test_redaction_covers_quoted_secret_values() -> None:
    text = (
        "password=\"hunter2\" "
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
    findings = diagnose("prefix " + ("x" * 500) + " AccessDeniedException " + ("y" * 500))

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


def test_batch_command_analyzes_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "first.log").write_text("Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8")
    (logs / "second.txt").write_text("Everything completed successfully.", encoding="utf-8")

    assert main(["batch", str(logs), "--format", "terminal"]) == 0
    output = capsys.readouterr().out

    assert "first.log" in output
    assert "second.log" not in output
    assert "second.txt" in output
    assert "AccessDenied" not in output
    assert "GitHub Actions cannot assume the configured AWS role through OIDC" in output


def test_batch_command_json_has_aggregate_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "a.txt").write_text("The REST API doesn't contain any methods", encoding="utf-8")
    (tmp_path / "b.log").write_text("sam deploy completed successfully", encoding="utf-8")

    assert main(["batch", str(tmp_path / "a.txt"), str(tmp_path / "b.log"), "--format", "json"]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["batch_count"] == 2
    assert any(entry["finding_count"] == 1 for entry in report["results"])


def test_batch_render_github_emits_annotations_only_for_findings(tmp_path: Path) -> None:
    from sam_doctor.cli import _batch_render

    finding_log = tmp_path / "with_finding.log"
    clean_log = tmp_path / "clean.log"
    finding_log.write_text("Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8")
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
    (tmp_path / "a.txt").write_text("The REST API doesn't contain any methods", encoding="utf-8")
    (tmp_path / "b.log").write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )

    assert (
        main(
            ["batch", str(tmp_path / "a.txt"), str(tmp_path / "b.log"), "--format", "json"],
        )
        == 0
    )


def test_batch_command_fails_with_fail_on_findings(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("The REST API doesn't contain any methods", encoding="utf-8")
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


def test_init_command_rejects_existing_file_without_force(tmp_path: Path, capsys) -> None:
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


def test_batch_command_preserves_path_for_duplicate_filenames(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first_dir = tmp_path / "run1"
    second_dir = tmp_path / "run2"
    first_dir.mkdir()
    second_dir.mkdir()

    first_file = first_dir / "duplicate.log"
    second_file = second_dir / "duplicate.log"
    first_file.write_text("Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8")
    second_file.write_text("The REST API doesn't contain any methods", encoding="utf-8")

    assert main(["batch", str(first_dir), str(second_dir), "--format", "terminal"]) == 0

    output = capsys.readouterr().out
    assert str(first_file) in output
    assert str(second_file) in output


def test_batch_markdown_output_includes_file_sections(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first_file = tmp_path / "first.log"
    second_file = tmp_path / "second.log"
    first_file.write_text("Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8")
    second_file.write_text("AccessDeniedException: action is not authorized", encoding="utf-8")

    assert main(["batch", str(first_file), str(second_file), "--format", "markdown"]) == 0

    output = capsys.readouterr().out
    assert "## Source:" in output
    assert str(first_file) in output
    assert str(second_file) in output


def test_diagnose_can_fail_on_findings_after_writing_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "failure.log"
    report = tmp_path / "diagnosis.json"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )

    assert main(
        [
            "diagnose",
            log,
            "--format",
            "json",
            "--output",
            report,
            "--fail-on-findings",
        ]
    ) == 1
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
    assert "SAM Doctor found 1 possible issue" in _render_findings(findings, "failure.log", "terminal")


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
    assert all(line.startswith("::notice ") for line in output.rstrip("\n").splitlines())
