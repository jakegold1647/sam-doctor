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
    assert summary == "7 contributors, 90 diagnostics"


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
