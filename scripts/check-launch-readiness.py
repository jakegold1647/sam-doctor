#!/usr/bin/env python3
"""Validate launch and release consistency before publishing a tag."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass
class _CheckResult:
    passed: int = 0
    failed: int = 0

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def report(self, label: str, passed: bool, detail: str) -> None:
        if passed:
            print(f"PASS: {label} - {detail}")
            self.passed += 1
        else:
            print(f"FAIL: {label} - {detail}")
            self.failed += 1


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _version_from_pyproject(root: Path) -> str:
    pyproject = _read_text(root / "pyproject.toml")
    data = tomllib.loads(pyproject)
    project = data.get("project", {})
    return project["version"]


def _version_from_init(root: Path) -> str:
    contents = _read_text(root / "src" / "sam_doctor" / "__init__.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', contents)
    if not match:
        raise ValueError("Could not parse __version__ from src/sam_doctor/__init__.py")
    return match.group(1)


def _changelog_has_version(root: Path, version: str) -> bool:
    lines = _read_text(root / "CHANGELOG.md").splitlines()
    return any(line.startswith(f"## v{version} - ") for line in lines)


def _release_note_exists(root: Path, version: str) -> bool:
    return (root / "launch" / f"RELEASE-v{version}.md").exists()


def _marketplace_metadata_ok(root: Path) -> bool:
    action_yaml = root / "action.yml"
    if not action_yaml.exists():
        return False
    text = action_yaml.read_text(encoding="utf-8")
    required_tokens = [
        "name:",
        "description:",
        "branding:",
        "runs:",
        "using: composite",
        "log-file:",
    ]
    return all(token in text for token in required_tokens)


def _is_prerelease(version: str) -> bool:
    return "-" in version


def _run_checks(root: Path) -> _CheckResult:
    result = _CheckResult()
    pyproject_version = _version_from_pyproject(root)
    init_version = _version_from_init(root)
    is_prerelease = _is_prerelease(pyproject_version)

    result.report(
        "version consistency",
        pyproject_version == init_version,
        f"pyproject={pyproject_version}, __init__={init_version}",
    )
    if is_prerelease:
        result.report(
            "prerelease release note",
            True,
            "release-note/changelog checks are optional until final stable release",
        )
        result.report(
            "marketplace action metadata",
            _marketplace_metadata_ok(root),
            f"required fields present in {root / 'action.yml'}",
        )
    else:
        release_exists = _release_note_exists(root, pyproject_version)
        changelog_ok = _changelog_has_version(root, pyproject_version)
        result.report(
            "release note file",
            release_exists,
            f"launch/RELEASE-v{pyproject_version}.md {'present' if release_exists else 'missing'}",
        )
        result.report(
            "changelog entry",
            changelog_ok,
            f"CHANGELOG.md contains v{pyproject_version}",
        )
        result.report(
            "marketplace action metadata",
            _marketplace_metadata_ok(root),
            f"required fields present in {root / 'action.yml'}",
        )

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root passed for repeatable checks.",
    )
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if not root.exists():
        print(f"root does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"root is not a directory: {root}", file=sys.stderr)
        return 1

    result = _run_checks(root)
    print(f"checks passed: {result.passed}, checks failed: {result.failed}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
