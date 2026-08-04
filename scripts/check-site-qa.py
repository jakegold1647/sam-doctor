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


class LinkCollector(HTMLParser):
    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source
        self.local_links: list[str] = []
        self.external_links: list[str] = []
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
            if value.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
                continue

            parsed = urllib.parse.urlparse(value)
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

    if collector.external_links:
        for bad in collector.external_links:
            if bad.lower().startswith("javascript:"):
                issues.append(f"{html_file}: javascript link blocked: {bad}")


def check_sitemap(site_root: Path, issues: list[str]) -> None:
    sitemap_path = site_root / "sitemap.xml"
    if not sitemap_path.exists():
        issues.append("Missing sitemap.xml")
        return

    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [elem.text for elem in root.findall(".//sm:loc", ns) if elem.text]
    for loc in locs:
        if not loc.startswith("https://jakegold1647.github.io/sam-doctor/"):
            continue
        rel = urllib.parse.urlparse(loc).path.lstrip("/")
        rel = rel.removeprefix("sam-doctor/")
        if not rel:
            rel = "index.html"
        candidate = site_root / rel
        if not candidate.exists():
            issues.append(f"sitemap.xml contains missing local path: {loc}")


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
