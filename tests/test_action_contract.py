"""The composite action's wiring, checked without running bash.

Every other test of the action runs `scripts/run-github-action.sh`, and those skip
wherever bash cannot see Windows drives - which includes the Git Bash on CI
runners. So the wiring between action.yml and the script is exercised on Linux and
nowhere else, and the wiring is exactly the kind that fails quietly: rename an
output key in the script and `${{ steps.diagnose.outputs.finding-count }}` becomes
an empty string in every consumer's workflow, with nothing failing anywhere.

These checks are static text comparisons, so they run on every platform.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTION_YML = REPO_ROOT / "action.yml"
WRAPPER = REPO_ROOT / "scripts" / "run-github-action.sh"


@pytest.fixture(scope="module")
def action() -> str:
    return ACTION_YML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wrapper() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def _block(text: str, start: str, *ends: str) -> str:
    """The text from one top-level key to whichever of `ends` comes first."""

    begin = text.index(start)
    stops = [text.index(end, begin) for end in ends if end in text[begin:]]
    return text[begin : min(stops)] if stops else text[begin:]


def _declared_inputs(action: str) -> list[str]:
    return re.findall(r"^  ([a-z0-9-]+):", _block(action, "\ninputs:", "\noutputs:"), re.MULTILINE)


def _declared_outputs(action: str) -> list[str]:
    # `branding:` sits between outputs and runs and has its own `icon:`/`color:`
    # keys at the same indent, which read as outputs if the block is not stopped
    # there. Both this test and a hand-check of the same wiring made that mistake.
    return re.findall(
        r"^  ([a-z0-9-]+):",
        _block(action, "\noutputs:", "\nbranding:", "\nruns:"),
        re.MULTILINE,
    )


def _output_value_references(action: str) -> list[tuple[str, str]]:
    """(step id, output key) for every `value: ${{ steps.X.outputs.Y }}`."""

    return re.findall(
        r"value:\s*\$\{\{\s*steps\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+)\s*\}\}",
        _block(action, "\noutputs:", "\nbranding:", "\nruns:"),
    )


def test_every_declared_input_is_passed_to_the_wrapper(action: str, wrapper: str) -> None:
    runs = _block(action, "\nruns:")

    for name in _declared_inputs(action):
        match = re.search(
            rf"([A-Z0-9_]+):\s*\$\{{\{{\s*inputs\.{re.escape(name)}\s*\}}\}}", runs
        )
        assert match, f"input {name!r} is declared but never passed to a step"
        env_var = match.group(1)
        assert env_var in wrapper, (
            f"input {name!r} reaches the script as {env_var} and the script never "
            "reads it, so setting that input would do nothing"
        )


def test_every_declared_output_is_written_by_the_wrapper(action: str, wrapper: str) -> None:
    references = _output_value_references(action)
    assert len(references) == len(_declared_outputs(action)), (
        "an output without a steps.*.outputs.* value would always be empty"
    )

    for _step_id, key in references:
        assert f'echo "{key}=' in wrapper, (
            f"action.yml exposes output {key!r} but the wrapper never writes "
            f"{key}= to $GITHUB_OUTPUT, so consumers read an empty string"
        )


def test_every_referenced_step_id_exists(action: str) -> None:
    runs = _block(action, "\nruns:")
    step_ids = set(re.findall(r"^\s*-?\s*id:\s*([A-Za-z0-9_-]+)", runs, re.MULTILINE))

    for step_id, key in _output_value_references(action):
        assert step_id in step_ids, (
            f"output {key!r} reads from step {step_id!r}, which does not exist "
            f"in this action (steps present: {sorted(step_ids)})"
        )


def test_the_wrapper_writes_nothing_it_does_not_declare(action: str, wrapper: str) -> None:
    # The reverse direction: a key written but not declared is invisible to
    # consumers, which usually means a half-finished output rather than a secret.
    written = set(re.findall(r'echo "([a-z0-9-]+)=[^"]*" >> "\$GITHUB_OUTPUT"', wrapper))
    declared = set(_declared_outputs(action))

    assert written <= declared, (
        f"the wrapper writes {sorted(written - declared)} to $GITHUB_OUTPUT, which "
        "action.yml does not declare as outputs"
    )


def test_the_wrapper_requires_github_output(wrapper: str) -> None:
    # Outside a workflow this variable is unset, and appending to an empty path
    # would fail obscurely partway through instead of at the start.
    assert 'GITHUB_OUTPUT:?' in wrapper
