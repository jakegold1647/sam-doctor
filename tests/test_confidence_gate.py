"""The confidence gate changes exit status only: every report keeps showing
every finding, and --fail-on-findings keeps its exact old meaning."""

from __future__ import annotations

from pathlib import Path

from sam_doctor.cli import main

# One rule fires per line: the OIDC assume-role rejection is high confidence,
# the interactive changeset prompt is medium.
_HIGH_LINE = "Not authorized to perform: sts:AssumeRoleWithWebIdentity"
_MEDIUM_LINE = "Deploy this changeset? [y/N]:"


def _log(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_high_threshold_fails_on_a_high_finding(tmp_path: Path, capsys) -> None:
    log = _log(tmp_path, "deploy.log", _HIGH_LINE)
    assert main(["diagnose", str(log), "--fail-on-confidence", "high"]) == 1


def test_high_threshold_passes_a_medium_only_log(tmp_path: Path, capsys) -> None:
    log = _log(tmp_path, "deploy.log", _MEDIUM_LINE)
    assert main(["diagnose", str(log), "--fail-on-confidence", "high"]) == 0
    assert "interactive changeset" in capsys.readouterr().out, (
        "the medium finding must still appear in the report"
    )


def test_medium_threshold_fails_on_a_medium_finding(tmp_path: Path, capsys) -> None:
    log = _log(tmp_path, "deploy.log", _MEDIUM_LINE)
    assert main(["diagnose", str(log), "--fail-on-confidence", "medium"]) == 1


def test_threshold_gates_without_fail_on_findings(tmp_path: Path, capsys) -> None:
    log = _log(tmp_path, "deploy.log", _HIGH_LINE)
    assert main(["diagnose", str(log)]) == 0
    capsys.readouterr()
    assert main(["diagnose", str(log), "--fail-on-confidence", "high"]) == 1


def test_fail_on_findings_still_fails_on_any_confidence(tmp_path: Path, capsys) -> None:
    log = _log(tmp_path, "deploy.log", _MEDIUM_LINE)
    assert main(["diagnose", str(log), "--fail-on-findings"]) == 1


def test_threshold_overrides_fail_on_findings_when_both_are_given(
    tmp_path: Path, capsys
) -> None:
    log = _log(tmp_path, "deploy.log", _MEDIUM_LINE)
    exit_code = main(
        ["diagnose", str(log), "--fail-on-findings", "--fail-on-confidence", "high"]
    )
    assert exit_code == 0, "the explicit threshold is the stricter, chosen gate"


def test_batch_high_threshold_passes_medium_only_files(tmp_path: Path, capsys) -> None:
    _log(tmp_path, "medium.log", _MEDIUM_LINE)
    _log(tmp_path, "clean.log", "Build Succeeded")
    assert main(["batch", str(tmp_path), "--fail-on-confidence", "high"]) == 0


def test_batch_high_threshold_fails_when_any_file_has_a_high_finding(
    tmp_path: Path, capsys
) -> None:
    _log(tmp_path, "medium.log", _MEDIUM_LINE)
    _log(tmp_path, "high.log", _HIGH_LINE)
    assert main(["batch", str(tmp_path), "--fail-on-confidence", "high"]) == 1


def test_rejects_an_unknown_threshold(tmp_path: Path, capsys) -> None:
    log = _log(tmp_path, "deploy.log", _HIGH_LINE)
    assert main(["diagnose", str(log), "--fail-on-confidence", "certain"]) == 2
