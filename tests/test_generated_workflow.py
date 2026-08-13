"""`sam-doctor init` writes a GitHub Actions workflow, and nothing parsed it.

The template is a format string containing `${{ }}` expressions, which means the
braces have to be doubled in the source - a detail already responsible for one bug
in this file's history. If the result stops being valid YAML, every `init` user
gets a workflow GitHub silently refuses to run, and the only test coverage was that
the file had been written.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from sam_doctor.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_a_multiline_deploy_command_stays_valid_and_is_captured(
    tmp_path: Path,
) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is unavailable")
    target = tmp_path / "sam-doctor.yml"
    command = "printf 'build output\\n'\nprintf 'deploy output\\n'\nfalse"

    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(target),
                "--deploy-command",
                command,
            ]
        )
        == 0
    )

    doc = yaml.safe_load(target.read_text(encoding="utf-8"))
    steps = next(iter(doc["jobs"].values()))["steps"]
    script = next(step["run"] for step in steps if step.get("name") == "Deploy")
    result = subprocess.run(
        [bash, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == "build output\ndeploy output\n"
    assert (tmp_path / "deployment.log").read_text(encoding="utf-8") == result.stdout


def test_an_empty_deploy_command_is_rejected_before_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "sam-doctor.yml"

    assert (
        main(
            [
                "init",
                "--workflow-file",
                str(target),
                "--deploy-command",
                " \t ",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert "--deploy-command must not be empty" in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert not target.exists()


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


def test_the_scaffold_grants_the_permission_its_deploy_step_needs(generated: dict) -> None:
    # Without id-token: write the runner never sets ACTIONS_ID_TOKEN_REQUEST_URL, so
    # an OIDC deploy fails before it starts. Measuring this catalog against real logs
    # found that exact failure in four unrelated repositories - it is the most common
    # one there is, and a scaffold that walks into it is a poor first experience.
    job = next(iter(generated["jobs"].values()))
    permissions = job.get("permissions") or generated.get("permissions") or {}

    assert permissions.get("id-token") == "write", f"permissions={permissions}"
    assert permissions.get("contents") == "read", (
        "naming permissions replaces the defaults, so contents: read has to be "
        "restated or the checkout loses it"
    )


def test_the_scaffold_pins_the_same_action_versions_this_repo_uses() -> None:
    """The template is a Python string, so dependabot cannot see it.

    Every action reference in .github/workflows gets bumped when a new major lands;
    the scaffold silently kept handing new users actions/checkout@v4 and
    setup-python@v5 after the repository had moved to v7. Comparing the two means the
    dependabot pull request that updates the workflows also fails here until the
    template is updated with it.
    """

    import re

    from sam_doctor.cli import _WORKFLOW_TEMPLATE

    workflow_versions: dict[str, set[str]] = {}
    for workflow in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        for action, version in re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@(v\d+)", text):
            workflow_versions.setdefault(action, set()).add(version)

    for action, version in re.findall(
        r"uses:\s*([\w.-]+/[\w.-]+)@(v\d+)", _WORKFLOW_TEMPLATE
    ):
        if action not in workflow_versions:
            continue  # the scaffold may use an action this repo's own CI does not
        assert version in workflow_versions[action], (
            f"the generated workflow pins {action}@{version} while this repository "
            f"uses {sorted(workflow_versions[action])} - update the template in "
            "src/sam_doctor/cli.py to match"
        )
