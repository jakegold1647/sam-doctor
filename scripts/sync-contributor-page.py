#!/usr/bin/env python3
"""Keep the public contributor page derived from CONTRIBUTORS.md.

The Markdown record is the human-reviewed source of truth for Hall of Fame
cards. This script turns its structured entries into the cards, the README
callout, and a diagnostic count tied to the actual rule catalog. It intentionally
does not call GitHub's API at build time: a pull request should be deterministic.
The shipped page may refresh the contributor total in the browser and keeps the
generated count as an offline fallback.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTORS_PATH = PROJECT_ROOT / "CONTRIBUTORS.md"
PAGE_PATH = PROJECT_ROOT / "site" / "contributors" / "index.html"
README_PATH = PROJECT_ROOT / "README.md"
# The link is optional. A contributor who deletes their GitHub account still
# shipped the work, so the entry keeps its badge and summary and simply drops
# the profile link rather than the person - a 404 is not a way to say thank you.
ENTRY_PATTERN = re.compile(
    r"^- (?:\[(?P<name>[^\]]+)\]\((?P<url>https://github\.com/[^)]+)\)"
    r"|(?P<plain_name>[A-Za-z0-9][A-Za-z0-9._-]*))"
    r" — (?P<badge>[^—]+) — (?P<summary>.+?)\s*$"
)
# Shown instead of the profile link when an entry has no reachable profile. This
# matches how the page already credits Harshil, whose commits carry no profile.
NO_PROFILE_NOTE = (
    "Intentionally unlinked because this GitHub account no longer exists. "
    "The contribution record stands."
)
SECTION_PATTERN = re.compile(
    r"^## People who have shipped changes\s*$", re.MULTILINE
)
NEXT_SECTION_PATTERN = re.compile(r"^##\s+", re.MULTILINE)
GENERATED_STATS_PATTERN = re.compile(
    r"<!-- BEGIN GENERATED CONTRIBUTOR STATS -->.*?"
    r"<!-- END GENERATED CONTRIBUTOR STATS -->",
    re.DOTALL,
)
GENERATED_CARDS_PATTERN = re.compile(
    r"<!-- BEGIN GENERATED CONTRIBUTOR CARDS -->.*?"
    r"<!-- END GENERATED CONTRIBUTOR CARDS -->",
    re.DOTALL,
)
GENERATED_CALLOUT_PATTERN = re.compile(
    r"<!-- BEGIN GENERATED CONTRIBUTOR CALLOUT -->.*?"
    r"<!-- END GENERATED CONTRIBUTOR CALLOUT -->",
    re.DOTALL,
)


@dataclass(frozen=True)
class Contributor:
    name: str
    url: str | None
    badge: str
    summary: str


def _read_contributors(text: str) -> list[Contributor]:
    section = SECTION_PATTERN.search(text)
    if section is None:
        raise ValueError("CONTRIBUTORS.md is missing the shipped-changes section")

    remainder = text[section.end() :]
    next_section = NEXT_SECTION_PATTERN.search(remainder)
    if next_section is not None:
        remainder = remainder[: next_section.start()]

    entries: list[Contributor] = []
    for line in remainder.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("- "):
            # Prose: the format guidance above the list, or the notes below it.
            # Anything after the first entry ends the list.
            if entries:
                break
            continue
        match = ENTRY_PATTERN.fullmatch(stripped)
        if match is None:
            raise ValueError(
                "Every shipped contributor must use "
                "`- [handle](https://github.com/handle) — badge — summary`, or "
                "`- handle — badge — summary` when the profile no longer exists"
            )
        linked_name = match.group("name")
        url = match.group("url")
        entries.append(
            Contributor(
                name=(linked_name or match.group("plain_name")).strip(),
                url=url.strip() if url else None,
                badge=match.group("badge").strip(),
                summary=match.group("summary").strip(),
            )
        )

    if not entries:
        raise ValueError("CONTRIBUTORS.md has no shipped contributors")
    names = [entry.name.casefold() for entry in entries]
    urls = [entry.url.casefold() for entry in entries if entry.url]
    if len(names) != len(set(names)):
        raise ValueError("CONTRIBUTORS.md contains duplicate contributor names")
    if len(urls) != len(set(urls)):
        raise ValueError("CONTRIBUTORS.md contains duplicate contributor URLs")
    return entries


def _rule_count() -> int:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from sam_doctor.diagnostics import supported_rules

    return len(supported_rules())


def _stats_block(contributor_count: int, rule_count: int) -> str:
    return "\n".join(
        (
            "<!-- BEGIN GENERATED CONTRIBUTOR STATS -->",
            '      <section class="hall-stats" aria-label="Community snapshot">',
            f'        <div class="hall-stat"><strong id="github-contributor-count" data-fallback="{contributor_count}" aria-live="polite">{contributor_count}</strong><span id="github-contributor-label">GitHub contributors (live)</span></div>',
            f'        <div class="hall-stat"><strong>{rule_count}</strong><span>documented diagnostics to improve</span></div>',
            '        <div class="hall-stat"><strong>GitHub</strong><span>current issue queue and discussions</span></div>',
            "      </section>",
            "<!-- END GENERATED CONTRIBUTOR STATS -->",
        )
    )


def _card(entry: Contributor, number: int, *, featured: bool) -> str:
    card_class = ' class="hall-card hall-card-featured"' if featured else ' class="hall-card"'
    name = html.escape(entry.name, quote=True)
    badge = html.escape(entry.badge, quote=True)
    summary = html.escape(entry.summary, quote=True)
    if entry.url:
        url = html.escape(entry.url, quote=True)
        heading = f'            <h3><a href="{url}">{name}</a></h3>'
        footer = (
            f'            <a class="hall-link" href="{url}">View profile '
            '<span aria-hidden="true">↗</span></a>'
        )
    else:
        # The card keeps its number, badge, and summary: the credit is the point,
        # and linking a deleted account would only send readers to a 404.
        heading = f"            <h3>{name}</h3>"
        footer = (
            '            <p class="hall-note"><span aria-hidden="true">—</span> '
            f"{html.escape(NO_PROFILE_NOTE)}</p>"
        )
    return "\n".join(
        (
            f"          <article{card_class}>",
            f'            <div class="hall-card-top"><span class="hall-number">{number:02d}</span><span class="hall-badge">{badge}</span></div>',
            heading,
            f"            <p>{summary}</p>",
            footer,
            "          </article>",
        )
    )


def _cards_block(entries: list[Contributor]) -> str:
    cards = "\n".join(
        _card(entry, index, featured=index == 1)
        for index, entry in enumerate(entries, start=1)
    )
    return (
        "<!-- BEGIN GENERATED CONTRIBUTOR CARDS -->\n"
        f'        <div class="hall-grid">\n{cards}\n        </div>\n'
        "<!-- END GENERATED CONTRIBUTOR CARDS -->"
    )


def _callout_block(entries: list[Contributor]) -> str:
    names = " · ".join(
        f"[{entry.name}]({entry.url})" if entry.url else entry.name
        for entry in entries
    )
    return (
        "<!-- BEGIN GENERATED CONTRIBUTOR CALLOUT -->\n"
        "## Community\n\n"
        "The Hall of Fame is where shipped work gets remembered. If a diagnostic "
        "rule, fixture, docs fix, or thoughtful report makes SAM Doctor better, "
        "there is room for your name next to the people who helped build it.\n\n"
        f"**Currently recognized:** {names}\n\n"
        "[Meet the contributors](https://sam-doctor.jacobgoldstein.dev/contributors/) "
        "· [Find a mentored first issue](https://github.com/jakegold1647/sam-doctor/"
        "issues?q=is%3Aissue+is%3Aopen+label%3A%22status%3A+ready%22+label%3A%22mentor%20"
        "available%22)\n"
        "<!-- END GENERATED CONTRIBUTOR CALLOUT -->"
    )


def _replace_generated(
    text: str, pattern: re.Pattern[str], replacement: str, label: str
) -> str:
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{label} must contain exactly one generated block")
    return updated


def render_page(page_text: str, entries: list[Contributor], rule_count: int) -> str:
    stats = _stats_block(len(entries), rule_count)
    cards = _cards_block(entries)
    updated = _replace_generated(
        page_text, GENERATED_STATS_PATTERN, stats, "contributor page stats block"
    )
    updated = _replace_generated(
        updated, GENERATED_CARDS_PATTERN, cards, "contributor page cards block"
    )
    return updated


def render_readme(readme_text: str, entries: list[Contributor]) -> str:
    return _replace_generated(
        readme_text,
        GENERATED_CALLOUT_PATTERN,
        _callout_block(entries),
        "README contributor callout",
    )


def sync(*, write: bool) -> tuple[bool, str]:
    entries = _read_contributors(CONTRIBUTORS_PATH.read_text(encoding="utf-8"))
    rule_count = _rule_count()
    page_before = PAGE_PATH.read_text(encoding="utf-8")
    readme_before = README_PATH.read_text(encoding="utf-8")
    page_after = render_page(page_before, entries, rule_count)
    readme_after = render_readme(readme_before, entries)
    changed = page_before != page_after or readme_before != readme_after
    if write and changed:
        for path in (PAGE_PATH, README_PATH):
            if path.exists() and path.stat().st_nlink > 1:
                raise ValueError(f"Refusing to write hard-linked file: {path}")
        if page_before != page_after:
            PAGE_PATH.write_text(page_after, encoding="utf-8")
        if readme_before != readme_after:
            README_PATH.write_text(readme_after, encoding="utf-8")
    return changed, f"{len(entries)} contributors, {rule_count} diagnostics"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the generated contributor page is out of sync.",
    )
    args = parser.parse_args()
    try:
        changed, summary = sync(write=not args.check)
    except (OSError, ValueError, ImportError) as error:
        print(f"contributor page sync error: {error}", file=sys.stderr)
        return 1
    if args.check and changed:
        print(f"contributor page is out of sync ({summary}); run the sync script")
        return 1
    action = "out of sync; updated" if changed else "in sync"
    print(f"contributor page {action} ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
