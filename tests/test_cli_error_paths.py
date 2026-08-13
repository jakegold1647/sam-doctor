"""CLI failure-path behavior: bad inputs and unwritable outputs exit 2."""

from __future__ import annotations

import codecs
import io
import json
from pathlib import Path

import pytest

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


def _output_alias(tmp_path: Path, source: Path, alias_kind: str) -> Path:
    if alias_kind == "literal":
        return source
    if alias_kind == "normalized":
        return tmp_path / "unused" / ".." / source.name

    alias = tmp_path / f"{alias_kind}-{source.name}"
    try:
        if alias_kind == "hardlink":
            alias.hardlink_to(source)
        else:
            alias.symlink_to(source.name)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"{alias_kind} aliases unavailable: {error}")
    return alias


@pytest.mark.parametrize("alias_kind", ("literal", "normalized", "hardlink", "symlink"))
def test_diagnose_output_cannot_alias_input(
    tmp_path: Path, capsys, alias_kind: str
) -> None:
    log = tmp_path / "failure.log"
    sentinel = "AccessDeniedException: do not replace this log\n"
    log.write_text(sentinel, encoding="utf-8")
    output = _output_alias(tmp_path, log, alias_kind)

    exit_code = main(
        ["diagnose", str(log), "--format", "json", "--output", str(output)]
    )

    assert exit_code == 2
    assert "must not resolve to an output target" in capsys.readouterr().err
    assert log.read_text(encoding="utf-8") == sentinel


@pytest.mark.parametrize("alias_kind", ("literal", "normalized", "hardlink", "symlink"))
def test_batch_output_cannot_alias_any_input(
    tmp_path: Path, capsys, alias_kind: str
) -> None:
    first = tmp_path / "first.log"
    second = tmp_path / "second.log"
    first_sentinel = "AccessDeniedException: keep first\n"
    second_sentinel = "AccessDeniedException: keep second\n"
    first.write_text(first_sentinel, encoding="utf-8")
    second.write_text(second_sentinel, encoding="utf-8")
    output = _output_alias(tmp_path, second, alias_kind)

    exit_code = main(
        [
            "batch",
            str(first),
            str(second),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 2
    assert "must not resolve to an output target" in capsys.readouterr().err
    assert first.read_text(encoding="utf-8") == first_sentinel
    assert second.read_text(encoding="utf-8") == second_sentinel


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


@pytest.mark.parametrize("command", ("demo", "rules", "diagnose", "batch", "init"))
@pytest.mark.parametrize("link_kind", ("hard link", "symlink"))
def test_regular_output_cannot_target_link_to_unrelated_file(
    tmp_path: Path, capsys, command: str, link_kind: str
) -> None:
    victim = tmp_path / "victim.txt"
    sentinel = "keep this unrelated file\n"
    victim.write_text(sentinel, encoding="utf-8")
    output = tmp_path / "report.txt"
    try:
        if link_kind == "hard link":
            output.hardlink_to(victim)
        else:
            output.symlink_to(victim.name)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"{link_kind}s unavailable: {error}")

    if command == "demo":
        args = ["demo", "--output", str(output)]
    elif command == "rules":
        args = ["rules", "--output", str(output)]
    elif command == "init":
        args = ["init", "--workflow-file", str(output), "--force"]
    else:
        log = tmp_path / "failure.log"
        log.write_text("AccessDeniedException: example\n", encoding="utf-8")
        args = [command, str(log), "--format", "json", "--output", str(output)]

    assert main(args) == 2
    assert f"must not be a {link_kind}" in capsys.readouterr().err
    assert victim.read_text(encoding="utf-8") == sentinel


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
    assert "sam-doctor request-packet deployment.log" in out


def test_empty_log_leaves_the_json_contract_alone(tmp_path: Path, capsys) -> None:
    import json as _json

    log = tmp_path / "deployment.log"
    log.write_text("", encoding="utf-8")

    assert main(["diagnose", str(log), "--format", "json"]) == 0
    payload = _json.loads(capsys.readouterr().out)
    assert payload["finding_count"] == 0
    assert payload["findings"] == []
    assert sorted(payload) == ["finding_count", "findings", "sam_doctor_version", "source"]


# Encoding handling. PowerShell writes redirected output as BOM-marked Unicode,
# so `sam deploy > deploy.log` on Windows can hand this tool a UTF-16 log. Those
# were read as UTF-8 and produced no findings at all - a silent miss on a log
# full of failures, which is worse than an error.
_UNICODE_CASES = {
    "utf-8": lambda text: text.encode("utf-8"),
    "utf-8-bom": lambda text: codecs.BOM_UTF8 + text.encode("utf-8"),
    "utf-16-le": lambda text: codecs.BOM_UTF16_LE + text.encode("utf-16-le"),
    "utf-16-be": lambda text: codecs.BOM_UTF16_BE + text.encode("utf-16-be"),
    "utf-32-le": lambda text: codecs.BOM_UTF32_LE + text.encode("utf-32-le"),
    "utf-32-be": lambda text: codecs.BOM_UTF32_BE + text.encode("utf-32-be"),
}
_ENCODING_FAILURE_LINE = (
    "Lambda was unable to configure access to your environment variables. "
    "KMS Exception: DisabledException"
)


@pytest.mark.parametrize("label", sorted(_UNICODE_CASES))
def test_diagnose_reads_every_bom_marked_encoding(
    label: str, tmp_path: Path, capsys
) -> None:
    text = f"Build Succeeded\nnoise line\n{_ENCODING_FAILURE_LINE}\n"
    log = tmp_path / f"{label}.log"
    log.write_bytes(_UNICODE_CASES[label](text))

    exit_code = main(["diagnose", str(log), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["finding_count"] == 1, f"{label} produced no finding"
    # The line number must survive decoding, not just the match.
    assert payload["findings"][0]["line_number"] == 3


def test_diagnose_reads_crlf_without_shifting_line_numbers(
    tmp_path: Path, capsys
) -> None:
    log = tmp_path / "crlf.log"
    text = f"Build Succeeded\r\nnoise line\r\n{_ENCODING_FAILURE_LINE}\r\n"
    log.write_bytes(text.encode("utf-8"))

    exit_code = main(["diagnose", str(log), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["findings"][0]["line_number"] == 3


def test_diagnose_reads_a_log_that_is_not_valid_utf8(tmp_path: Path, capsys) -> None:
    # A latin-1 log must stay readable rather than raise: replacement characters
    # in a stack trace are acceptable, losing the whole diagnosis is not.
    log = tmp_path / "latin1.log"
    text = f"R\xe9sum\xe9\n{_ENCODING_FAILURE_LINE}\n"
    log.write_bytes(text.encode("latin-1"))

    exit_code = main(["diagnose", str(log), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["finding_count"] == 1
