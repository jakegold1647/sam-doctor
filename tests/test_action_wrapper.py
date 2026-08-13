import os
import shlex
import subprocess
from pathlib import Path

import pytest

from sam_doctor import __version__

ROOT = Path(__file__).resolve().parents[1]


def _wsl_bash_available() -> bool:
    """Whether `bash` can see Windows drives under /mnt, i.e. is WSL.

    On a POSIX host the wrapper runs natively and this is trivially true. On
    Windows the harness translates repo paths to /mnt/<drive>/..., which only
    WSL mounts - the Git Bash on CI runners cannot, so the wrapper-run tests
    skip there. The composite action itself is still exercised on Windows by
    the verify-windows CI job, which runs `uses: ./` directly.
    """

    if not ROOT.drive:
        return True
    try:
        result = subprocess.run(
            ["bash", "-lc", "test -d /mnt/c"],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


requires_wsl_bash = pytest.mark.skipif(
    not _wsl_bash_available(),
    reason=(
        "needs a bash that mounts Windows drives under /mnt (WSL); the "
        "composite action is covered on Windows by the verify-windows CI job"
    ),
)


def _bash_path(path: Path) -> str:
    if path.drive:
        return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]
    return str(path)


def _run_action(root: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    script = root / "scripts" / "run-github-action.sh"
    if not root.drive:
        return subprocess.run(
            ["bash", str(script)],
            cwd=root,
            env=os.environ | environment,
            text=True,
            capture_output=True,
            check=False,
        )

    assignments = " ".join(
        f"{key}={shlex.quote(value)}" for key, value in environment.items()
    )
    command = f"{assignments} bash {shlex.quote(_bash_path(script))}"
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=root,
        env=os.environ,
        text=True,
        capture_output=True,
        check=False,
    )


def test_action_wrapper_script_has_posix_newlines():
    script = ROOT / "scripts" / "run-github-action.sh"
    assert script.exists(), "run-github-action.sh should exist"
    content = script.read_bytes()
    assert b"\r\n" not in content
    assert content.startswith(b"#!/usr/bin/env bash")


@requires_wsl_bash
def test_action_wrapper_emits_redacted_notice(tmp_path: Path):
    root = ROOT
    output_path = tmp_path / "github-output.txt"
    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(output_path),
            "GITHUB_STEP_SUMMARY": _bash_path(tmp_path / "github-summary.md"),
            "SAM_DOCTOR_LOG_FILE": _bash_path(
                root / "src" / "sam_doctor" / "data" / "oidc-assume-role-failure.txt"
            ),
            "SAM_DOCTOR_ANNOTATIONS": "true",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "::notice file=oidc-assume-role-failure.txt,line=" in result.stdout
    assert "GitHub Actions cannot assume" in result.stdout
    assert "123456789012" not in result.stdout
    output = output_path.read_text(encoding="utf-8")
    assert "finding-count=1\n" in output
    assert "has-findings=true\n" in output
    assert f"sam-doctor-version={__version__}\n" in output


@requires_wsl_bash
def test_action_wrapper_can_disable_notices(tmp_path: Path):
    root = ROOT
    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(tmp_path / "github-output.txt"),
            "GITHUB_STEP_SUMMARY": _bash_path(tmp_path / "github-summary.md"),
            "SAM_DOCTOR_LOG_FILE": _bash_path(
                root / "src" / "sam_doctor" / "data" / "oidc-assume-role-failure.txt"
            ),
            "SAM_DOCTOR_ANNOTATIONS": "false",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "::notice" not in result.stdout


@requires_wsl_bash
def test_action_wrapper_fails_when_fail_on_findings_is_true(tmp_path: Path):
    root = ROOT
    output_path = tmp_path / "github-output.txt"
    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(output_path),
            "GITHUB_STEP_SUMMARY": _bash_path(tmp_path / "github-summary.md"),
            "SAM_DOCTOR_LOG_FILE": _bash_path(
                root / "src" / "sam_doctor" / "data" / "oidc-assume-role-failure.txt"
            ),
            "SAM_DOCTOR_FAIL_ON_FINDINGS": "true",
            "SAM_DOCTOR_ANNOTATIONS": "false",
        },
    )

    assert result.returncode == 1, result.stderr
    assert "SAM Doctor found 1 supported issue(s)." in result.stderr
    output = output_path.read_text(encoding="utf-8")
    assert "finding-count=1\n" in output
    assert "has-findings=true\n" in output
    assert f"sam-doctor-version={__version__}\n" in output


@requires_wsl_bash
def test_action_wrapper_can_run_batch_mode(tmp_path: Path):
    root = ROOT
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    failing_log = logs_dir / "failure.txt"
    clean_log = logs_dir / "clean.txt"
    failing_log.write_text(
        Path(
            ROOT / "src" / "sam_doctor" / "data" / "oidc-assume-role-failure.txt"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    clean_log.write_text("Deployment completed with no failures.\n", encoding="utf-8")
    output_path = tmp_path / "github-output.txt"

    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(output_path),
            "GITHUB_STEP_SUMMARY": _bash_path(tmp_path / "github-summary.md"),
            "SAM_DOCTOR_LOG_FILE": _bash_path(logs_dir),
            "SAM_DOCTOR_BATCH": "true",
            "SAM_DOCTOR_SUMMARY": "true",
            "SAM_DOCTOR_ANNOTATIONS": "true",
        },
    )

    assert result.returncode == 0, result.stderr
    assert "SAM_DOCTOR_BATCH" not in result.stderr
    assert "finding-count=1" in output_path.read_text(encoding="utf-8")
    assert "has-findings=true" in output_path.read_text(encoding="utf-8")
    assert f"sam-doctor-version={__version__}" in output_path.read_text(encoding="utf-8")
    assert "::notice file=" in result.stdout
    assert "GitHub Actions cannot assume" in result.stdout


