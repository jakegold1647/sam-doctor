#!/usr/bin/env python3
"""Sync public-site metadata with canonical package and page values.

Usage:
  python scripts/sync-site-metadata.py

This keeps the public site's release display aligned with pyproject.toml and
generates a canonical social-card head for every indexable HTML page.

The README deliberately carries no version: it installs unpinned from PyPI and
points at `@<tag>` for source installs, so there is nothing here to sync. Its
three anchors were removed once this script started reporting dead ones - they
had matched nothing since the README was rewritten on 2026-08-05.
"""

from __future__ import annotations

import argparse
import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    # Python 3.10 compatibility fallback for environments that still prefer tomli.
    import tomli as tomllib  # type: ignore[no-redef]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
INDEX_PATH = SITE_ROOT / "index.html"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
SOCIAL_IMAGE_URL = (
    "https://sam-doctor.jacobgoldstein.dev/assets/sam-doctor-social-preview.jpg"
)
SOCIAL_IMAGE_ALT = (
    "SAM Doctor identifies the next useful check in a failed AWS deployment"
)
SOCIAL_DESCRIPTION_OVERRIDES = {
    "index.html": (
        "Turn AWS SAM, CloudFormation, IAM, and GitHub Actions deployment failures "
        "into a focused next check. SAM Doctor runs locally, cites the evidence it "
        "matched, and never needs AWS credentials."
    ),
    "quickstart.html": (
        "Start with one sanitized excerpt and get an actionable finding in "
        "minutes for SAM, CDK, or CloudFormation deployment failures."
    ),
}
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
SOCIAL_META_TAG_PATTERN = re.compile(
    r"\n[ \t]*<meta\b(?=[^>]*\b(?:property|name)\s*=\s*[\"']"
    r"(?:og:|twitter:)[^\"']*[\"'])"
    r"[^>]*?/?>",
    re.IGNORECASE,
)
CANONICAL_TAG_PATTERN = re.compile(
    r"(?P<indent>^[ \t]*)<link\b(?=[^>]*\brel\s*=\s*[\"']canonical[\"'])"
    r"[^>]*?/?>",
    flags=re.IGNORECASE | re.MULTILINE,
)


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


class _PageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.title_count = 0
        self.descriptions: list[str] = []
        self.canonicals: list[str] = []
        self.robots: list[str] = []
        self._in_title = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        if tag == "title":
            self.title_count += 1
            self._in_title = True
        elif tag == "meta":
            name = attributes.get("name", "").lower()
            if name == "description":
                self.descriptions.append(attributes.get("content", ""))
            elif name == "robots":
                self.robots.append(attributes.get("content", ""))
        elif tag == "link" and attributes.get("rel", "").lower() == "canonical":
            self.canonicals.append(attributes.get("href", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def _page_label(path: Path) -> str:
    return f"site/{path.relative_to(SITE_ROOT).as_posix()}"


def _social_metadata_block(
    *, path: Path, title: str, description: str, canonical: str, indent: str
) -> str:
    relative_path = path.relative_to(SITE_ROOT).as_posix()
    social_description = SOCIAL_DESCRIPTION_OVERRIDES.get(
        relative_path, description
    )
    page_type = (
        "article"
        if relative_path.startswith("errors/") and relative_path != "errors/index.html"
        else "website"
    )
    values = {
        "title": html.escape(title, quote=True),
        "description": html.escape(social_description, quote=True),
        "canonical": html.escape(canonical, quote=True),
        "image": html.escape(SOCIAL_IMAGE_URL, quote=True),
        "image_alt": html.escape(SOCIAL_IMAGE_ALT, quote=True),
    }
    tags = [
        '<meta property="og:site_name" content="SAM Doctor" />',
        '<meta property="og:locale" content="en_US" />',
        f'<meta property="og:type" content="{page_type}" />',
        f'<meta property="og:title" content="{values["title"]}" />',
        f'<meta property="og:description" content="{values["description"]}" />',
        f'<meta property="og:url" content="{values["canonical"]}" />',
        f'<meta property="og:image" content="{values["image"]}" />',
        '<meta property="og:image:type" content="image/jpeg" />',
        '<meta property="og:image:width" content="1280" />',
        '<meta property="og:image:height" content="640" />',
        f'<meta property="og:image:alt" content="{values["image_alt"]}" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:title" content="{values["title"]}" />',
        f'<meta name="twitter:description" content="{values["description"]}" />',
        f'<meta name="twitter:image" content="{values["image"]}" />',
        f'<meta name="twitter:image:alt" content="{values["image_alt"]}" />',
    ]
    return "\n".join(f"{indent}{tag}" for tag in tags)


def _sync_social_metadata(path: Path, text: str) -> tuple[str, list[str]]:
    parser = _PageMetadataParser()
    parser.feed(text)
    parser.close()

    robots = ",".join(parser.robots).lower()
    robots_directives = {token.strip() for token in robots.split(",")}
    if robots_directives & {"noindex", "none"}:
        return text, []

    missing: list[str] = []
    label = _page_label(path)
    title = _normalize_whitespace("".join(parser.title_parts))
    if parser.title_count != 1 or not title:
        missing.append(f"{label}: exactly one nonempty title")
    if len(parser.descriptions) != 1 or not parser.descriptions[0].strip():
        missing.append(f"{label}: exactly one nonempty description")
    if len(parser.canonicals) != 1 or not parser.canonicals[0].strip():
        missing.append(f"{label}: exactly one nonempty canonical URL")
    if missing:
        return text, missing

    description = _normalize_whitespace(parser.descriptions[0])
    canonical = parser.canonicals[0].strip()
    without_social = SOCIAL_META_TAG_PATTERN.sub("", text)
    canonical_match = CANONICAL_TAG_PATTERN.search(without_social)
    if canonical_match is None:
        return text, [f"{label}: canonical link insertion point"]
    social = _social_metadata_block(
        path=path,
        title=title,
        description=description,
        canonical=canonical,
        indent=canonical_match.group("indent"),
    )
    updated = (
        without_social[: canonical_match.end()]
        + "\n"
        + social
        + without_social[canonical_match.end() :]
    )
    return updated, []


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

    changed_paths: set[Path] = set()
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
        changed_paths.add(INDEX_PATH)

    for page in sorted(SITE_ROOT.rglob("*.html")):
        if not write and page.resolve() == INDEX_PATH.resolve():
            page_text = updated_index
        else:
            page_text = page.read_text(encoding="utf-8")
        updated_page, page_missing = _sync_social_metadata(page, page_text)
        missing.extend(page_missing)
        if updated_page == page_text:
            continue
        if write:
            page.write_text(updated_page, encoding="utf-8")
        changed_paths.add(page)

    return len(changed_paths), version, missing


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync site version and social metadata.",
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
        print("these metadata anchors are missing or invalid:")
        for label in missing:
            print(f"- {label}")
        print(
            "restore the required page metadata or update the sync pattern in "
            "scripts/sync-site-metadata.py"
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
