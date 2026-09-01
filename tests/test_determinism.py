"""Determinism is a stated product claim, so it gets its own tests.

The README promises identical output for identical input, and Windows support
means CRLF-captured logs are a first-class input shape - a finding must not
move or change because a runner wrote \r\n.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import pytest
from conftest import child_env

from sam_doctor.cli import (
    _batch_render,
    _ordered_unique_paths,
    _render_findings,
    _write_report,
)
from sam_doctor.diagnostics import diagnose
from sam_doctor.redaction import redact

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "src" / "sam_doctor" / "data"

FORMATS = ("terminal", "markdown", "json", "github", "sarif")
RULE_FORMATS = ("terminal", "json")


def _composite_log() -> str:
    return "\n".join(
        sample.read_text(encoding="utf-8")
        for sample in sorted(SAMPLES_DIR.glob("*.txt"))
    )


def test_every_format_is_byte_identical_across_runs() -> None:
    text = _composite_log()
    first = {
        fmt: _render_findings(diagnose(text), "composite.log", fmt)
        for fmt in FORMATS
    }
    second = {
        fmt: _render_findings(diagnose(text), "composite.log", fmt)
        for fmt in FORMATS
    }
    assert first == second


def test_report_files_are_utf8_with_lf_newlines(tmp_path: Path) -> None:
    report = "first line\nUnicode evidence: café\n"
    output = tmp_path / "report.txt"

    _write_report(output, report)

    assert output.read_bytes() == report.encode("utf-8")


def test_redirected_cli_output_uses_utf8_with_lf_newlines(tmp_path: Path) -> None:
    log = tmp_path / "unicode.log"
    log.write_text(
        "AccessDeniedException: action is not authorized for 雪\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "-m", "sam_doctor.cli", "diagnose", str(log)],
        capture_output=True,
        env=child_env(),
        check=False,
    )

    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert b"\r" not in result.stdout
    assert result.stdout.endswith(b"\n")
    assert "雪" in result.stdout.decode("utf-8")


def test_batch_paths_have_platform_independent_order_and_separators(
    tmp_path: Path,
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    for name in ("a.log", "B.log"):
        (logs / name).write_text("Deployment completed successfully.\n", encoding="utf-8")

    report, _ = _batch_render([str(logs)], "json")
    sources = [result["source"] for result in json.loads(report)["results"]]

    # Sources go through the same redaction as the findings, so a gate run
    # from a home directory compares against the redacted form of each path.
    assert sources == [
        redact((logs / "B.log").as_posix()),
        redact((logs / "a.log").as_posix()),
    ]
    assert all("\\" not in source for source in sources)


def test_batch_path_deduplication_preserves_case_distinct_windows_names() -> None:
    paths = [
        PureWindowsPath("logs/a.log"),
        PureWindowsPath("logs/A.log"),
        PureWindowsPath("logs/a.log"),
    ]

    assert [path.as_posix() for path in _ordered_unique_paths(paths)] == [
        "logs/A.log",
        "logs/a.log",
    ]


def test_crlf_input_produces_the_same_findings_as_lf() -> None:
    text = _composite_log()
    lf_findings = diagnose(text)
    crlf_findings = diagnose(text.replace("\n", "\r\n"))

    assert [f.rule_id for f in lf_findings] == [f.rule_id for f in crlf_findings]
    assert [f.line_number for f in lf_findings] == [
        f.line_number for f in crlf_findings
    ]
    assert [f.evidence for f in lf_findings] == [f.evidence for f in crlf_findings]


def test_finding_order_follows_first_matching_line() -> None:
    text = _composite_log()
    findings = diagnose(text)
    assert findings, "the composite of bundled samples must produce findings"
    assert [f.line_number for f in findings] == sorted(
        f.line_number for f in findings
    )


def _composite_log_file(tmp_path: Path) -> Path:
    log = tmp_path / "composite.log"
    log.write_text(_composite_log(), encoding="utf-8")
    return log


def _run_cli(
    log: Path, output_format: str, *, env_extra: dict[str, str] | None = None, cwd: Path | None = None
) -> str:
    env = child_env()
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, "-m", "sam_doctor.cli", "diagnose", str(log), "--format", output_format],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd) if cwd else None,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _run_rules(output_format: str, *, hash_seed: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "sam_doctor.cli", "rules", "--format", output_format],
        capture_output=True,
        text=True,
        env=child_env(PYTHONHASHSEED=hash_seed),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("output_format", FORMATS)
def test_output_does_not_depend_on_the_hash_seed(
    output_format: str, tmp_path: Path
) -> None:
    # The in-process check above cannot catch this: dict and set iteration order
    # is stable within a run, so a hash-order dependence only shows up when the
    # seed changes between processes.
    log = _composite_log_file(tmp_path)
    outputs = {
        _run_cli(log, output_format, env_extra={"PYTHONHASHSEED": seed})
        for seed in ("0", "1", "12345")
    }

    assert len(outputs) == 1, f"{output_format} output varies with PYTHONHASHSEED"


@pytest.mark.parametrize("output_format", RULE_FORMATS)
def test_rule_catalog_does_not_depend_on_the_hash_seed(output_format: str) -> None:
    outputs = {_run_rules(output_format, hash_seed=seed) for seed in ("0", "1", "12345")}

    assert len(outputs) == 1, f"{output_format} rule catalog varies with PYTHONHASHSEED"


def test_output_does_not_depend_on_the_locale(tmp_path: Path) -> None:
    # tr_TR is the interesting one: dotless-i breaks naive case folding, and the
    # rules all match case-insensitively.
    log = _composite_log_file(tmp_path)
    outputs = {
        _run_cli(log, "json", env_extra={"LC_ALL": locale, "LANG": locale})
        for locale in ("C", "en_US.UTF-8", "tr_TR.UTF-8")
    }

    assert len(outputs) == 1, "json output varies with the locale"


def test_output_does_not_depend_on_the_working_directory(tmp_path: Path) -> None:
    log = _composite_log_file(tmp_path)
    here = Path(__file__).resolve().parents[1]

    assert _run_cli(log, "json", cwd=here) == _run_cli(log, "json", cwd=tmp_path)


def test_packet_timestamps_stay_utc_whatever_the_local_zone(tmp_path: Path) -> None:
    # A local-time timestamp in a shared artifact leaks the reporter's zone and
    # makes two packets hard to order. These must always carry +00:00.
    log = _composite_log_file(tmp_path)
    for index, zone in enumerate(("UTC", "Asia/Tokyo", "America/Los_Angeles")):
        env = child_env(TZ=zone)
        output_dir = tmp_path / f"packet{index}"
        result = subprocess.run(
            [
                sys.executable, "-m", "sam_doctor.cli", "packet", str(log),
                "--output-dir", str(output_dir),
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        notes = (output_dir / "researcher-notes.md").read_text(encoding="utf-8")
        generated = next(
            line for line in notes.splitlines() if line.startswith("- Generated:")
        )
        assert generated.endswith("+00:00"), f"TZ={zone} produced {generated}"
