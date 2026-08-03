from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, flags=re.MULTILINE)
    assert match is not None
    return match.group(1)


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


def test_stable_install_links_match_project_version() -> None:
    version = _project_version()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    assert "python -m pip install sam-doctor" in readme
    assert "https://pypi.org/project/sam-doctor/" in readme
    assert "python -m pip install sam-doctor" in site
    assert "https://pypi.org/project/sam-doctor/" in site
    assert f"releases/tag/v{version}" in site
