from pathlib import Path
import importlib.util
import sys


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
        "\n".join(
            [
                "name: SAM Doctor AWS Deployment Diagnostics",
                "description: Diagnose local AWS deployment failures",
                "branding:",
                "  icon: activity",
                "  color: yellow",
                "runs:",
                "  using: composite",
                "  steps: []",
                "inputs:",
                "  log-file:",
                "    description: Path to the deployment log to diagnose.",
                "    required: true",
            ]
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
