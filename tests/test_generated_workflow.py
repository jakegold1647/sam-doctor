"""`sam-doctor init` writes a GitHub Actions workflow, and nothing parsed it.

The template is a format string containing `${{ }}` expressions, which means the
braces have to be doubled in the source - a detail already responsible for one bug
in this file's history. If the result stops being valid YAML, every `init` user
gets a workflow GitHub silently refuses to run, and the only test coverage was that
the file had been written.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from sam_doctor.cli import main


@pytest.fixture
def generated(tmp_path: Path) -> dict:
    target = tmp_path / "sam-doctor.yml"
    assert main(["init", "--workflow-file", str(target)]) == 0
    return yaml.safe_load(target.read_text(encoding="utf-8"))


def test_the_generated_workflow_is_valid_yaml(generated: dict) -> None:
    assert isinstance(generated, dict)
    assert generated.get("name")
    # PyYAML resolves the bare `on:` key to the boolean True, which is correct YAML
    # and what GitHub accepts; asserting on it directly documents that oddity.
    assert True in generated or "on" in generated
    assert generated.get("jobs"), "a workflow with no jobs does nothing"


def test_the_workflow_runs_this_action_and_a_deploy_step(generated: dict) -> None:
    steps = next(iter(generated["jobs"].values()))["steps"]
    uses = [step["uses"] for step in steps if "uses" in step]

    assert any("sam-doctor" in u for u in uses), f"the action is not used: {uses}"
    assert any("actions/checkout" in u for u in uses)
    assert any(step.get("run") for step in steps), "no deploy step to diagnose"


def test_the_action_inputs_survive_templating(tmp_path: Path) -> None:
    # The point of the flags is that they land in the `with:` block. A format-string
    # mistake would drop or mangle them while still producing parseable YAML.
    target = tmp_path / "sam-doctor.yml"
    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(target),
                "--fail-on-confidence",
                "high",
                "--batch",
                "--on-push",
            ]
        )
        == 0
    )

    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    steps = next(iter(doc["jobs"].values()))["steps"]
    with_block = next(step["with"] for step in steps if "sam-doctor" in str(step.get("uses", "")))

    assert with_block["fail-on-confidence"] == "high"
    assert with_block["batch"] is True
    triggers = doc[True] if True in doc else doc["on"]
    assert "push" in triggers


def test_the_manual_trigger_is_the_default(generated: dict) -> None:
    triggers = generated[True] if True in generated else generated["on"]

    assert "workflow_dispatch" in triggers, (
        "the default scaffold should be runnable by hand before it runs on push"
    )


def test_no_unexpanded_placeholders_remain(tmp_path: Path) -> None:
    # A missed substitution leaves `{name}` in the file, which is valid YAML and
    # completely broken.
    target = tmp_path / "sam-doctor.yml"
    assert main(["init", "--workflow-file", str(target)]) == 0

    text = target.read_text(encoding="utf-8")

    for placeholder in ("{trigger}", "{deploy_command}", "{summary}", "{annotations}"):
        assert placeholder not in text
