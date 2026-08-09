"""Tests for the version-sync gate that guards every release.

release.yml runs this script with --check before building anything, and it had no
tests. Its whole mechanism is regex substitution, which fails in the one direction
nobody notices: a pattern that stops matching rewrites nothing, the text compares
equal to itself, and --check prints "metadata is in sync". Three README anchors had
been dead since the README was rewritten, and the release gate never said a word.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

INDEX = """<!doctype html>
<html><head>
<title>SAM Doctor</title>
<meta name="description" content="A local deployment diagnostic.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://sam-doctor.jacobgoldstein.dev/">
<meta property="og:site_name" content="SAM Doctor" />
<meta property="og:locale" content="en_US" />
<meta property="og:type" content="website" />
<meta property="og:title" content="SAM Doctor" />
<meta property="og:description" content="Turn AWS SAM, CloudFormation, IAM, and GitHub Actions deployment failures into a focused next check. SAM Doctor runs locally, cites the evidence it matched, and never needs AWS credentials." />
<meta property="og:url" content="https://sam-doctor.jacobgoldstein.dev/" />
<meta property="og:image" content="https://sam-doctor.jacobgoldstein.dev/assets/sam-doctor-social-preview.jpg" />
<meta property="og:image:type" content="image/jpeg" />
<meta property="og:image:width" content="1280" />
<meta property="og:image:height" content="640" />
<meta property="og:image:alt" content="SAM Doctor identifies the next useful check in a failed AWS deployment" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="SAM Doctor" />
<meta name="twitter:description" content="Turn AWS SAM, CloudFormation, IAM, and GitHub Actions deployment failures into a focused next check. SAM Doctor runs locally, cites the evidence it matched, and never needs AWS credentials." />
<meta name="twitter:image" content="https://sam-doctor.jacobgoldstein.dev/assets/sam-doctor-social-preview.jpg" />
<meta name="twitter:image:alt" content="SAM Doctor identifies the next useful check in a failed AWS deployment" />
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
    site_root = tmp_path / "site"
    site_root.mkdir()
    monkeypatch.setattr(module, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(module, "SITE_ROOT", site_root)
    monkeypatch.setattr(module, "INDEX_PATH", site_root / "index.html")
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


def test_write_mode_rejects_hard_linked_target_before_any_write(
    sync, tmp_path: Path
) -> None:
    _write_index(sync, heading="0.8.1")
    original = sync.INDEX_PATH.read_text(encoding="utf-8")
    victim = tmp_path / "victim.html"
    victim.write_text(original, encoding="utf-8")
    sync.INDEX_PATH.unlink()
    try:
        os.link(victim, sync.INDEX_PATH)
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")

    with pytest.raises(ValueError, match="must not be a hard link"):
        sync.sync_metadata(write=True)
    assert victim.read_text(encoding="utf-8") == original


def test_social_metadata_is_generated_from_the_page_and_is_idempotent(sync) -> None:
    _write_index(sync)
    error_dir = sync.SITE_ROOT / "errors"
    error_dir.mkdir()
    error_page = error_dir / "example.html"
    error_page.write_text(
        """<!doctype html>
<html><head>
<title>Exact failure &amp; recovery | SAM Doctor</title>
<meta name="description" content="Diagnose &quot;Exact failure&quot; safely.">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://sam-doctor.jacobgoldstein.dev/errors/example.html">
</head><body></body></html>
""",
        encoding="utf-8",
    )

    changes, _, missing = sync.sync_metadata(write=True)

    assert changes == 1
    assert missing == []
    text = error_page.read_text(encoding="utf-8")
    assert '<meta property="og:type" content="article" />' in text
    assert (
        '<meta property="og:title" '
        'content="Exact failure &amp; recovery | SAM Doctor" />'
    ) in text
    assert (
        '<meta property="og:description" '
        'content="Diagnose &quot;Exact failure&quot; safely." />'
    ) in text
    assert (
        '<meta property="og:url" '
        'content="https://sam-doctor.jacobgoldstein.dev/errors/example.html" />'
    ) in text
    assert '<meta name="twitter:card" content="summary_large_image" />' in text

    changes, _, missing = sync.sync_metadata(write=False)
    assert (changes, missing) == (0, [])


def test_social_sync_replaces_single_quoted_stale_tags(sync) -> None:
    _write_index(sync)
    page = sync.SITE_ROOT / "guide.html"
    page.write_text(
        """<!doctype html>
<html><head>
<title>Current guide | SAM Doctor</title>
<meta name="description" content="Current description.">
<meta name="robots" content="index, follow">
<link rel='canonical' href='https://sam-doctor.jacobgoldstein.dev/guide.html'>
<meta property='og:title' content='Stale title'>
<meta name='twitter:title' content='Stale title'>
</head><body></body></html>
""",
        encoding="utf-8",
    )

    changes, _, missing = sync.sync_metadata(write=True)

    assert (changes, missing) == (1, [])
    text = page.read_text(encoding="utf-8")
    assert "Stale title" not in text
    assert text.count('property="og:title"') == 1
    assert text.count('name="twitter:title"') == 1
    changes, _, missing = sync.sync_metadata(write=False)
    assert (changes, missing) == (0, [])


@pytest.mark.parametrize("robots", ("noindex, nofollow", "none"))
def test_nonindexable_page_is_left_out_of_social_metadata_sync(
    sync, robots: str
) -> None:
    _write_index(sync)
    draft = sync.SITE_ROOT / "draft.html"
    original = f"""<!doctype html>
<html><head>
<title>Draft</title>
<meta name="description" content="Not published.">
<meta name="robots" content="{robots}">
<link rel="canonical" href="https://sam-doctor.jacobgoldstein.dev/draft.html">
</head><body></body></html>
"""
    draft.write_text(original, encoding="utf-8")

    changes, _, missing = sync.sync_metadata(write=True)

    assert (changes, missing) == (0, [])
    assert draft.read_text(encoding="utf-8") == original


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
