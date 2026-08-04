#!/usr/bin/env python3
"""Run a minimal SAM Doctor smoke check for onboarding.

This script is intentionally small and dependency-free. It verifies:

- local package import path works for `sam_doctor.cli`
- sample diagnosis JSON output can be produced
- sample demonstration output can be produced
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "examples" / "oidc-assume-role-failure.txt"


def _run_python_module(argv: list[str], env: dict[str, str]) -> int:
    process = subprocess.run(
        [sys.executable, "-m", *argv],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return process.returncode


def _run_json_command(argv: list[str], output_path: Path, env: dict[str, str], *, title: str) -> None:
    process = subprocess.run(
        [sys.executable, "-m", *argv],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if process.returncode != 0:
        print(f"[{title}] failed with exit code {process.returncode}")
        if process.stdout:
            print(process.stdout)
        if process.stderr:
            print(process.stderr, file=sys.stderr)
        raise SystemExit(1)

    if not output_path.exists():
        print(f"[{title}] expected output file was not created: {output_path}")
        raise SystemExit(2)


def _assert_findings(output_path: Path, *, require_min_count: int, title: str) -> None:
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    finding_count = payload.get("finding_count")
    if finding_count is None:
        print(f"[{title}] output is missing finding_count")
        raise SystemExit(2)
    if finding_count < require_min_count:
        print(f"[{title}] expected at least {require_min_count} findings, got {finding_count}")
        raise SystemExit(2)


def run_smoke(sample_log: Path) -> int:
    if not sample_log.exists():
        print(f"Missing sample log: {sample_log}")
        return 2

    env = os.environ.copy()
    env_pythonpath = f"{ROOT / 'src'}"
    if existing := env.get("PYTHONPATH"):
        env_pythonpath = f"{env_pythonpath}{os.pathsep}{existing}"
    env["PYTHONPATH"] = env_pythonpath

    print("Running SAM Doctor smoke check...")
    print(f"Using sample log: {sample_log}")

    rc = _run_python_module(["sam_doctor.cli", "--help"], env)
    if rc != 0:
        print("sam_doctor.cli module entry check failed.")
        return 2

    with TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demo_output = tmp / "smoke-demo.json"
        diagnose_output = tmp / "smoke-diagnose.json"

        _run_json_command(
            ["sam_doctor.cli", "demo", "--format", "json", "--output", str(demo_output)],
            demo_output,
            env,
            title="demo",
        )
        _run_json_command(
            [
                "sam_doctor.cli",
                "diagnose",
                str(sample_log),
                "--format",
                "json",
                "--output",
                str(diagnose_output),
            ],
            diagnose_output,
            env,
            title="diagnose",
        )

        _assert_findings(demo_output, require_min_count=1, title="demo")
        _assert_findings(diagnose_output, require_min_count=1, title="diagnose")

    print("Smoke check passed: demo + diagnose produced valid JSON findings.")
    print("Next:")
    print("1) Run real diagnostics: sam-doctor diagnose <deployment.log>")
    print("2) Share only the top finding and verification command.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a quick SAM Doctor smoke test.")
    parser.add_argument(
        "log_file",
        nargs="?",
        default=str(DEFAULT_LOG),
        help="Path to a sample log file for diagnosis",
    )
    args = parser.parse_args(argv)

    return run_smoke(Path(args.log_file))


if __name__ == "__main__":
    raise SystemExit(main())
