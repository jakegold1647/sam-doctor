import io
from pathlib import Path

import pytest

from sam_doctor.cli import _read_demo, _read_text, _write_report
from sam_doctor.diagnostics import diagnose, markdown_report
from sam_doctor.redaction import redact


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
