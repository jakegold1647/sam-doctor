import gzip
import io
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

import yaml

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


def test_release_build_is_manual_default_branch_and_read_only() -> None:
    path = ROOT / ".github" / "workflows" / "release.yml"
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert set(parsed["on"]) == {"workflow_dispatch"}
    assert parsed["permissions"] == {}
    assert parsed["concurrency"] == {
        "group": "release-publishing",
        "cancel-in-progress": "false",
    }

    build = parsed["jobs"]["build"]
    assert build["permissions"] == {"contents": "read"}
    resolver = build["steps"][0]
    assert resolver["env"]["RELEASE_TAG"] == "${{ inputs.release-tag }}"
    resolver_script = resolver["run"]
    for required in (
        'GITHUB_REF" != "refs/heads/${default_branch}',
        'WORKFLOW_SHA" != "$default_commit',
        "/git/ref/tags/${encoded_tag}",
        "/git/tags/${tag_commit}",
        "/compare/${tag_commit}...${default_commit}",
        "merge_base_commit.sha",
    ):
        assert required in resolver_script

    checkout = build["steps"][1]
    assert checkout["with"]["ref"] == "${{ steps.resolve.outputs.tag_commit }}"
    assert checkout["with"]["persist-credentials"] == "false"
    serialized_steps = yaml.dump(build["steps"])
    assert "python -m build" in serialized_steps
    assert "actions/upload-artifact@" in serialized_steps
    assert "contents: write" not in yaml.dump(build)
    assert "actions: write" not in yaml.dump(build)


def test_release_build_pins_and_normalizes_package_timestamps() -> None:
    path = ROOT / ".github" / "workflows" / "release.yml"
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    steps = yaml.dump(parsed["jobs"]["build"]["steps"])

    assert "git show -s --format=%ct" in steps
    assert "SOURCE_DATE_EPOCH" in steps
    assert "scripts/reproducible-sdist.py dist/*.tar.gz" in steps


def _write_test_archive(path: Path, *, member_mtime: int, gzip_mtime: int) -> None:
    with (
        path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=gzip_mtime) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        root = tarfile.TarInfo("sam_doctor-0.0.0")
        root.type = tarfile.DIRTYPE
        root.mtime = member_mtime
        archive.addfile(root)

        payload = b"stable source bytes\n"
        member = tarfile.TarInfo("sam_doctor-0.0.0/README.md")
        member.mtime = member_mtime
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))


def test_reproducible_sdist_normalizer_produces_identical_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    _write_test_archive(first, member_mtime=1_700_000_001, gzip_mtime=1_700_000_002)
    _write_test_archive(second, member_mtime=1_700_000_101, gzip_mtime=1_700_000_102)

    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = "1700000000"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "reproducible-sdist.py"),
    ]
    for archive in (first, second):
        subprocess.run(
            [*command, str(archive)],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )

    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, mode="r:gz") as archive:
        assert all(member.mtime == 1_700_000_000 for member in archive.getmembers())


def test_release_write_job_only_verifies_and_publishes_prebuilt_bytes() -> None:
    path = ROOT / ".github" / "workflows" / "release.yml"
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    publish = parsed["jobs"]["publish"]

    assert publish["needs"] == "build"
    assert publish["permissions"] == {"actions": "write", "contents": "write"}
    serialized_steps = yaml.dump(publish["steps"])
    assert "actions/checkout@" not in serialized_steps
    assert "actions/setup-python@" not in serialized_steps
    assert "pip install" not in serialized_steps
    assert "python " not in serialized_steps
    assert 'gh run download "$GITHUB_RUN_ID"' in publish["steps"][0]["run"]
    assert "sha256sum --check --strict" in publish["steps"][1]["run"]
    release_script = publish["steps"][2]["run"]
    assert 'gh release create "$RELEASE_TAG"' in release_script
    assert "/git/ref/tags/${encoded_tag}" in release_script
    assert 'current_tag_commit" != "$TAG_COMMIT' in release_script
    assert ".draft == false" in release_script
    assert ".assets | type" in release_script
    assert ".digest == $wheel_digest" in release_script
    assert ".digest == $sdist_digest" in release_script
    assert "dist/*" not in serialized_steps

    stable_step = publish["steps"][-1]
    assert stable_step["if"] == "${{ needs.build.outputs.prerelease == 'false' }}"
    assert "gh workflow run pypi-publish.yml" in stable_step["run"]
    assert '--ref "$DEFAULT_BRANCH"' in stable_step["run"]
    assert '-f release-tag="$RELEASE_TAG"' in stable_step["run"]
    assert "/git/refs/tags/v0" in stable_step["run"]
    assert "/compare/${v0_commit}...${TAG_COMMIT}" in stable_step["run"]
    assert "v0 already points to a newer stable release" in stable_step["run"]


