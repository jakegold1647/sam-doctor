"""Tests for the version-sync gate that guards every release.

release.yml runs this script with --check before building anything, and it had no
tests. Its whole mechanism is regex substitution, which fails in the one direction
nobody notices: a pattern that stops matching rewrites nothing, the text compares
equal to itself, and --check prints "metadata is in sync". Three README anchors had
been dead since the README was rewritten, and the release gate never said a word.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

INDEX = """<!doctype html>
<html><head>
<script type="application/ld+json">{{"softwareVersion": "{software}"}}</script>
</head><body>
<h2 id="install-title">Install v{heading} in one command.</h2>
<a href="https://github.com/jakegold1647/sam-doctor/releases/tag/v{link}">
View v{label} release notes</a>
</body></html>
"""


def _load_sync():
    spec = importlib.util.spec_from_file_location(
        "sync_site_metadata", str(REPO_ROOT / "scripts" / "sync-site-metadata.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load sync-site-metadata.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The script pointed at a throwaway pyproject and index page."""

    module = _load_sync()
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "sam-doctor"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    monkeypatch.setattr(module, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(module, "INDEX_PATH", tmp_path / "index.html")
    return module


def _write_index(sync, **versions: str) -> None:
    fields = {"software": "1.2.3", "heading": "1.2.3", "link": "1.2.3", "label": "1.2.3"}
    fields.update(versions)
    sync.INDEX_PATH.write_text(INDEX.format(**fields), encoding="utf-8")


def test_an_aligned_page_is_in_sync(sync) -> None:
    _write_index(sync)

    changes, version, missing = sync.sync_metadata(write=False)

    assert (changes, version, missing) == (0, "1.2.3", [])


@pytest.mark.parametrize("field", ["software", "heading", "link", "label"])
def test_each_stale_version_is_detected(sync, field: str) -> None:
    _write_index(sync, **{field: "0.8.1"})

    changes, _, missing = sync.sync_metadata(write=False)

    assert changes == 1, f"a stale {field} version was not noticed"
    assert missing == []


def test_a_reworded_anchor_is_reported_rather_than_passing_silently(sync) -> None:
    # The defect this file exists for. The heading says 0.8.1 and the package is
    # 1.2.3, but the wording changed, so the substitution matches nothing - and
    # before this check that counted as "in sync".
    _write_index(sync)
    sync.INDEX_PATH.write_text(
        sync.INDEX_PATH.read_text(encoding="utf-8").replace(
            '<h2 id="install-title">Install v1.2.3 in one command.</h2>',
            '<h2 id="install-title">Get started with v0.8.1 today.</h2>',
        ),
        encoding="utf-8",
    )

    changes, _, missing = sync.sync_metadata(write=False)

    assert changes == 0, "the reworded heading cannot be rewritten, by definition"
    assert missing == ["site/index.html: install heading"], (
        "a dead anchor has to be reported, or the stale version ships silently"
    )


def test_a_dead_anchor_fails_check_mode(sync, monkeypatch) -> None:
    _write_index(sync)
    sync.INDEX_PATH.write_text(
        sync.INDEX_PATH.read_text(encoding="utf-8").replace("softwareVersion", "swVersion"),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["sync-site-metadata.py", "--check"])

    assert sync.main() == 1


def test_a_dead_anchor_also_fails_write_mode(sync, monkeypatch) -> None:
    # Write mode is where a release actually updates the page. Passing there
    # leaves that one spot on the old version with nothing to catch it later.
    _write_index(sync)
    sync.INDEX_PATH.write_text(
        sync.INDEX_PATH.read_text(encoding="utf-8").replace("release notes", "changelog"),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["sync-site-metadata.py"])

    assert sync.main() == 1


def test_writing_makes_the_page_agree_and_is_idempotent(sync, monkeypatch) -> None:
    _write_index(sync, heading="0.8.1", link="0.8.1")
    monkeypatch.setattr(sys, "argv", ["sync-site-metadata.py"])

    assert sync.main() == 0
    text = sync.INDEX_PATH.read_text(encoding="utf-8")
    assert "Install v1.2.3 in one command." in text
    assert "releases/tag/v1.2.3" in text
    assert "0.8.1" not in text

    # A second run must be a no-op, or --check would fail right after a sync.
    changes, _, missing = sync.sync_metadata(write=False)
    assert (changes, missing) == (0, [])


def test_check_mode_does_not_touch_the_file(sync, monkeypatch) -> None:
    _write_index(sync, heading="0.8.1")
    before = sync.INDEX_PATH.read_text(encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["sync-site-metadata.py", "--check"])

    assert sync.main() == 1
    assert sync.INDEX_PATH.read_text(encoding="utf-8") == before


def test_a_missing_version_in_pyproject_is_an_error(sync) -> None:
    sync.PYPROJECT_PATH.write_text('[project]\nname = "sam-doctor"\n', encoding="utf-8")
    _write_index(sync)

    with pytest.raises(RuntimeError, match="project.version"):
        sync.sync_metadata(write=False)


def test_the_real_repository_is_in_sync() -> None:
    # Guards the anchors themselves: if a site edit reworders one, this fails in
    # the pull request instead of at release time.
    module = _load_sync()
    changes, _, missing = module.sync_metadata(write=False)
    assert missing == [], f"dead version anchors: {missing}"
    assert changes == 0, "site/index.html disagrees with pyproject version"
