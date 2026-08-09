import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN_PATTERN = re.compile(r"--([a-z0-9-]+):\s*(#[0-9a-f]{6})", re.IGNORECASE)


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
