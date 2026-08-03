import io
import json
from pathlib import Path

import pytest

from sam_doctor.cli import _read_demo, _read_text, _write_report
from sam_doctor.diagnostics import diagnose, json_report, markdown_report
from sam_doctor.redaction import redact
from sam_doctor import __version__


def test_package_version_matches_release() -> None:
    assert __version__ == "0.2.0"


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


@pytest.mark.parametrize(
    ("log_line", "title_fragment"),
    (
        ("InvalidIdentityToken: Incorrect token audience", "token audience"),
        ("AccessDeniedException: action is not authorized", "AWS denied"),
        ("UPDATE_ROLLBACK_IN_PROGRESS after a resource failure", "rollback"),
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
        "Configured CORS for the API",
        "The preflight request returned 204",
    ),
)
def test_success_like_lines_do_not_create_false_findings(log_line: str) -> None:
    assert diagnose(log_line) == []


def test_packaged_demo_is_available() -> None:
    assert "AssumeRoleWithWebIdentity" in _read_demo()


def test_redaction_covers_common_ci_credentials() -> None:
    text = "AKIAIOSFODNN7EXAMPLE ghp_123456789012345678901234567890123456"

    result = redact(text)

    assert "AKIAIOSFODNN7EXAMPLE" not in result
    assert "ghp_123456789012345678901234567890123456" not in result
    assert "[REDACTED_AWS_ACCESS_KEY]" in result
    assert "[REDACTED_GITHUB_TOKEN]" in result


def test_markdown_report_escapes_log_markup() -> None:
    findings = diagnose("AccessDeniedException: <script>alert('x')</script>")

    report = markdown_report(findings, "failed`<log>.txt")

    assert "<script>" not in report
    assert "&lt;script&gt;" in report
    assert "failed`<log>.txt" not in report
    assert "failed`&lt;log&gt;.txt" in report


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
    assert report["source"] == "failure.log"
    assert "[REDACTED_ARN]" in report["findings"][0]["evidence"][0]
    assert "123456789012" not in json_report(findings, "failure.log")


def test_long_evidence_is_bounded() -> None:
    findings = diagnose("prefix " + ("x" * 500) + " AccessDeniedException " + ("y" * 500))

    evidence = findings[0].evidence[0]

    assert len(evidence) <= 360
    assert "..." in evidence
