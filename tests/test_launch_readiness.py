import importlib.util
import sys
from pathlib import Path


def _load_module(root: Path):
    script_path = root / "scripts" / "check-launch-readiness.py"
    spec = importlib.util.spec_from_file_location(
        "check_launch_readiness",
        str(script_path),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load check-launch-readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _create_repo(root: Path, version: str, with_release=True, with_changelog=True) -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "sam-doctor"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    src = root / "src" / "sam_doctor"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text(
        f'__version__ = "{version}"\n', encoding="utf-8"
    )
    (root / "launch").mkdir(exist_ok=True, parents=True)
    if with_release:
        (root / "launch" / f"RELEASE-v{version}.md").write_text(
            "Release note", encoding="utf-8"
        )
    if with_changelog:
        (root / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## v{version} - 2026-08-03\n",
            encoding="utf-8",
        )

    site_dir = root / "site"
    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(
        "<html><body>SAM Doctor</body></html>",
        encoding="utf-8",
    )
    (assets_dir / "sam-doctor-social-preview.jpg").write_bytes(b"fake jpg")

    (root / "action.yml").write_text(
        (
            "name: SAM Doctor AWS Deployment Diagnostics\n"
            "description: Diagnose local AWS deployment failures\n"
            "branding:\n"
            "  icon: activity\n"
            "  color: yellow\n"
            "runs:\n"
            "  using: composite\n"
            "  steps: []\n"
            "inputs:\n"
            "  log-file:\n"
            "    description: Path to the deployment log to diagnose.\n"
            "    required: true"
        ),
        encoding="utf-8",
    )
    (root / "scripts").mkdir(exist_ok=True, parents=True)
    (root / "scripts" / "check-launch-readiness.py").write_text(
        Path(__file__).resolve().parents[1].joinpath(
            "scripts", "check-launch-readiness.py"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )


def test_launch_readiness_passes_for_consistent_release_metadata(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3")
    module = _load_module(tmp_path)
    result = module._run_checks(tmp_path)
    assert result.ok
    assert result.failed == 0
    assert result.passed == 6


def test_launch_readiness_fails_when_release_metadata_missing(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3", with_release=False)
    module = _load_module(tmp_path)
    result = module._run_checks(tmp_path)
    assert not result.ok
    assert result.failed == 1
    assert result.passed == 5


def test_launch_readiness_fails_when_versions_do_not_match(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3")
    (tmp_path / "src" / "sam_doctor" / "__init__.py").write_text(
        '__version__ = "1.2.4"\n', encoding="utf-8"
    )
    module = _load_module(tmp_path)
    result = module._run_checks(tmp_path)
    assert not result.ok
    assert result.failed == 1
    assert result.passed == 5


def test_launch_readiness_prerelease_skips_release_note_requirements(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3-rc.1", with_release=False, with_changelog=False)
    module = _load_module(tmp_path)
    result = module._run_checks(tmp_path)
    assert result.ok
    assert result.failed == 0
    assert result.passed == 5


def test_launch_readiness_flags_stable_release_marked_as_prerelease(tmp_path: Path, monkeypatch) -> None:
    _create_repo(tmp_path, "1.2.3", with_release=True, with_changelog=True)

    module = _load_module(tmp_path)
    original_get_json = module._get_json
    expected_topics = [
        "aws",
        "aws-sam",
        "cloudformation",
        "github-actions",
        "iam",
        "python",
        "serverless",
        "cli",
    ]

    def fake_get_json(url: str, token: str | None):
        if url.endswith("/jakegold1647/sam-doctor/releases/tags/v1.2.3"):
            return {"prerelease": True}, 200
        if url == "https://api.github.com/repos/jakegold1647/sam-doctor":
            return {"homepage": "https://jakegold1647.github.io/sam-doctor/", "topics": expected_topics}, 200
        return original_get_json(url, token)

    monkeypatch.setattr(module, "_get_json", fake_get_json)

    result = module._run_checks_with_options(
        tmp_path,
        repo="jakegold1647/sam-doctor",
        token="token",
    )
    assert not result.ok
    assert result.failed == 1
    assert result.passed == 5


def test_launch_readiness_can_skip_remote_release_state_for_monitoring(
    tmp_path: Path, monkeypatch
) -> None:
    _create_repo(tmp_path, "1.2.3", with_release=True, with_changelog=True)

    module = _load_module(tmp_path)
    expected_topics = [
        "aws",
        "aws-sam",
        "cloudformation",
        "github-actions",
        "iam",
        "python",
        "serverless",
        "cli",
    ]

    def fake_get_json(url: str, token: str | None):
        assert url == "https://api.github.com/repos/jakegold1647/sam-doctor"
        return {
            "homepage": "https://jakegold1647.github.io/sam-doctor/",
            "topics": expected_topics,
        }, 200

    monkeypatch.setattr(module, "_get_json", fake_get_json)

    result = module._run_checks_with_options(
        tmp_path,
        repo="jakegold1647/sam-doctor",
        token="token",
        check_release_state=False,
    )
    assert result.ok
    assert result.failed == 0
    assert result.passed == 6


def test_launch_readiness_flags_stable_release_marked_as_draft(tmp_path: Path, monkeypatch) -> None:
    _create_repo(tmp_path, "1.2.3", with_release=True, with_changelog=True)

    module = _load_module(tmp_path)
    original_get_json = module._get_json
    expected_topics = [
        "aws",
        "aws-sam",
        "cloudformation",
        "github-actions",
        "iam",
        "python",
        "serverless",
        "cli",
    ]

    def fake_get_json(url: str, token: str | None):
        if url.endswith("/jakegold1647/sam-doctor/releases/tags/v1.2.3"):
            return {"prerelease": False, "draft": True}, 200
        if url == "https://api.github.com/repos/jakegold1647/sam-doctor":
            return {"homepage": "https://jakegold1647.github.io/sam-doctor/", "topics": expected_topics}, 200
        return original_get_json(url, token)

    monkeypatch.setattr(module, "_get_json", fake_get_json)

    result = module._run_checks_with_options(
        tmp_path,
        repo="jakegold1647/sam-doctor",
        token="token",
    )
    assert not result.ok
    assert result.failed == 1
    assert result.passed == 5


def test_launch_readiness_fails_when_action_metadata_is_missing(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3", with_release=True, with_changelog=True)
    (tmp_path / "action.yml").unlink()
    module = _load_module(tmp_path)
    result = module._run_checks(tmp_path)
    assert not result.ok
    assert result.failed == 1
    assert result.passed == 5


def test_launch_readiness_skips_remote_metadata_without_token(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3")
    module = _load_module(tmp_path)
    result = module._run_checks_with_options(
        tmp_path,
        repo="jakegold1647/sam-doctor",
        token=None,
    )
    assert result.failed == 0
    assert result.passed == 6


def _run_with_tag(module, root: Path, tag: str):
    return module._run_checks_with_options(
        root,
        repo="jakegold1647/sam-doctor",
        token=None,
        check_release_state=False,
        tag=tag,
    )


def test_a_tag_matching_the_packaged_version_passes(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3")
    module = _load_module(tmp_path)

    result = _run_with_tag(module, tmp_path, "v1.2.3")

    assert result.ok, "a correct tag must not fail the readiness check"


def test_a_tag_that_disagrees_with_the_packaged_version_fails(tmp_path: Path) -> None:
    # This is the check's whole reason for existing. Without it the release
    # builds the packaged version, `gh release create` attaches those artifacts
    # to the mismatched tag anyway, and the PyPI step - correctly using
    # skip-existing so a re-dispatch is a no-op - sees that version already
    # published and does nothing. A release tagged for a version it does not
    # contain, and nothing fails to say so.
    _create_repo(tmp_path, "1.2.3")
    module = _load_module(tmp_path)

    result = _run_with_tag(module, tmp_path, "v1.3.0")

    assert not result.ok
    assert result.failed == 1


def test_the_tag_check_is_opt_in(tmp_path: Path) -> None:
    # Scheduled monitoring runs have no tag, and must not start failing.
    _create_repo(tmp_path, "1.2.3")
    module = _load_module(tmp_path)

    without = module._run_checks_with_options(
        tmp_path, repo="jakegold1647/sam-doctor", token=None, check_release_state=False
    )
    with_tag = _run_with_tag(module, tmp_path, "v1.2.3")

    assert without.ok
    # The tag check adds exactly one assertion when a tag is supplied.
    assert with_tag.passed == without.passed + 1


def test_a_tag_without_the_v_prefix_is_accepted(tmp_path: Path) -> None:
    _create_repo(tmp_path, "1.2.3")
    module = _load_module(tmp_path)

    assert _run_with_tag(module, tmp_path, "1.2.3").ok
