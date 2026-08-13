"""Tests for the shell-free deploy wrapper used in daily workflows."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

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
    log.write_text("stale deployment output\n", encoding="utf-8")

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
    recorded = log.read_text(encoding="utf-8")
    assert "Not authorized to perform" in recorded
    assert "stale deployment output" not in recorded


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


def test_run_can_create_a_missing_log_when_report_target_already_exists(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "deployment.log"
    report = tmp_path / "diagnosis.json"
    report.write_text("stale report", encoding="utf-8")

    status = main(
        [
            "run",
            "--log-file",
            str(log),
            "--format",
            "json",
            "--output",
            str(report),
            "--",
            *_child(
                "print('Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity'); raise SystemExit(4)"
            ),
        ]
    )

    assert status == 4
    assert log.exists()
    assert '"finding_count": 1' in report.read_text(encoding="utf-8")
    assert "Wrote json failure report" in capsys.readouterr().out


def test_run_requires_a_command(capsys) -> None:
    assert main(["run"]) == 2
    assert "requires a deployment command" in capsys.readouterr().err


def test_run_reports_a_missing_executable(tmp_path: Path, capsys) -> None:
    log = tmp_path / "deployment.log"
    sentinel = "previous deployment evidence\n"
    log.write_text(sentinel, encoding="utf-8")

    assert main(["run", "--log-file", str(log), "--", "definitely-not-a-real-command"]) == 2
    assert "Could not run definitely-not-a-real-command" in capsys.readouterr().err
    assert log.read_text(encoding="utf-8") == sentinel


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


@pytest.mark.parametrize("linked_option", ("log", "report"))
@pytest.mark.parametrize("link_kind", ("hard link", "symlink"))
def test_run_rejects_linked_targets_before_starting_the_command(
    tmp_path: Path, capsys, linked_option: str, link_kind: str
) -> None:
    victim = tmp_path / "unrelated.txt"
    sentinel = "leave the unrelated file alone\n"
    victim.write_text(sentinel, encoding="utf-8")
    linked = tmp_path / "linked-output.txt"
    try:
        if link_kind == "hard link":
            linked.hardlink_to(victim)
        else:
            linked.symlink_to(victim.name)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"{link_kind}s unavailable: {error}")

    log = linked if linked_option == "log" else tmp_path / "deployment.log"
    report = linked if linked_option == "report" else tmp_path / "diagnosis.md"
    status = main(
        [
            "run",
            "--log-file",
            str(log),
            "--output",
            str(report),
            "--",
            *_child("print('COMMAND_RAN'); raise SystemExit(7)"),
        ]
    )

    captured = capsys.readouterr()
    assert status == 2
    assert f"must not be a {link_kind}" in captured.err
    assert "COMMAND_RAN" not in captured.out
    assert victim.read_text(encoding="utf-8") == sentinel
