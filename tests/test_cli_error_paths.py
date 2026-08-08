"""CLI failure-path behavior: bad inputs and unwritable outputs exit 2."""

from __future__ import annotations

import io
from pathlib import Path

from sam_doctor.cli import main
from sam_doctor.diagnostics import rules_report


def test_diagnose_missing_file_exits_2(tmp_path: Path, capsys) -> None:
    exit_code = main(["diagnose", str(tmp_path / "does-not-exist.log")])

    assert exit_code == 2
    assert "Could not read" in capsys.readouterr().err


def test_diagnose_unwritable_output_exits_2(tmp_path: Path, capsys) -> None:
    log = tmp_path / "failure.log"
    log.write_text("AccessDeniedException: nope", encoding="utf-8")

    exit_code = main(["diagnose", str(log), "--output", str(tmp_path / "missing-dir" / "report.txt")])

    assert exit_code == 2
    assert "Could not write" in capsys.readouterr().err


def test_batch_missing_input_exits_2(tmp_path: Path, capsys) -> None:
    exit_code = main(["batch", str(tmp_path / "nope-*.log")])

    assert exit_code == 2
    assert "not found" in capsys.readouterr().err


def test_batch_directory_without_logs_exits_2(tmp_path: Path, capsys) -> None:
    (tmp_path / "empty-dir").mkdir()

    exit_code = main(["batch", str(tmp_path / "empty-dir")])

    assert exit_code == 2
    assert "No log files found" in capsys.readouterr().err


def test_packet_empty_stdin_exits_2(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    exit_code = main(["packet", "-", "--output-dir", str(tmp_path / "artifacts")])

    assert exit_code == 2
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


def test_large_input_notes_the_expected_wait_on_stderr(tmp_path: Path, capsys) -> None:
    from sam_doctor.cli import _note_slow_input

    # Exercised directly: diagnosing a real 25 MB log would add half a minute
    # to the suite to assert one line of text.
    _note_slow_input(Path("huge.log"), "x" * (26 * 1024 * 1024))
    captured = capsys.readouterr()
    assert "26 MB" in captured.err
    assert "second per megabyte" in captured.err
    assert captured.out == "", "the note must not pollute machine-readable stdout"


def test_ordinary_input_stays_quiet(tmp_path: Path, capsys) -> None:
    from sam_doctor.cli import _note_slow_input

    _note_slow_input(Path("small.log"), "x" * 1024)
    captured = capsys.readouterr()
    assert captured.err == ""


def test_empty_log_says_nothing_to_diagnose_not_no_pattern_found(
    tmp_path: Path, capsys
) -> None:
    """An empty log is not an unrecognized failure.

    Reporting "no supported pattern found" for one would tell a user the tool
    read their failure and did not recognize it, when the deploy step simply
    never wrote anything - a routine CI outcome with a different fix.
    """
    log = tmp_path / "deployment.log"
    log.write_text("", encoding="utf-8")

    assert main(["diagnose", str(log)]) == 0
    out = capsys.readouterr().out
    assert "nothing to diagnose" in out
    assert "No supported diagnostic pattern" not in out
    assert "rule_request" not in out, "an empty log has no excerpt to request a rule for"


def test_whitespace_only_log_counts_as_empty(tmp_path: Path, capsys) -> None:
    log = tmp_path / "deployment.log"
    log.write_text("   \n\n\t\n", encoding="utf-8")

    assert main(["diagnose", str(log)]) == 0
    assert "nothing to diagnose" in capsys.readouterr().out


def test_unmatched_but_non_empty_log_keeps_the_rule_request_prompt(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "deployment.log"
    log.write_text("Deployment finished with an error nobody has a rule for\n", encoding="utf-8")

    assert main(["diagnose", str(log)]) == 0
    out = capsys.readouterr().out
    assert "No supported diagnostic pattern" in out
    assert "rule_request" in out


def test_empty_log_leaves_the_json_contract_alone(tmp_path: Path, capsys) -> None:
    import json as _json

    log = tmp_path / "deployment.log"
    log.write_text("", encoding="utf-8")

    assert main(["diagnose", str(log), "--format", "json"]) == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["finding_count"] == 0
    assert payload["findings"] == []
    assert sorted(payload) == ["finding_count", "findings", "sam_doctor_version", "source"]
