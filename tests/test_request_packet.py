from __future__ import annotations

from pathlib import Path

from sam_doctor.cli import main
from sam_doctor.diagnostics import likely_error_excerpt


def test_likely_error_excerpt_finds_context_around_first_match() -> None:
    text = (
        "Starting deployment\n"
        "Uploading artifacts\n"
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity\n"
        "Rolling back stack\n"
        "Deployment complete"
    )

    excerpt = likely_error_excerpt(text, context=1)

    assert [line_number for line_number, _ in excerpt] == [2, 3, 4]
    assert "AssumeRoleWithWebIdentity" in excerpt[1][1]


def test_likely_error_excerpt_returns_empty_when_nothing_looks_wrong() -> None:
    text = "Starting deployment\nUploading artifacts\nDeployment complete\n"

    assert likely_error_excerpt(text) == ()


def test_likely_error_excerpt_redacts_sensitive_data() -> None:
    text = (
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
        "for arn:aws:iam::123456789012:role/deployer, contact owner@example.com, "
        "key AKIAABCDEFGHIJKLMNOP"
    )

    excerpt = likely_error_excerpt(text)

    (_, line) = excerpt[0]
    assert "123456789012" not in line
    assert "owner@example.com" not in line
    assert "AKIAABCDEFGHIJKLMNOP" not in line
    assert "[REDACTED_ARN]" in line
    assert "[REDACTED_EMAIL]" in line
    assert "[REDACTED_AWS_ACCESS_KEY]" in line


def test_likely_error_excerpt_caps_at_max_lines() -> None:
    text = "\n".join(["denied line"] + [f"noise {i}" for i in range(30)])

    excerpt = likely_error_excerpt(text, context=20, max_lines=5)

    assert len(excerpt) <= 5


def test_cli_request_packet_writes_excerpt_for_unmatched_log(tmp_path: Path) -> None:
    log = tmp_path / "unmatched.log"
    log.write_text(
        "\n".join(
            [f"noise line {i}" for i in range(5)]
            + ["Something odd happened that no rule covers: widget-error-9000"]
            + [f"more noise {i}" for i in range(5)]
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(
        ["request-packet", str(log), "--output-dir", str(output_dir), "--context", "1"]
    )

    assert exit_code == 0
    excerpt_path = output_dir / "rule-request.md"
    assert excerpt_path.exists()
    content = excerpt_path.read_text(encoding="utf-8")
    assert "widget-error-9000" in content
    assert "noise line 0" not in content
    assert "more noise 4" not in content
    assert "rule request" in content.lower()


def test_cli_request_packet_reports_no_excerpt_when_nothing_looks_wrong(tmp_path: Path) -> None:
    log = tmp_path / "clean.log"
    log.write_text("Deployment completed with no failures.\n", encoding="utf-8")
    output_dir = tmp_path / "artifacts"

    exit_code = main(["request-packet", str(log), "--output-dir", str(output_dir)])

    assert exit_code == 0
    content = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "No line looked like an error" in content


def test_cli_request_packet_redacts_account_id_and_email(tmp_path: Path) -> None:
    log = tmp_path / "failure.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
        "for arn:aws:iam::123456789012:role/deployer, contact owner@example.com",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(["request-packet", str(log), "--output-dir", str(output_dir)])

    assert exit_code == 0
    content = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "123456789012" not in content
    assert "owner@example.com" not in content


def test_cli_request_packet_supports_stdin(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "artifacts"
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO("Not authorized to perform: sts:AssumeRoleWithWebIdentity\n"),
    )

    exit_code = main(["request-packet", "-", "--output-dir", str(output_dir)])

    assert exit_code == 0
    content = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "<stdin>" in content


def test_cli_request_packet_empty_stdin_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))

    exit_code = main(["request-packet", "-", "--output-dir", str(tmp_path / "artifacts")])

    assert exit_code == 2
    assert "empty" in capsys.readouterr().err
