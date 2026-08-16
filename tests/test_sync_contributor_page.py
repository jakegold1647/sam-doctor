"""Regression coverage for the generated contributor Hall of Fame page."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_sync():
    spec = importlib.util.spec_from_file_location(
        "sync_contributor_page",
        str(ROOT / "scripts" / "sync-contributor-page.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load sync-contributor-page.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_real_contributor_page_is_in_sync() -> None:
    module = _load_sync()

    changed, summary = module.sync(write=False)

    assert changed is False
    assert summary == "7 contributors, 92 diagnostics"


def test_hall_stats_use_live_github_count_with_fallback() -> None:
    module = _load_sync()

    rendered = module._stats_block(7, 90)

    assert 'id="github-contributor-count"' in rendered
    assert 'data-fallback="7"' in rendered
    assert "GitHub contributors (live)" in rendered


def test_live_count_script_uses_github_with_offline_fallback() -> None:
    script = (ROOT / "site" / "contributors" / "live-count.js").read_text(
        encoding="utf-8"
    )

    assert "api.github.com/repos/jakegold1647/sam-doctor/contributors" in script
    assert "anon=1&per_page=100" in script
    assert "offline snapshot" in script


def test_entries_render_in_record_order() -> None:
    module = _load_sync()
    entries = module._read_contributors(
        """# Contributors

## People who have shipped changes

Each entry uses this format:
`- [handle](https://github.com/handle) — badge — summary`.

- [first](https://github.com/first) — docs — A docs fix.
- [second](https://github.com/second) — rules — A rule fix.

This paragraph follows the entries.
"""
    )

    rendered = module._cards_block(entries)

    assert rendered.index(">first</a>") < rendered.index(">second</a>")
    assert 'class="hall-card hall-card-featured"' in rendered
    assert rendered.count('class="hall-card"') == 1


def test_readme_callout_uses_every_contributor() -> None:
    module = _load_sync()
    entries = [
        module.Contributor(
            name="first",
            url="https://github.com/first",
            badge="docs",
            summary="A docs fix.",
        ),
        module.Contributor(
            name="second",
            url="https://github.com/second",
            badge="rules",
            summary="A rule fix.",
        ),
    ]

    rendered = module.render_readme(
        "<!-- BEGIN GENERATED CONTRIBUTOR CALLOUT -->old<!-- END GENERATED CONTRIBUTOR CALLOUT -->",
        entries,
    )

    assert "[first](https://github.com/first)" in rendered
    assert "[second](https://github.com/second)" in rendered
    assert "-->old<!--" not in rendered


def test_malformed_entry_fails_closed() -> None:
    module = _load_sync()

    with pytest.raises(ValueError, match="Every shipped contributor"):
        module._read_contributors(
            """# Contributors

## People who have shipped changes

- missing structured metadata
"""
        )


def test_contributor_without_a_profile_keeps_credit_and_drops_the_link() -> None:
    """A deleted GitHub account must not cost someone their credit or add a 404."""

    module = _load_sync()

    entries = module._read_contributors(
        """# Contributors

## People who have shipped changes

Each entry uses this format so the public contributor page can stay in sync:
`- [handle](https://github.com/handle) — short badge — contribution summary`.
If a contributor's GitHub account no longer exists, drop the link.

- [linked](https://github.com/linked) — docs — A documented change.
- gone — rules + tooling — Rules and tooling that made the project extensible.
"""
    )

    assert [(entry.name, entry.url) for entry in entries] == [
        ("linked", "https://github.com/linked"),
        ("gone", None),
    ]

    card = module._card(entries[1], 2, featured=False)
    assert "<h3>gone</h3>" in card
    assert "github.com/gone" not in card
    assert "View profile" not in card
    assert "Rules and tooling that made the project extensible." in card
    assert module.NO_PROFILE_NOTE in card

    callout = module._callout_block(entries)
    assert "[linked](https://github.com/linked)" in callout
    assert "· gone" in callout
    assert "[gone]" not in callout


def test_prose_around_the_list_is_not_mistaken_for_an_entry() -> None:
    module = _load_sync()

    entries = module._read_contributors(
        """# Contributors

## People who have shipped changes

Guidance prose sits above the list and must be skipped.

- [only](https://github.com/only) — docs — A documented change.

This is a thank-you list, not an authoritative contributor count.
"""
    )

    assert [entry.name for entry in entries] == ["only"]


def test_page_without_markers_fails_closed() -> None:
    module = _load_sync()
    entry = module.Contributor(
        name="person",
        url="https://github.com/person",
        badge="docs",
        summary="A useful change.",
    )

    with pytest.raises(ValueError, match="contributor page stats block"):
        module.render_page("<html></html>", [entry], 1)
