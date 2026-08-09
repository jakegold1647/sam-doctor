import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_IMMUTABLE_ACTION_REF = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_USES_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)")


def _project_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_external_workflow_actions_use_immutable_commit_shas() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    workflows = sorted(
        path
        for path in workflow_dir.rglob("*")
        if path.suffix in {".yml", ".yaml"}
    )
    unpinned: list[str] = []

    for workflow in workflows:
        for line_number, line in enumerate(
            workflow.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = _USES_LINE.match(line)
            if match is None:
                continue
            target = match.group(1).strip("'\"")
            if target.startswith("./"):
                continue
            if _IMMUTABLE_ACTION_REF.fullmatch(target) is None:
                relative_path = workflow.relative_to(ROOT)
                unpinned.append(f"{relative_path}:{line_number}: {target}")

    assert not unpinned, (
        "External workflow actions must use a 40-character lowercase commit SHA:\n"
        + "\n".join(unpinned)
    )


def test_stable_release_dispatches_pypi_from_main() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    dispatch = workflow.split("gh workflow run pypi-publish.yml", 1)[1]
    assert "--ref main" in dispatch
    assert '-f release-tag="$TAG"' in dispatch


def test_manual_pypi_publish_builds_requested_tag_and_checks_from_main() -> None:
    workflow = (ROOT / ".github" / "workflows" / "pypi-publish.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert (
        "ref: ${{ github.event_name == 'workflow_dispatch' && "
        "inputs.release-tag || github.event.release.tag_name }}"
    ) in workflow

    health_check = workflow.split("gh workflow run distribution-check.yml", 1)[1]
    assert "--ref main" in health_check
    assert '-f release-tag="$RELEASE_TAG"' in health_check


def test_distribution_health_uses_local_outreach_notes_not_repo_tracking_files() -> None:
    workflow = (ROOT / ".github" / "workflows" / "distribution-check.yml").read_text(
        encoding="utf-8"
    )
    assert "bootstrap-outreach-log.py notes/sam-doctor-outreach-log.csv" in workflow
    assert 'python scripts/bootstrap-outreach-log.py notes/sam-doctor-outreach-log.csv' in workflow
    assert "--outreach-log notes/sam-doctor-outreach-log.csv" in workflow


def test_publish_checklist_has_no_growth_or_outreach_content() -> None:
    publish = (ROOT / "launch" / "PUBLISH.md").read_text(encoding="utf-8")
    assert "outreach" not in publish.lower()
    assert "revenue" not in publish.lower()
    assert "distribution" not in publish.lower()


def test_stable_install_links_match_project_version() -> None:
    version = _project_version()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    assert "python -m pip install sam-doctor" in readme
    assert "https://pypi.org/project/sam-doctor/" in readme
    assert "python -m pip install sam-doctor" in site
    assert "https://pypi.org/project/sam-doctor/" in site
    assert f"releases/tag/v{version}" in site