def test_pypi_publish_uses_only_default_branch_manual_dispatch() -> None:
    path = ROOT / ".github" / "workflows" / "pypi-publish.yml"
    workflow = path.read_text(encoding="utf-8")
    parsed = yaml.load(workflow, Loader=yaml.BaseLoader)

    assert set(parsed["on"]) == {"workflow_dispatch"}
    assert parsed["permissions"] == {}
    validate_job = parsed["jobs"]["validate-release"]
    assert validate_job["permissions"] == {"contents": "read"}
    assert "environment" not in validate_job

    resolver = validate_job["steps"][0]
    resolver_script = resolver["run"]
    assert 'GITHUB_REF" != "refs/heads/${default_branch}' in resolver_script
    assert "jq -sRr @uri" in resolver_script
    assert "/git/ref/heads/${encoded_default_branch}" in resolver_script
    assert 'WORKFLOW_SHA" != "$trusted_commit' in resolver_script

    checkout = validate_job["steps"][1]
    assert checkout["with"]["ref"] == "${{ steps.trusted-source.outputs.commit }}"
    assert checkout["with"]["persist-credentials"] == "false"
    assert checkout["with"]["fetch-depth"] == "1"

    validation = validate_job["steps"][2]
    assert validation["env"]["RELEASE_TAG"] == "${{ inputs.release-tag }}"
    assert "scripts/validate-pypi-release.py validate" in validation["run"]


def test_pypi_publish_rechecks_assets_in_oidc_job_without_building() -> None:
    path = ROOT / ".github" / "workflows" / "pypi-publish.yml"
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    publish = parsed["jobs"]["publish"]

    assert publish["needs"] == "validate-release"
    assert publish["environment"] == {
        "name": "pypi",
        "url": "https://pypi.org/project/sam-doctor/",
    }
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}

    serialized_steps = yaml.dump(publish["steps"])
    assert "actions/checkout@" not in serialized_steps
    assert "actions/setup-python@" not in serialized_steps
    assert "pip install" not in serialized_steps
    assert "python -m build" not in serialized_steps
    assert "?ref=${TRUSTED_COMMIT}" in serialized_steps
    assert "sha256sum --check --strict" in serialized_steps
    assert 'python3 "$VALIDATOR_PATH" recheck' in publish["steps"][1]["run"]
    for expected_argument in (
        "--tag-commit",
        "--wheel-asset-id",
        "--wheel-digest",
        "--wheel-size",
        "--sdist-asset-id",
        "--sdist-digest",
        "--sdist-size",
    ):
        assert expected_argument in serialized_steps
    assert "pypa/gh-action-pypi-publish@" in serialized_steps


def test_post_publish_health_has_no_oidc_permission() -> None:
    path = ROOT / ".github" / "workflows" / "pypi-publish.yml"
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    health = parsed["jobs"]["post-release-health"]

    assert health["needs"] == ["validate-release", "publish"]
    assert health["permissions"] == {"contents": "read", "actions": "write"}
    health_check = health["steps"][0]["run"]
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
