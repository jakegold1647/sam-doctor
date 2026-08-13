#!/usr/bin/env python3
"""Install the built wheel into a clean environment and run it.

Everything else in the gate tests the source tree with src/ on the path, which
cannot see packaging mistakes: a module left out of the wheel, a broken console
script, a data file that exists in the repository and not in the artifact. The
first person to hit those is whoever runs `pip install sam-doctor`.

This lived only as a shell block inside ci.yml, which is why the local gate
drifted away from CI - scripts/check-pr.py claims to mirror the required steps
and had no way to mirror a block of inline bash. One script, two callers.

The install uses --no-index: sam-doctor declares no runtime dependencies, so a
correct wheel installs with no network at all, and requiring one here would make
the check fail for reasons that have nothing to do with the package.

Exit code 0 when the installed wheel runs and reports the expected finding, 1
otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10, which this repo still supports
    import tomli as tomllib  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DEMO_FINDINGS = 1


def _packaged_version() -> str:
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = payload.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit("project.version missing or invalid in pyproject.toml")
    return version.strip()


def _wheel_for_this_version(dist_dir: Path) -> Path:
    """The wheel matching pyproject's version, not whichever sorts last.

    Picking `sorted(dist.glob("*.whl"))[-1]` sorts version strings
    lexicographically, so 0.9.0 beats 0.11.0 and the check quietly verifies an
    older artifact while reporting success. CI escapes this only because it
    deletes dist/ first; a developer's dist/ accumulates builds, and the first
    run of this script picked a wheel two releases behind.
    """

    version = _packaged_version()
    match = dist_dir / f"sam_doctor-{version}-py3-none-any.whl"
    if match.is_file():
        return match

    present = sorted(path.name for path in dist_dir.glob("*.whl"))
    if not present:
        raise SystemExit(f"No wheel artifacts found in {dist_dir}; run `python -m build` first.")
    raise SystemExit(
        f"No wheel for the packaged version {version} in {dist_dir}. "
        f"Present: {', '.join(present)}. Run `python -m build` to produce it - "
        "verifying a stale wheel would pass while saying nothing about this code."
    )


def _venv_python(venv_dir: Path) -> Path:
    # Windows puts executables in Scripts/, everything else in bin/.
    candidates = (venv_dir / "bin" / "python", venv_dir / "Scripts" / "python.exe")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(f"Could not find the interpreter inside {venv_dir}")


def _venv_console_script(venv_dir: Path) -> Path | None:
    for candidate in (
        venv_dir / "bin" / "sam-doctor",
        venv_dir / "Scripts" / "sam-doctor.exe",
    ):
        if candidate.exists():
            return candidate
    return None


def _isolated_subprocess_environment() -> dict[str, str]:
    """Keep source-tree Python overrides out of the wheel-only environment."""

    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)
    return environment


def _run(command: list[str], *, title: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=_isolated_subprocess_environment(),
    )
    if completed.returncode != 0:
        print(f"FAIL: {title} exited {completed.returncode}")
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise SystemExit(1)
    return completed


def verify_wheel(wheel: Path, workdir: Path) -> None:
    venv_dir = workdir / "wheel-verify"
    print(f"creating a clean environment in {venv_dir}")
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    python = _venv_python(venv_dir)

    print(f"installing {wheel.name} with no index")
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-index",
            str(wheel),
        ],
        title="pip install",
    )

    # The module entry point, which the README offers as the fallback.
    output = workdir / "cli-demo.json"
    _run(
        [
            str(python),
            "-m",
            "sam_doctor.cli",
            "demo",
            "--format",
            "json",
            "--output",
            str(output),
        ],
        title="python -m sam_doctor.cli demo",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    found = payload.get("finding_count")
    if found != EXPECTED_DEMO_FINDINGS:
        raise SystemExit(
            f"FAIL: expected exactly {EXPECTED_DEMO_FINDINGS} finding in demo output, got {found!r}"
        )

    # Human-facing output, which renders through a different path than JSON.
    _run([str(python), "-m", "sam_doctor.cli", "demo"], title="demo (text output)")

    # The shell-independent wrapper is the daily workflow advertised by the
    # README and homepage. Exercise it from the installed wheel as well as the
    # source-tree tests: a missing subcommand or omitted module can otherwise
    # leave `sam-doctor diagnose` healthy while the one-command deploy flow is
    # broken for every installer.
    run_log = workdir / "run-smoke.log"
    _run(
        [
            str(python),
            "-m",
            "sam_doctor.cli",
            "run",
            "--log-file",
            str(run_log),
            "--",
            sys.executable,
            "-c",
            "print('packaged run smoke')",
        ],
        title="python -m sam_doctor.cli run",
    )
    if "packaged run smoke" not in run_log.read_text(encoding="utf-8"):
        raise SystemExit(
            "FAIL: packaged `run` wrapper did not preserve the child command output"
        )

    # The console script is how the wheel is actually used, and a broken
    # entry point would not show up in any of the checks above.
    console_script = _venv_console_script(venv_dir)
    if console_script is None:
        raise SystemExit(
            "FAIL: the wheel installed without a `sam-doctor` console script; "
            "check [project.scripts] in pyproject.toml"
        )
    version = _run([str(console_script), "--version"], title="sam-doctor --version")
    print(f"console script reports: {version.stdout.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel",
        default="",
        help="Wheel to verify (default: the dist/ wheel matching pyproject's version)",
    )
    parser.add_argument(
        "--dist-dir",
        default=str(REPO_ROOT / "dist"),
        help="Where to look for wheels when --wheel is not given",
    )
    args = parser.parse_args()

    wheel = Path(args.wheel) if args.wheel else _wheel_for_this_version(Path(args.dist_dir))
    if not wheel.is_file():
        raise SystemExit(f"Wheel not found: {wheel}")

    with tempfile.TemporaryDirectory(prefix="sam-doctor-wheel-") as tmpdir:
        verify_wheel(wheel, Path(tmpdir))

    print(f"Wheel verified in a clean environment: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
