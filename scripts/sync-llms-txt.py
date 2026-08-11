#!/usr/bin/env python3
"""Sync the llms.txt exact-error guide labels with the pages they link to.

Usage:
  python scripts/sync-llms-txt.py
  python scripts/sync-llms-txt.py --check

site/llms.txt exists so that assistants summarising SAM Doctor quote the
project accurately. That only holds while the link labels match the pages, and
they silently stopped matching: a title pass moved every error page to lead
with the literal AWS error string, and llms.txt kept the older descriptive
labels. The result was a machine-readable index telling assistants a page was
called something no visitor to that page would ever see.

The page's own `<h1>` is the source of truth here, for the same reason the
error pages lead with it: it is the exact string a reader pastes from a failed
build. This script rewrites each label to match and leaves the URL and the
hand-written description after the colon untouched, so the editorial half of
the file stays editorial.

`--check` makes drift a build failure instead of a slow decay - the same shape
as scripts/sync-site-metadata.py.

Exit code 0 when llms.txt is in sync, 1 when it drifted or a link is broken.
"""

from __future__ import annotations

import argparse
import re
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
LLMS_PATH = SITE_ROOT / "llms.txt"
ERRORS_ROOT = SITE_ROOT / "errors"
SITE_ORIGIN = "https://sam-doctor.jacobgoldstein.dev"

# A list item pointing at one error page: "- [label](<origin>/errors/<slug>.html): rest".
# The label allows backslash escapes so that error strings containing square
# brackets (for example "Requires capabilities : [CAPABILITY_IAM]") survive a
# round trip through this script without breaking the markdown link.
ERROR_LINK_PATTERN = re.compile(
    r"^(?P<prefix>- \[)"
    r"(?P<label>(?:[^\[\]\\]|\\.)*)"
    r"(?P<middle>\]\()"
    r"(?P<url>" + re.escape(SITE_ORIGIN) + r"/errors/(?P<slug>[A-Za-z0-9._-]+\.html))"
    r"(?P<suffix>\).*)$",
    re.MULTILINE,
)


class _HeadingParser(HTMLParser):
    """Collect the text of the first <h1> in a page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._depth = 0
        self._parts: list[str] = []
        self.heading: str | None = None

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "h1" and self.heading is None:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1" and self._depth:
            self._depth -= 1
            if not self._depth:
                self.heading = " ".join("".join(self._parts).split())

    def handle_data(self, data: str) -> None:
        if self._depth:
            self._parts.append(data)


def _page_heading(slug: str) -> str:
    """Return the normalised <h1> text of an error page."""
    path = ERRORS_ROOT / slug
    if not path.is_file():
        raise ValueError(f"llms.txt links to {slug}, which does not exist")
    parser = _HeadingParser()
    parser.feed(path.read_text(encoding="utf-8"))
    if not parser.heading:
        raise ValueError(f"{slug} has no usable <h1> to label its llms.txt entry")
    return parser.heading


def _escape_label(heading: str) -> str:
    """Escape the characters that would otherwise end the markdown link text."""
    escaped = heading.replace(chr(92), chr(92) * 2)
    return escaped.replace("[", chr(92) + "[").replace("]", chr(92) + "]")


def sync_llms_txt(write: bool) -> tuple[list[tuple[str, str, str]], int]:
    """Align every error-guide label with its page heading.

    Returns the drifted entries as (slug, old label, new label) and the total
    number of error links inspected.
    """
    original = LLMS_PATH.read_text(encoding="utf-8")
    drifted: list[tuple[str, str, str]] = []
    seen = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal seen
        seen += 1
        slug = match.group("slug")
        expected = _escape_label(_page_heading(slug))
        current = match.group("label")
        if current != expected:
            drifted.append((slug, current, expected))
        return (
            match.group("prefix")
            + expected
            + match.group("middle")
            + match.group("url")
            + match.group("suffix")
        )

    updated = ERROR_LINK_PATTERN.sub(replace, original)
    if write and updated != original:
        LLMS_PATH.write_text(updated, encoding="utf-8", newline="\n")
    return drifted, seen


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync llms.txt error-guide labels with their page headings.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift but do not modify llms.txt.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        drifted, seen = sync_llms_txt(write=not args.check)
    except (OSError, ValueError) as error:
        print(f"llms.txt sync error: {error}")
        return 1
    if not seen:
        # The file is meant to index the error guides; matching nothing means the
        # link shape changed and this gate went blind rather than clean.
        print(f"no error-guide links found in {LLMS_PATH.name}; update the link pattern")
        return 1
    if args.check:
        if drifted:
            print(f"llms.txt labels are out of sync with {len(drifted)} of {seen} pages:")
            for slug, old, new in drifted:
                print(f"- {slug}\n    llms.txt: {old}\n    page h1 : {new}")
            print("run: python scripts/sync-llms-txt.py")
            return 1
        print(f"llms.txt labels are in sync ({seen} error guides)")
    else:
        print(f"llms.txt sync complete ({len(drifted)} of {seen} labels updated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
