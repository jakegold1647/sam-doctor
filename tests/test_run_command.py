"""Tests for the shell-free deploy wrapper used in daily workflows."""

from __future__ import annotations

import sys
from pathlib import Path

from sam_doctor.cli import main


def _child(script: str) -> list[str]:
    return [sys.executable, "-c", script]


def test_run_streams_and_records_a_failed_command_then_diagnoses(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "deployment.log"

    status = main(
        [
            "run",
            "--log-file",
            str(log),
            "--",
            *_child(
                "print('Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity'); raise SystemExit(7)"
            ),
        ]
    )

    assert status == 7
    assert "Not authorized to perform" in log.read_text(encoding="utf-8")
    assert "SAM Doctor found 1 possible issue" in capsys.readouterr().out


def test_run_does_not_add_diagnosis_noise_after_a_successful_command(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "deployment.log"

    status = main(
        [
            "run",
            "--log-file",
            str(log),
            "--",
            *_child("print('Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity')"),
        ]
    )

    assert status == 0
    output = capsys.readouterr().out
    assert "Not authorized to perform" in output
    assert "SAM Doctor found" not in output


def test_run_can_write_the_failure_report_separately(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "deployment.log"
    report = tmp_path / "diagnosis.md"

    status = main(
        [
            "run",
            "--log-file",
            str(log),
            "--format",
            "markdown",
            "--output",
            str(report),
            "--",
            *_child("print('Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity'); raise SystemExit(3)"),
        ]
    )

    assert status == 3
    assert "## 1." in report.read_text(encoding="utf-8")
    assert "Wrote markdown failure report" in capsys.readouterr().out


def test_run_requires_a_command(capsys) -> None:
    assert main(["run"]) == 2
    assert "requires a deployment command" in capsys.readouterr().err


def test_run_reports_a_missing_executable(tmp_path: Path, capsys) -> None:
    log = tmp_path / "deployment.log"

    assert main(["run", "--log-file", str(log), "--", "definitely-not-a-real-command"]) == 2
    assert "Could not run definitely-not-a-real-command" in capsys.readouterr().err


def test_run_rejects_a_report_that_aliases_the_log(tmp_path: Path, capsys) -> None:
    log = tmp_path / "deployment.log"

    assert (
        main(
            [
                "run",
                "--log-file",
                str(log),
                "--output",
                str(log),
                "--",
                *_child("print('should not run')"),
            ]
        )
        == 2
    )
    assert "must not resolve to an output target" in capsys.readouterr().err
    assert not log.exists()
