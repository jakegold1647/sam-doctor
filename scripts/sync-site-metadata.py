#!/usr/bin/env python3
"""Sync selected marketing metadata with the package version.

Usage:
  python scripts/sync-site-metadata.py

This keeps the public site and README release display aligned with pyproject.toml.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    # Python 3.10 compatibility fallback for environments that still prefer tomli.
    import tomli as tomllib  # type: ignore[no-redef]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_PATH = PROJECT_ROOT / "README.md"
INDEX_PATH = PROJECT_ROOT / "site" / "index.html"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
CURRENT_RELEASE_PATTERN = re.compile(r"Current release: \*\*v(?P<version>\d+\.\d+\.\d+)\*\*")
SOFTWARE_VERSION_PATTERN = re.compile(r'"softwareVersion":\s*"(?P<version>\d+\.\d+\.\d+)"')
README_PIN_PATTERN = re.compile(r"sam-doctor==(?P<version>\d+\.\d+\.\d+)")
README_GITPIN_PATTERN = re.compile(
    r'sam-doctor @ git\+https://github\.com/jakegold1647/sam-doctor\.git@v(?P<version>\d+\.\d+\.\d+)'
)
INDEX_INSTALL_HEADING_PATTERN = re.compile(
    r'(<h2 id="install-title">)Install v(?P<version>\d+\.\d+\.\d+) in one command\.</h2>'
)
INDEX_RELEASE_LINK_PATTERN = re.compile(
    r'https://github\.com/jakegold1647/sam-doctor/releases/tag/v(?P<version>\d+\.\d+\.\d+)'
)
INDEX_RELEASE_LINK_LABEL_PATTERN = re.compile(
    r"View v(?P<version>\d+\.\d+\.\d+) release notes"
)


def _read_version() -> str:
    payload = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    project: dict[str, Any] = payload.get("project", {})
    version = project.get("version")
    if not version or not isinstance(version, str):
        raise RuntimeError("project.version missing or invalid in pyproject.toml")
    return version.strip()


def sync_metadata(write: bool = True) -> tuple[int, str]:
    version = _read_version()
    print(f"syncing metadata for version: {version}")

    changes = 0
    readme_text = README_PATH.read_text(encoding="utf-8")
    updated_readme = CURRENT_RELEASE_PATTERN.sub(
        lambda _match: f"Current release: **v{version}**",
        readme_text,
    )
    updated_readme = README_PIN_PATTERN.sub(
        lambda _match: f"sam-doctor=={version}",
        updated_readme,
    )
    updated_readme = README_GITPIN_PATTERN.sub(
        lambda _match: f"sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v{version}",
        updated_readme,
    )
    if updated_readme != readme_text:
        if write:
            README_PATH.write_text(updated_readme, encoding="utf-8")
        changes += 1

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    updated_index = SOFTWARE_VERSION_PATTERN.sub(
        lambda _match: f'"softwareVersion": "{version}"',
        index_text,
    )
    updated_index = INDEX_INSTALL_HEADING_PATTERN.sub(
        lambda _match: f'<h2 id="install-title">Install v{version} in one command.</h2>',
        updated_index,
    )
    updated_index = INDEX_RELEASE_LINK_PATTERN.sub(
        lambda _match: f"https://github.com/jakegold1647/sam-doctor/releases/tag/v{version}",
        updated_index,
    )
    updated_index = INDEX_RELEASE_LINK_LABEL_PATTERN.sub(
        lambda _match: f"View v{version} release notes",
        updated_index,
    )
    if updated_index != index_text:
        if write:
            INDEX_PATH.write_text(updated_index, encoding="utf-8")
        changes += 1

    return changes, version


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync site metadata from pyproject version.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify metadata is aligned but do not modify files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    initial_changes, _ = sync_metadata(write=not args.check)
    if args.check:
        if initial_changes:
            print("metadata is out of sync; run without --check to update files")
            return 1
        print("metadata is in sync")
    else:
        print(f"metadata sync complete (updated sections: {initial_changes})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
