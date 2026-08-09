"""Tests for the onboarding smoke check.

It runs on every push as the last CI step and it is the first thing a new
contributor is told to run, so what it does when something is wrong matters as
much as what it does when everything is fine. It was the last script in the
repository with no test referencing it.

Each test spawns real subprocesses, because that is the whole point of this
script - it checks that `python -m sam_doctor.cli` works as an installed-ish
entry point rather than as an import. Kept to four cases for that reason.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_smoke():
    spec = importlib.util.spec_from_file_location(
        "run_smoke", str(REPO_ROOT / "scripts" / "run-smoke.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load run-smoke.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def smoke():
    return _load_smoke()


def test_the_default_sample_log_exists(smoke) -> None:
    # The script's default argument points at a file in examples/. Renaming that
    # file breaks the documented `python scripts/run-smoke.py` with no argument,
    # and CI runs exactly that form.
    assert smoke.DEFAULT_LOG.is_file(), f"{smoke.DEFAULT_LOG} is missing"


def test_a_real_failure_log_passes_the_smoke_check(smoke, capsys) -> None:
    assert smoke.run_smoke(smoke.DEFAULT_LOG) == 0

    assert "Smoke check passed" in capsys.readouterr().out


def test_a_missing_log_is_reported_before_anything_runs(smoke, tmp_path: Path, capsys) -> None:
    exit_code = smoke.run_smoke(tmp_path / "not-here.log")

    assert exit_code == 2
    assert "Missing sample log" in capsys.readouterr().out


def test_a_log_with_no_findings_fails_rather_than_passing_quietly(
    smoke, tmp_path: Path, capsys
) -> None:
    # The check exists to prove the tool still detects something. A clean log
    # producing "smoke check passed" would make the gate decorative.
    benign = tmp_path / "clean.log"
    benign.write_text("Build Succeeded\nDeployment succeeded\n", encoding="utf-8")

    with pytest.raises(SystemExit) as raised:
        smoke.run_smoke(benign)

    assert raised.value.code == 2
    assert "expected at least 1 findings" in capsys.readouterr().out
