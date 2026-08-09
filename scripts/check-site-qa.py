#!/usr/bin/env python3
"""Site QA checks for the published SAM Doctor website."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_ROOT = ROOT / "site"
SITE_BASE_URL = "https://jakegold1647.github.io/sam-doctor/"
REPO_BLOB_PREFIX = "/blob/main/"


class LinkCollector(HTMLParser):
    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source
        self.local_links: list[str] = []
        self.external_links: list[str] = []
        self.script_links: list[str] = []
        self.meta_has_title = False
        self.has_canonical = False
        self.has_description = False
        self._in_title = False
        self.missing_img_alt = 0
        self.title_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = {name.lower(): value for name, value in attrs if value is not None}

        if tag == "title":
            self._in_title = True

        if tag == "meta" and attrs.get("name", "").lower() == "description":
            self.has_description = True

        if tag == "link" and attrs.get("rel") == "canonical":
            self.has_canonical = True

        if tag == "img" and not attrs.get("alt"):
            self.missing_img_alt += 1

        for key in ("href", "src", "action"):
            value = attrs.get(key)
            if not value:
                continue
            if value.startswith("#"):
                continue

            parsed = urllib.parse.urlparse(value)
            # urlparse lowercases the scheme, so `JavaScript:` is caught too. This
            # used to be a startswith check that skipped javascript: links before
            # anything could object, which made the block further down dead code.
            if parsed.scheme == "javascript":
                self.script_links.append(value)
                continue
            if parsed.scheme in {"mailto", "tel", "data"}:
                continue

            if parsed.scheme in {"http", "https"}:
                self.external_links.append(value)
                continue

            # Ignore protocol-relative URLs.
            if value.startswith("//"):
                self.external_links.append(value)
                continue

            # Ignore explicit fragment links, handled above.
            self.local_links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data.strip()
            if self.title_text:
                self.meta_has_title = True


def collect_links(html_path: Path) -> LinkCollector:
    parser = LinkCollector(html_path)
    parser.feed(html_path.read_text(encoding="utf-8"))
    return parser


def check_html(site_root: Path, html_file: Path, issues: list[str]) -> None:
    if not html_file.is_file():
        issues.append(f"Missing HTML file: {html_file}")
        return

    collector = collect_links(html_file)
    if not collector.meta_has_title:
        issues.append(f"{html_file}: missing <title> tag")
    if not collector.has_description:
        issues.append(f"{html_file}: missing description meta tag")
    if not collector.has_canonical:
        issues.append(f"{html_file}: missing canonical link tag")
    if collector.missing_img_alt:
        issues.append(
            f"{html_file}: {collector.missing_img_alt} image(s) missing alt attribute"
        )

    for link in collector.local_links:
        clean = link.split("#", 1)[0]
        clean = clean.split("?", 1)[0]
        if not clean:
            continue
        candidate = (html_file.parent / clean).resolve()
        if clean.startswith("/"):
            candidate = (site_root / clean.lstrip("/")).resolve()

        if candidate.is_dir():
            candidate /= "index.html"
        elif candidate.suffix == "":
            # Keep backward-compatible support for links like `./foo` -> `foo.html`.
            maybe_html = candidate.with_suffix(".html")
            if maybe_html.exists():
                candidate = maybe_html

        if not candidate.exists():
            issues.append(f"{html_file}: broken local link '{link}' -> {candidate}")

    for bad in collector.script_links:
        issues.append(f"{html_file}: javascript link blocked: {bad}")

    # Links into our own repository are classed as external and so were never
    # checked, but they are as verifiable as a local link: the path after
    # /blob/main/ is a file in this checkout. Rename a doc and eleven pages point
    # at a 404 that no gate mentions. Genuinely external links stay unchecked -
    # that needs the network, which is what the weekly link check is for.
    for link in collector.external_links:
        if REPO_BLOB_PREFIX not in link:
            continue
        repo_relative = link.split(REPO_BLOB_PREFIX, 1)[1].split("#")[0].split("?")[0]
        if not (site_root.parent / repo_relative).is_file():
            issues.append(
                f"{html_file}: links to a repository file that does not exist: "
                f"{repo_relative} ({link})"
            )


def _sitemap_relative_path(loc: str) -> str:
    """Map a sitemap URL to the site-relative file it stands for."""

    rel = urllib.parse.urlparse(loc).path.lstrip("/")
    rel = rel.removeprefix("sam-doctor/")
    if not rel or rel.endswith("/"):
        # `/errors/` and `/` are served by the directory's index.html.
        rel = f"{rel}index.html"
    return rel


def check_sitemap(site_root: Path, issues: list[str]) -> None:
    sitemap_path = site_root / "sitemap.xml"
    if not sitemap_path.exists():
        issues.append("Missing sitemap.xml")
        return

    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [elem.text for elem in root.findall(".//sm:loc", ns) if elem.text]

    listed: set[str] = set()
    for loc in locs:
        if REPO_BLOB_PREFIX in loc:
            # Sitemap entries pointing at files in the repository rather than at
            # published pages. These were skipped entirely, and they break the same
            # way a page link does: rename a doc and the sitemap advertises a 404
            # to search engines with every gate still green. That is not
            # hypothetical here - commit 1db8d9f is "Point the sitemap at the
            # renamed rollout and examples docs", found and fixed by hand.
            repo_relative = loc.split(REPO_BLOB_PREFIX, 1)[1]
            if not (site_root.parent / repo_relative).is_file():
                issues.append(
                    f"sitemap.xml points at a repository file that does not exist: "
                    f"{repo_relative} ({loc})"
                )
            continue
        if not loc.startswith(SITE_BASE_URL):
            continue
        rel = _sitemap_relative_path(loc)
        listed.add(rel)
        if not (site_root / rel).exists():
            issues.append(f"sitemap.xml contains missing local path: {loc}")

    # The other direction, which is the one that rots. Adding an error page is a
    # per-rule chore and updating the sitemap is a separate edit, so the sitemap
    # silently stopped keeping up: four commits added pages without touching it,
    # leaving 38 pages that search engines had no path to. Nothing failed,
    # because nothing was looking this way.
    for html in sorted(site_root.rglob("*.html")):
        rel = html.relative_to(site_root).as_posix()
        if rel in listed:
            continue
        issues.append(
            f"{rel} exists but is not listed in sitemap.xml; add "
            f"<url><loc>{SITE_BASE_URL}{_sitemap_url_suffix(rel)}</loc></url> "
            "or the page will not be indexed"
        )


def _sitemap_url_suffix(rel: str) -> str:
    """The canonical URL suffix for a site-relative HTML path."""

    if rel == "index.html":
        return ""
    if rel.endswith("/index.html"):
        return rel.removesuffix("index.html")
    return rel


def check_robots(site_root: Path, issues: list[str]) -> None:
    robots = site_root / "robots.txt"
    if not robots.exists():
        issues.append("Missing robots.txt")
        return
    content = robots.read_text(encoding="utf-8").lower()
    if "sitemap:" not in content:
        issues.append("robots.txt missing Sitemap directive")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight website QA checks.")
    parser.add_argument(
        "site_root",
        nargs="?",
        default=str(DEFAULT_SITE_ROOT),
        help="Path to the website folder (default: ./site)",
    )
    args = parser.parse_args()

    site_root = Path(args.site_root).resolve()
    if not site_root.exists() or not site_root.is_dir():
        print(f"ERROR: site root not found: {site_root}", file=sys.stderr)
        return 1

    issues: list[str] = []
    for html in sorted(site_root.rglob("*.html")):
        check_html(site_root, html, issues)

    check_sitemap(site_root, issues)
    check_robots(site_root, issues)

    if issues:
        print("Site QA checks failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("Site QA checks passed:")
    print(f"- checked {len(list(site_root.rglob('*.html')))} HTML files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
