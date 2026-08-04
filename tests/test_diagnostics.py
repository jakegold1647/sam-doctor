import io
import json
from pathlib import Path

import pytest

from sam_doctor.cli import _read_demo, _read_text, _render_findings, _write_report, main
from sam_doctor.diagnostics import (
    diagnose,
    json_report,
    markdown_report,
    rules_report,
    terminal_report,
)
from sam_doctor.redaction import redact
from sam_doctor import __version__


def test_package_version_matches_release() -> None:
    assert __version__ == "0.7.7"


def test_oidc_failure_is_detected_and_redacted() -> None:
    findings = diagnose(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
        "arn:aws:iam::123456789012:role/deploy owner@example.com"
    )

    assert len(findings) == 1
    assert findings[0].title.startswith("GitHub Actions cannot assume")
    report = markdown_report(findings, "failure.log")
    assert "[REDACTED_ARN]" in report
    assert "[REDACTED_EMAIL]" in report
    assert "123456789012" not in report


def test_unknown_log_has_no_finding() -> None:
    assert diagnose("Everything completed successfully.") == []


def test_no_finding_reports_include_a_sanitized_rule_request_path() -> None:
    markdown = markdown_report([], "unknown.log")
    terminal = terminal_report([], "unknown.log")

    assert "sam-doctor rules" in markdown
    assert "diagnostic rule request" in markdown
    assert "issues/new/choose" in markdown
    assert "sam-doctor rules" in terminal
    assert "issues/new/choose" in terminal


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
        ("Deploy this changeset? [y/N]:", "interactive changeset confirmation"),
        (
            "AWS::CloudFormation::Stack ROLLBACK_FAILED ... The following resource(s) failed to delete: [IAMRoleDeployment]",
            "rollback could not delete an iam role",
        ),
        ("UPDATE_ROLLBACK_IN_PROGRESS after a resource failure", "rollback"),
        ("Stack entered ROLLBACK_FAILED after a resource failure", "rollback"),
        ("Error: Failed to create changeset", "SAM deployment"),
        ("CORS conflict: duplicate OPTIONS method", "CORS preflight"),
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
            "Failed to delete AWS::IAM::Role MyRole",
            "rollback could not delete an iam role",
        ),
    ),
)
def test_specific_findings_suppress_broader_diagnostics(log: str, title_fragment: str) -> None:
    findings = diagnose(log)

    assert len(findings) == 1
    assert title_fragment.lower() in findings[0].title.lower()


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
        ("interactive-changeset", "interactive changeset confirmation"),
    ),
)
def test_packaged_scenario_demos_are_available(scenario: str, title_fragment: str) -> None:
    findings = diagnose(_read_demo(scenario))

    assert any(title_fragment.lower() in finding.title.lower() for finding in findings)


@pytest.mark.parametrize(
    "scenario",
    ("oidc", "cloudformation", "capabilities", "api-gateway", "s3-bucket-conflict", "esbuild", "interactive-changeset"),
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
