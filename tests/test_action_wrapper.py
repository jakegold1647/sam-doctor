import os
from pathlib import Path
import shlex
import subprocess


def _bash_path(path: Path) -> str:
    return "/mnt/" + path.drive[0].lower() + path.as_posix()[2:]


def _run_action(root: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assignments = " ".join(
        f"{key}={shlex.quote(value)}" for key, value in environment.items()
    )
    command = f"{assignments} bash {shlex.quote(_bash_path(root / 'scripts' / 'run-github-action.sh'))}"
    return subprocess.run(
        ["bash", "-lc", command],
        cwd=root,
        env=os.environ,
        text=True,
        capture_output=True,
        check=False,
    )


def test_action_wrapper_script_has_posix_newlines():
    script = Path("scripts") / "run-github-action.sh"
    assert script.exists(), "run-github-action.sh should exist"
    content = script.read_bytes()
    assert b"\r\n" not in content
    assert content.startswith(b"#!/usr/bin/env bash")


def test_action_wrapper_emits_redacted_notice(tmp_path: Path):
    root = Path.cwd()
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
    assert "::notice title=SAM Doctor::GitHub Actions cannot assume" in result.stdout
    assert "123456789012" not in result.stdout
    assert output_path.read_text(encoding="utf-8") == "finding-count=1\nhas-findings=true\n"


def test_action_wrapper_can_disable_notices(tmp_path: Path):
    root = Path.cwd()
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
