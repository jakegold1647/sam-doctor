"""Tests for the website QA gate.

This script runs on every push and is the only thing standing between a broken
public page and the published site, and it had no tests. The gap it shipped with
is the one worth remembering: it checked that every sitemap entry pointed at a
real file, but never that every real page appeared in the sitemap - so the
sitemap fell 39 error pages behind without a single failure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "site"


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_site_qa", str(REPO_ROOT / "scripts" / "check-site-qa.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load check-site-qa.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def qa():
    return _load_checker()


PAGE = """<!doctype html>
<html><head>
<title>A title</title>
<meta name="description" content="A description">
<link rel="canonical" href="{canonical}">
</head><body>{body}</body></html>
"""


def _write_site(root: Path, *, body: str = "", extra_locs: tuple[str, ...] = ()) -> None:
    """A minimal site that passes every check, ready to be broken one way."""

    base = "https://jakegold1647.github.io/sam-doctor/"
    (root / "index.html").write_text(
        PAGE.format(canonical=base, body=body), encoding="utf-8"
    )
    locs = [base, *extra_locs]
    entries = "".join(f"  <url><loc>{loc}</loc></url>\n" for loc in locs)
    (root / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}</urlset>\n",
        encoding="utf-8",
    )
    (root / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8"
    )


def _issues(qa, root: Path) -> list[str]:
    issues: list[str] = []
    for html in sorted(root.rglob("*.html")):
        qa.check_html(root, html, issues)
    qa.check_sitemap(root, issues)
    qa.check_robots(root, issues)
    return issues


def test_the_real_site_passes(qa) -> None:
    # Guards the fix as much as the checker: if an error page lands without a
    # sitemap entry again, this fails in the PR that adds it.
    assert _issues(qa, SITE_ROOT) == []


def test_every_error_page_is_in_the_real_sitemap(qa) -> None:
    # Stated directly, because the generic message above is easy to misread as a
    # link problem. These pages exist to be found by search.
    sitemap = (SITE_ROOT / "sitemap.xml").read_text(encoding="utf-8")
    unlisted = [
        page.name
        for page in sorted(SITE_ROOT.glob("errors/*.html"))
        if page.name != "index.html" and page.name not in sitemap
    ]
    assert unlisted == [], f"error pages missing from sitemap.xml: {unlisted}"


def test_a_page_absent_from_the_sitemap_is_reported(qa, tmp_path: Path) -> None:
    _write_site(tmp_path)
    (tmp_path / "orphan.html").write_text(
        PAGE.format(canonical="https://example.com/orphan", body=""), encoding="utf-8"
    )

    problems = [p for p in _issues(qa, tmp_path) if "not listed in sitemap" in p]

    assert len(problems) == 1
    assert "orphan.html" in problems[0]
    # The message has to carry the line to paste, or the fix means hand-building a URL.
    assert "<url><loc>https://jakegold1647.github.io/sam-doctor/orphan.html" in problems[0]


def test_a_sitemap_entry_for_a_missing_file_is_reported(qa, tmp_path: Path) -> None:
    _write_site(
        tmp_path,
        extra_locs=("https://jakegold1647.github.io/sam-doctor/deleted.html",),
    )

    problems = [p for p in _issues(qa, tmp_path) if "missing local path" in p]

    assert len(problems) == 1
    assert "deleted.html" in problems[0]


def test_a_directory_url_satisfies_its_index_page(qa, tmp_path: Path) -> None:
    # `/errors/` in the sitemap is the entry for errors/index.html. Treating those
    # as different pages would report the whole error index as unlisted forever,
    # and a gate that cries wolf gets bypassed.
    base = "https://jakegold1647.github.io/sam-doctor/"
    _write_site(tmp_path, extra_locs=(f"{base}errors/",))
    (tmp_path / "errors").mkdir()
    (tmp_path / "errors" / "index.html").write_text(
        PAGE.format(canonical=f"{base}errors/", body=""), encoding="utf-8"
    )

    assert _issues(qa, tmp_path) == []


def test_a_broken_local_link_is_reported(qa, tmp_path: Path) -> None:
    _write_site(tmp_path, body='<a href="./nowhere.html">gone</a>')

    problems = [p for p in _issues(qa, tmp_path) if "broken local link" in p]

    assert len(problems) == 1


def test_a_working_local_link_is_not_reported(qa, tmp_path: Path) -> None:
    base = "https://jakegold1647.github.io/sam-doctor/"
    _write_site(
        tmp_path,
        body='<a href="./other.html#section">there</a>',
        extra_locs=(f"{base}other.html",),
    )
    (tmp_path / "other.html").write_text(
        PAGE.format(canonical=f"{base}other.html", body=""), encoding="utf-8"
    )

    assert _issues(qa, tmp_path) == []


def test_a_javascript_link_is_blocked(qa, tmp_path: Path) -> None:
    _write_site(tmp_path, body='<a href="javascript:alert(1)">x</a>')

    problems = [p for p in _issues(qa, tmp_path) if "javascript link blocked" in p]

    assert len(problems) == 1


def test_an_image_without_alt_text_is_reported(qa, tmp_path: Path) -> None:
    _write_site(tmp_path, body='<img src="x.png">')

    problems = [p for p in _issues(qa, tmp_path) if "missing alt" in p]

    assert len(problems) == 1


@pytest.mark.parametrize(
    ("removed", "expected"),
    [
        ("<title>A title</title>", "missing <title> tag"),
        ('<meta name="description" content="A description">', "missing description"),
        ('<link rel="canonical" href="{canonical}">', "missing canonical"),
    ],
)
def test_missing_head_metadata_is_reported(
    qa, tmp_path: Path, removed: str, expected: str
) -> None:
    _write_site(tmp_path)
    page = tmp_path / "index.html"
    base = "https://jakegold1647.github.io/sam-doctor/"
    page.write_text(
        page.read_text(encoding="utf-8").replace(removed.format(canonical=base), ""),
        encoding="utf-8",
    )

    problems = [p for p in _issues(qa, tmp_path) if expected in p]

    assert len(problems) == 1


def test_a_missing_sitemap_and_robots_are_reported(qa, tmp_path: Path) -> None:
    _write_site(tmp_path)
    (tmp_path / "sitemap.xml").unlink()
    (tmp_path / "robots.txt").unlink()

    problems = _issues(qa, tmp_path)

    assert "Missing sitemap.xml" in problems
    assert "Missing robots.txt" in problems


def test_robots_without_a_sitemap_directive_is_reported(qa, tmp_path: Path) -> None:
    _write_site(tmp_path)
    (tmp_path / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    assert "robots.txt missing Sitemap directive" in _issues(qa, tmp_path)


def test_the_exit_code_reflects_the_findings(qa, tmp_path: Path, monkeypatch) -> None:
    # CI reads the exit code, not the printed lines.
    _write_site(tmp_path)
    monkeypatch.setattr(sys, "argv", ["check-site-qa.py", str(tmp_path)])
    assert qa.main() == 0

    (tmp_path / "orphan.html").write_text(
        PAGE.format(canonical="https://example.com/o", body=""), encoding="utf-8"
    )
    assert qa.main() == 1


def test_a_sitemap_link_to_a_renamed_repository_file_is_reported(qa, tmp_path: Path) -> None:
    # Sitemap entries pointing at repository files were skipped entirely. They
    # break the same way a page link does - rename a doc and the sitemap
    # advertises a 404 to search engines with every gate green. Commit 1db8d9f,
    # "Point the sitemap at the renamed rollout and examples docs", is that
    # having already happened once and been caught by hand.
    site = tmp_path / "site"
    site.mkdir()
    _write_site(
        site,
        extra_locs=(
            "https://github.com/jakegold1647/sam-doctor/blob/main/docs/present.md",
            "https://github.com/jakegold1647/sam-doctor/blob/main/docs/renamed-away.md",
        ),
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "present.md").write_text("# present", encoding="utf-8")

    problems = [p for p in _issues(qa, site) if "repository file" in p]

    assert len(problems) == 1
    assert "docs/renamed-away.md" in problems[0]


def test_the_real_sitemaps_repository_links_all_resolve(qa) -> None:
    problems = [p for p in _issues(qa, SITE_ROOT) if "repository file" in p]

    assert problems == []


def test_a_page_linking_to_a_renamed_repository_file_is_reported(qa, tmp_path: Path) -> None:
    # Links into our own repository were classed as external and never checked,
    # yet they are as verifiable as a local link: the path after /blob/main/ is a
    # file in this checkout. Eleven site pages rely on that.
    site = tmp_path / "site"
    site.mkdir()
    base = "https://github.com/jakegold1647/sam-doctor/blob/main/"
    _write_site(
        site,
        body=(
            f'<a href="{base}docs/present.md">here</a>'
            f'<a href="{base}docs/renamed-away.md">gone</a>'
        ),
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "present.md").write_text("# present", encoding="utf-8")

    problems = [p for p in _issues(qa, site) if "links to a repository file" in p]

    assert len(problems) == 1
    assert "docs/renamed-away.md" in problems[0]


def test_a_repository_link_with_an_anchor_is_still_resolved(qa, tmp_path: Path) -> None:
    # A fragment is part of the URL, not the filename.
    site = tmp_path / "site"
    site.mkdir()
    base = "https://github.com/jakegold1647/sam-doctor/blob/main/"
    _write_site(site, body=f'<a href="{base}docs/present.md#a-heading">here</a>')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "present.md").write_text("# present", encoding="utf-8")

    assert [p for p in _issues(qa, site) if "repository file" in p] == []


def test_genuinely_external_links_are_left_unchecked(qa, tmp_path: Path) -> None:
    # Verifying those needs the network, which is what the weekly link check is
    # for; doing it here would make every contributor's gate depend on someone
    # else's website being up.
    site = tmp_path / "site"
    site.mkdir()
    _write_site(site, body='<a href="https://docs.aws.amazon.com/nope-not-real.html">docs</a>')

    assert _issues(qa, site) == []


def test_every_repository_link_on_the_real_site_resolves(qa) -> None:
    problems = [p for p in _issues(qa, SITE_ROOT) if "repository file" in p]

    assert problems == []
