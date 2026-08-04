"""CLI failure-path behavior: bad inputs and unwritable outputs exit 2."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from sam_doctor.cli import main
from sam_doctor.diagnostics import rules_report


def test_diagnose_missing_file_exits_2(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["diagnose", str(tmp_path / "does-not-exist.log")])

    assert excinfo.value.code == 2
    assert "Could not read" in capsys.readouterr().err


def test_diagnose_unwritable_output_exits_2(tmp_path: Path, capsys) -> None:
    log = tmp_path / "failure.log"
    log.write_text("AccessDeniedException: nope", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        main(["diagnose", str(log), "--output", str(tmp_path / "missing-dir" / "report.txt")])

    assert excinfo.value.code == 2
    assert "Could not write" in capsys.readouterr().err


def test_batch_missing_input_exits_2(tmp_path: Path, capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["batch", str(tmp_path / "nope-*.log")])

    assert excinfo.value.code == 2
    assert "not found" in capsys.readouterr().err


def test_batch_directory_without_logs_exits_2(tmp_path: Path, capsys) -> None:
    (tmp_path / "empty-dir").mkdir()

    with pytest.raises(SystemExit) as excinfo:
        main(["batch", str(tmp_path / "empty-dir")])

    assert excinfo.value.code == 2
    assert "No log files found" in capsys.readouterr().err


def test_packet_empty_stdin_exits_2(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    with pytest.raises(SystemExit) as excinfo:
        main(["packet", "-", "--output-dir", str(tmp_path / "artifacts")])

    assert excinfo.value.code == 2
    assert "stdin input was empty" in capsys.readouterr().err


def test_demo_writes_report_to_output_file(tmp_path: Path, capsys) -> None:
    target = tmp_path / "demo-report.md"

    exit_code = main(["demo", "--format", "markdown", "--output", str(target)])

    assert exit_code == 0
    assert "Wrote markdown report" in capsys.readouterr().out
    assert "SAM Doctor diagnostic report" in target.read_text(encoding="utf-8")


def test_rules_report_terminal_lists_every_rule() -> None:
    from sam_doctor.diagnostics import supported_rules

    report = rules_report("terminal")

    assert f"supports {len(supported_rules())} diagnostic rule(s)" in report
    for rule in supported_rules():
        assert rule.title in report
