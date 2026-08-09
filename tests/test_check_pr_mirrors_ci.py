"""check-pr.py promises to mirror CI, and that promise had nothing holding it.

Its docstring says it "mirrors the required steps of .github/workflows/ci.yml so a
contributor discovers failures locally instead of after pushing". Nothing compared
the two, so the local gate had quietly stopped running the clean-environment wheel
verification: that gate lived only as an inline bash block in the workflow, which
a list of commands cannot mirror. A contributor could pass every local check and
still fail CI on packaging.

These tests compare the two lists directly, so adding a script to CI without
adding it here fails in the pull request that adds it.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Scripts CI runs that are deliberately not part of the local gate.
NOT_MIRRORED_LOCALLY: dict[str, str] = {}


def _load_check_pr():
    spec = importlib.util.spec_from_file_location(
        "check_pr", str(REPO_ROOT / "scripts" / "check-pr.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load check-pr.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def check_pr():
    return _load_check_pr()


def _ci_scripts() -> set[str]:
    """Scripts CI executes, ignoring comments that merely mention one."""

    lines = [
        line
        for line in CI_WORKFLOW.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    ]
    return set(re.findall(r"(scripts/[A-Za-z0-9_.-]+\.py)", "\n".join(lines)))


def _local_scripts(check_pr) -> set[str]:
    found: set[str] = set()
    for _name, command in check_pr._steps(fast=False):
        found.update(part for part in command if part.startswith("scripts/"))
    return found


def test_every_ci_script_runs_in_the_local_gate(check_pr) -> None:
    missing = sorted(_ci_scripts() - _local_scripts(check_pr) - set(NOT_MIRRORED_LOCALLY))
    assert missing == [], (
        f"CI runs {missing} but scripts/check-pr.py does not, so a contributor can "
        "pass the local gate and fail CI. Add the step, or record why not in "
        "NOT_MIRRORED_LOCALLY."
    )


def test_every_local_script_exists(check_pr) -> None:
    for script in sorted(_local_scripts(check_pr)):
        assert (REPO_ROOT / script).is_file(), f"check-pr.py runs a missing {script}"


def test_the_docstring_lists_every_step(check_pr) -> None:
    # The docstring is what a contributor reads before trusting the command; a
    # step missing from it reads as a step that does not exist.
    documented = set(re.findall(r"(scripts/[A-Za-z0-9_.-]+\.py)", check_pr.__doc__ or ""))
    assert _local_scripts(check_pr) <= documented, (
        f"undocumented steps: {sorted(_local_scripts(check_pr) - documented)}"
    )

    numbered = re.findall(r"^(\d+)\. ", check_pr.__doc__ or "", flags=re.MULTILINE)
    assert [int(n) for n in numbered] == list(range(1, len(check_pr._steps(fast=False)) + 1)), (
        "the numbered list in the docstring does not match the actual step count"
    )


def test_fast_mode_only_drops_the_expensive_tail(check_pr) -> None:
    full = [name for name, _ in check_pr._steps(fast=False)]
    fast = [name for name, _ in check_pr._steps(fast=True)]

    assert fast == full[: len(fast)], "--fast must drop a suffix, not reorder or skip in the middle"
    assert set(full) - set(fast) == {
        "package build",
        "wheel in a clean env",
        "onboarding smoke check",
    }


def test_the_wheel_check_runs_after_the_build(check_pr) -> None:
    # Verifying an artifact before producing it would check a stale wheel, or
    # nothing at all on a clean checkout.
    names = [name for name, _ in check_pr._steps(fast=False)]
    assert names.index("package build") < names.index("wheel in a clean env")


def test_the_workflow_no_longer_hides_a_gate_in_inline_bash() -> None:
    # The specific shape of the original defect: a `run: |` block doing real
    # verification that no local command could reproduce.
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert ".wheel-verify/bin/python" not in text, (
        "the wheel verification is inline bash again; keep it in "
        "scripts/verify-wheel.py so the local gate can run the same thing"
    )
    assert 'sorted(Path("dist").glob("*.whl"))' not in text, (
        "lexicographic wheel selection is back: 0.9.0 sorts after 0.11.0"
    )
