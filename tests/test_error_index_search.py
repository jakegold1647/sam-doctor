from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "site" / "errors" / "index.html"
SCRIPT_PATH = ROOT / "site" / "assets" / "error-index-filter.js"


def test_error_index_keeps_static_guides_and_exposes_accessible_search() -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")
    guide_links = re.findall(r'href="\./[^"/]+\.html"', index)

    assert len(guide_links) >= 90
    assert len(guide_links) == len(set(guide_links))
    assert 'role="search"' in index
    assert 'type="search"' in index
    assert 'role="status"' in index
    assert 'aria-live="polite"' in index
    assert 'id="error-guide-search-clear"' in index
    assert 'id="error-guide-search-empty"' in index
    assert 'src="../assets/error-index-filter.js"' in index


def test_error_index_filter_is_local_bookmarkable_and_keyboard_clearable() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "URLSearchParams" in script
    assert "history.replaceState" in script
    assert "row.hidden" in script
    assert "section.hidden" in script
    assert 'event.key === "Escape"' in script
    assert 'event.key === "Enter"' in script
    assert "focusFirstVisibleGuide" in script
    assert 'clearButton.addEventListener("click", clearSearch)' in script
    assert "fetch(" not in script
    assert "XMLHttpRequest" not in script
