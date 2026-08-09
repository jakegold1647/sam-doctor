import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATTERN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-f]{6})", re.IGNORECASE)


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _css_block(source: str, marker: str) -> str:
    marker_start = source.index(marker)
    block_start = source.index("{", marker_start)
    depth = 1
    for index in range(block_start + 1, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[block_start + 1 : index]
    raise AssertionError(f"unclosed CSS block after {marker!r}")


class _BrandLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.accessible_names: list[str] = []
        self._aria_label = ""
        self._parts: list[str] = []
        self._child_hidden: list[bool] = []
        self._hidden_depth = 0
        self._in_brand = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if not self._in_brand:
            if tag != "a" or "brand" not in (attributes.get("class") or "").split():
                return
            self._in_brand = True
            self._aria_label = attributes.get("aria-label") or ""
            self._parts = []
            self._child_hidden = []
            self._hidden_depth = 0
            return

        hidden = "hidden" in attributes or (
            (attributes.get("aria-hidden") or "").lower() == "true"
        )
        self._child_hidden.append(hidden)
        if hidden:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if not self._in_brand:
            return
        if tag == "a" and not self._child_hidden:
            name = self._aria_label or "".join(self._parts)
            self.accessible_names.append(_normalize_whitespace(name))
            self._in_brand = False
            return
        hidden = self._child_hidden.pop()
        if hidden:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_brand and self._hidden_depth == 0:
            self._parts.append(data)


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_muted_copy_meets_normal_text_contrast_on_site_backgrounds() -> None:
    css = (ROOT / "site" / "styles.css").read_text(encoding="utf-8")
    tokens = dict(TOKEN_PATTERN.findall(css))

    for background_name in ("paper", "paper-deep"):
        ratio = _contrast_ratio(tokens["muted"], tokens[background_name])
        assert ratio >= 4.5, (
            f"--muted contrast on --{background_name} is {ratio:.2f}:1; "
            "normal text requires at least 4.5:1"
        )


def test_mobile_brand_links_keep_their_accessible_names() -> None:
    site_root = ROOT / "site"
    pages = sorted(site_root.rglob("*.html"))
    assert pages

    for page in pages:
        parser = _BrandLinkParser()
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
        assert parser.accessible_names, f"{page} has no brand link"
        assert all(parser.accessible_names), f"{page} has an unnamed brand link"

    css = (site_root / "styles.css").read_text(encoding="utf-8")
    mobile = _css_block(css, "@media (max-width: 470px)")
    brand_name = _css_block(mobile, ".brand-name")
    declarations = {
        name.strip(): value.strip()
        for declaration in brand_name.split(";")
        if ":" in declaration
        for name, value in [declaration.split(":", 1)]
    }

    assert declarations.get("display") != "none"
    assert declarations.get("visibility") != "hidden"
    expected = {
        "position": "absolute",
        "width": "1px",
        "height": "1px",
        "padding": "0",
        "margin": "-1px",
        "overflow": "hidden",
        "clip": "rect(0, 0, 0, 0)",
        "clip-path": "inset(50%)",
        "white-space": "nowrap",
        "border": "0",
    }
    assert declarations.items() >= expected.items()


def test_mobile_header_does_not_cover_anchor_targets() -> None:
    css = (ROOT / "site" / "styles.css").read_text(encoding="utf-8")
    mobile = _css_block(css, "@media (max-width: 700px)")
    topbar = _css_block(mobile, ".topbar")
    declarations = {
        name.strip(): value.strip()
        for declaration in topbar.split(";")
        if ":" in declaration
        for name, value in [declaration.split(":", 1)]
    }

    assert declarations.get("position") == "relative"
