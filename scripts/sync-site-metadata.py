#!/usr/bin/env python3
"""Sync selected marketing metadata with the package version.

Usage:
  python scripts/sync-site-metadata.py

This keeps the public site's release display aligned with pyproject.toml.

The README deliberately carries no version: it installs unpinned from PyPI and
points at `@<tag>` for source installs, so there is nothing here to sync. Its
three anchors were removed once this script started reporting dead ones - they
had matched nothing since the README was rewritten on 2026-08-05.
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
INDEX_PATH = PROJECT_ROOT / "site" / "index.html"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
SOFTWARE_VERSION_PATTERN = re.compile(r'"softwareVersion":\s*"(?P<version>\d+\.\d+\.\d+)"')
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


def _apply_anchors(
    text: str, anchors: list[tuple[str, re.Pattern[str], str]]
) -> tuple[str, list[str]]:
    """Rewrite each anchor, reporting any whose pattern no longer matches.

    Every check here is a regex substitution, so a pattern that stops matching
    does not report a problem - it quietly rewrites nothing, the text compares
    equal to itself, and --check prints "metadata is in sync". Rewording a
    heading is enough to switch off its version check permanently, and the next
    release ships a page advertising the previous version with the release gate
    green. A missing anchor is therefore a failure in its own right: it means
    this script has stopped watching something it claims to watch.
    """

    missing: list[str] = []
    for label, pattern, replacement in anchors:
        text, count = pattern.subn(lambda _match, r=replacement: r, text)
        if count == 0:
            missing.append(label)
    return text, missing


def sync_metadata(write: bool = True) -> tuple[int, str, list[str]]:
    version = _read_version()
    print(f"syncing metadata for version: {version}")

    changes = 0
    missing: list[str] = []

    index_text = INDEX_PATH.read_text(encoding="utf-8")
    updated_index, index_missing = _apply_anchors(
        index_text,
        [
            (
                'site/index.html: "softwareVersion" in structured data',
                SOFTWARE_VERSION_PATTERN,
                f'"softwareVersion": "{version}"',
            ),
            (
                "site/index.html: install heading",
                INDEX_INSTALL_HEADING_PATTERN,
                f'<h2 id="install-title">Install v{version} in one command.</h2>',
            ),
            (
                "site/index.html: release-tag link",
                INDEX_RELEASE_LINK_PATTERN,
                f"https://github.com/jakegold1647/sam-doctor/releases/tag/v{version}",
            ),
            (
                "site/index.html: 'View vX.Y.Z release notes' label",
                INDEX_RELEASE_LINK_LABEL_PATTERN,
                f"View v{version} release notes",
            ),
        ],
    )
    missing.extend(index_missing)
    if updated_index != index_text:
        if write:
            INDEX_PATH.write_text(updated_index, encoding="utf-8")
        changes += 1

    return changes, version, missing


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
    initial_changes, _, missing = sync_metadata(write=not args.check)
    if missing:
        # Fails in both modes. In --check it would otherwise pass while blind; in
        # write mode the sync silently leaves that spot on the old version.
        print("these version anchors no longer match anything:")
        for label in missing:
            print(f"- {label}")
        print(
            "the text they look for was reworded or removed; update the pattern "
            "in scripts/sync-site-metadata.py so the version stays checked"
        )
        return 1
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