@requires_wsl_bash
def test_action_wrapper_can_run_a_deploy_and_preserve_its_status(tmp_path: Path):
    root = ROOT
    output_path = tmp_path / "github-output.txt"
    summary_path = tmp_path / "github-summary.md"
    command = (
        "python3 -c "
        + shlex.quote(
            "print('Error: Not authorized to perform: "
            "sts:AssumeRoleWithWebIdentity'); raise SystemExit(7)"
        )
    )

    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(output_path),
            "GITHUB_STEP_SUMMARY": _bash_path(summary_path),
            "SAM_DOCTOR_LOG_FILE": _bash_path(tmp_path / "deployment.log"),
            "SAM_DOCTOR_RUN_COMMAND": command,
            "SAM_DOCTOR_SUMMARY": "true",
            "SAM_DOCTOR_ANNOTATIONS": "true",
        },
    )

    assert result.returncode == 7, result.stderr
    output = output_path.read_text(encoding="utf-8")
    assert "finding-count=1\n" in output
    assert "deploy-exit-status=7\n" in output
    assert "has-findings=true\n" in output
    assert "GitHub Actions cannot assume" in summary_path.read_text(encoding="utf-8")
    assert "::notice file=deployment.log,line=" in result.stdout


@requires_wsl_bash
def test_action_wrapper_keeps_a_successful_deploy_successful(tmp_path: Path):
    root = ROOT
    output_path = tmp_path / "github-output.txt"
    command = (
        "python3 -c "
        + shlex.quote(
            "print('Error: Not authorized to perform: "
            "sts:AssumeRoleWithWebIdentity')"
        )
    )

    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(output_path),
            "GITHUB_STEP_SUMMARY": _bash_path(tmp_path / "github-summary.md"),
            "SAM_DOCTOR_LOG_FILE": _bash_path(tmp_path / "deployment.log"),
            "SAM_DOCTOR_RUN_COMMAND": command,
            "SAM_DOCTOR_ANNOTATIONS": "false",
        },
    )

    assert result.returncode == 0, result.stderr
    output = output_path.read_text(encoding="utf-8")
    assert "finding-count=1" in output
    assert "deploy-exit-status=0" in output


@requires_wsl_bash
def test_action_wrapper_gates_on_confidence_threshold(tmp_path: Path):
    root = ROOT
    data = root / "src" / "sam_doctor" / "data"

    def run_with(log_name: str) -> "subprocess.CompletedProcess[str]":
        return _run_action(
            root,
            {
                "GITHUB_ACTION_PATH": _bash_path(root),
                "GITHUB_OUTPUT": _bash_path(tmp_path / f"output-{log_name}.txt"),
                "GITHUB_STEP_SUMMARY": _bash_path(tmp_path / f"summary-{log_name}.md"),
                "SAM_DOCTOR_LOG_FILE": _bash_path(data / log_name),
                "SAM_DOCTOR_FAIL_ON_CONFIDENCE": "high",
            },
        )

    high = run_with("oidc-assume-role-failure.txt")
    assert high.returncode == 1, high.stderr
    assert "at high confidence or above" in high.stderr

    medium_only = run_with("interactive-changeset-failure.txt")
    assert medium_only.returncode == 0, medium_only.stderr
    assert "::notice file=" in medium_only.stdout, (
        "the medium finding must still be reported even though it does not gate"
    )


@requires_wsl_bash
@pytest.mark.parametrize(
    "payload",
    (
        pytest.param(b"", id="empty-utf8"),
        pytest.param(" \r\n\t".encode("utf-16"), id="whitespace-utf16"),
    ),
)
def test_action_summary_calls_an_empty_log_empty(tmp_path: Path, payload: bytes):
    """The job summary is the surface most CI users actually read.

    It is rebuilt from the JSON payload, which reports zero findings for an
    empty log and an unrecognized one alike, so the wrapper has to tell them
    apart itself or the summary claims the tool read a failure it did not
    recognize.
    """
    root = ROOT
    empty_log = tmp_path / "deployment.log"
    empty_log.write_bytes(payload)
    summary = tmp_path / "github-summary.md"

    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(tmp_path / "github-output.txt"),
            "GITHUB_STEP_SUMMARY": _bash_path(summary),
            "SAM_DOCTOR_LOG_FILE": _bash_path(empty_log),
            "SAM_DOCTOR_SUMMARY": "true",
            "SAM_DOCTOR_ANNOTATIONS": "false",
        },
    )

    assert result.returncode == 0, result.stderr
    rendered = summary.read_text(encoding="utf-8")
    assert "Nothing to diagnose" in rendered
    assert "No supported pattern found" not in rendered


@requires_wsl_bash
def test_action_summary_keeps_the_unmatched_wording_for_real_logs(tmp_path: Path):
    root = ROOT
    log = tmp_path / "deployment.log"
    log.write_text("Something failed that no rule covers\n", encoding="utf-8")
    summary = tmp_path / "github-summary.md"

    result = _run_action(
        root,
        {
            "GITHUB_ACTION_PATH": _bash_path(root),
            "GITHUB_OUTPUT": _bash_path(tmp_path / "github-output.txt"),
            "GITHUB_STEP_SUMMARY": _bash_path(summary),
            "SAM_DOCTOR_LOG_FILE": _bash_path(log),
            "SAM_DOCTOR_SUMMARY": "true",
            "SAM_DOCTOR_ANNOTATIONS": "false",
        },
    )

    assert result.returncode == 0, result.stderr
    rendered = summary.read_text(encoding="utf-8")
    assert "No supported pattern found" in rendered
    assert "Nothing to diagnose" not in rendered
