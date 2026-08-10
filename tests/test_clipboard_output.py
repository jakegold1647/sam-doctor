"""Tests for the optional native clipboard report handoff."""

from __future__ import annotations

import sys
from pathlib import Path

from sam_doctor import cli


def test_diagnose_copy_keeps_report_on_stdout_and_uses_native_command(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    log = tmp_path / "deployment.log"
    log.write_text(
        "Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity\n",
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(cli, "_clipboard_command", lambda: ["fake-copy"])

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    assert cli.main(["diagnose", str(log), "--format", "markdown", "--copy"]) == 0

    captured = capsys.readouterr()
    assert "## 1." in captured.out
    assert "Copied the report to the clipboard." in captured.err
    assert calls == [
        {
            "command": ["fake-copy"],
            "input": captured.out,
            "text": True,
            "encoding": "utf-8",
            "check": True,
            "capture_output": True,
        }
    ]


def test_diagnose_copy_without_a_native_clipboard_is_a_usage_error(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    log = tmp_path / "deployment.log"
    log.write_text("No supported failure here\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_clipboard_command", lambda: None)

    assert cli.main(["diagnose", str(log), "--copy"]) == 2
    assert "No native clipboard command is available" in capsys.readouterr().err


def test_run_copy_failure_stays_advisory_to_the_deploy_status(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    log = tmp_path / "deployment.log"
    monkeypatch.setattr(cli, "_clipboard_command", lambda: None)

    status = cli.main(
        [
            "run",
            "--log-file",
            str(log),
            "--copy",
            "--",
            sys.executable,
            "-c",
            "print('Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity'); raise SystemExit(7)",
        ]
    )

    assert status == 7
    assert "No native clipboard command is available" in capsys.readouterr().err
