"""`python -m sam_doctor` is a documented fallback, so it gets tested.

The README tells anyone whose shell cannot find the `sam-doctor` console
script to run the module instead. That path had no coverage: breaking
`__main__.py` would have left a documented instruction failing with nothing
in CI to notice.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import child_env

ROOT = Path(__file__).resolve().parents[1]


def _run_module(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sam_doctor", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=child_env(),
        check=False,
    )


def test_the_subprocess_runs_this_checkout() -> None:
    # Guards the guard: every assertion in this file is about the repository, and
    # is worthless if the child interpreter imported an installed copy instead.
    result = _run_module("--version")
    assert result.returncode == 0, result.stderr

    located = subprocess.run(
        [sys.executable, "-c", "import sam_doctor; print(sam_doctor.__file__)"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=child_env(),
        check=False,
    )
    assert located.returncode == 0, located.stderr
    assert Path(located.stdout.strip()).is_relative_to(ROOT / "src"), (
        f"subprocess imported sam_doctor from {located.stdout.strip()!r}, "
        f"not from {ROOT / 'src'}"
    )


def test_module_entry_point_reports_the_same_version() -> None:
    from sam_doctor import __version__

    result = _run_module("--version")
    assert result.returncode == 0, result.stderr
    assert __version__ in result.stdout


def test_module_entry_point_diagnoses_like_the_console_script(tmp_path: Path) -> None:
    log = tmp_path / "deployment.log"
    log.write_text(
        "Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity\n",
        encoding="utf-8",
    )

    result = _run_module("diagnose", str(log), "--format", "json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["rule_id"] == "github.oidc.assume-role-rejected"


def test_module_entry_point_propagates_the_fail_gate(tmp_path: Path) -> None:
    log = tmp_path / "deployment.log"
    log.write_text(
        "Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity\n",
        encoding="utf-8",
    )

    result = _run_module("diagnose", str(log), "--fail-on-findings")
    assert result.returncode == 1, result.stderr


def test_module_entry_point_reports_usage_errors_as_exit_two() -> None:
    result = _run_module("diagnose", "no-such-file.log")
    assert result.returncode == 2
    assert "Could not read" in result.stderr
