#!/usr/bin/env python3
"""Run every check a pull request must pass, in one command, on any platform.

This mirrors the required steps of `.github/workflows/ci.yml` so a contributor
discovers failures locally instead of after pushing:

1. site metadata is in sync        (scripts/sync-site-metadata.py --check)
2. contributor page is in sync     (scripts/sync-contributor-page.py --check)
3. website QA                      (scripts/check-site-qa.py)
4. lint                            (ruff check src tests scripts)
5. rule catalog quality gate       (scripts/check-rule-catalog.py)
6. rule fixture registry gate      (scripts/check-rule-fixtures.py)
7. error page mapping gate         (scripts/check-error-pages.py)
8. test suite + coverage floor     (pytest -q --cov)
9. package build                   (python -m build)
10. built wheel in a clean env     (scripts/verify-wheel.py)
11. onboarding smoke check         (scripts/run-smoke.py)

All steps run even when an early one fails, then a summary reports every
failure at once. Exit code 0 only when everything passed.

    python scripts/check-pr.py           # full gate, same as CI
    python scripts/check-pr.py --fast    # skip the build, wheel, and smoke steps
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _steps(fast: bool) -> list[tuple[str, list[str]]]:
    python = sys.executable
    steps = [
        ("site metadata in sync", [python, "scripts/sync-site-metadata.py", "--check"]),
        (
            "contributor page in sync",
            [python, "scripts/sync-contributor-page.py", "--check"],
        ),
        ("website QA", [python, "scripts/check-site-qa.py"]),
        ("ruff lint", [python, "-m", "ruff", "check", "src", "tests", "scripts"]),
        ("rule catalog quality", [python, "scripts/check-rule-catalog.py"]),
        ("rule fixture registry", [python, "scripts/check-rule-fixtures.py"]),
        ("error page mapping", [python, "scripts/check-error-pages.py"]),
        ("test suite", [python, "-m", "pytest", "-q", "--cov"]),
    ]
    if not fast:
        steps.append(("package build", [python, "-m", "build"]))
        # Must follow the build: it verifies the artifact that build just produced.
        steps.append(("wheel in a clean env", [python, "scripts/verify-wheel.py"]))
        steps.append(("onboarding smoke check", [python, "scripts/run-smoke.py"]))
    return steps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="skip the package build, wheel check, and smoke check for quick iteration",
    )
    args = parser.parse_args()

    results: list[tuple[str, bool, float]] = []
    for name, command in _steps(args.fast):
        print(f"\n=== {name}: {' '.join(command[1:])}")
        started = time.perf_counter()
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
        results.append((name, completed.returncode == 0, time.perf_counter() - started))

    print("\n" + "=" * 60)
    failures = 0
    for name, passed, elapsed in results:
        status = "PASS" if passed else "FAIL"
        failures += 0 if passed else 1
        print(f"{status}  {name:<28} {elapsed:6.1f}s")
    if args.fast:
        print("note: --fast skipped the package build, wheel check, and smoke check.")
    if failures:
        print(f"\n{failures} step(s) failed. A pull request in this state will fail CI.")
        return 1
    print("\nAll checks passed. This matches what CI requires on a pull request.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
