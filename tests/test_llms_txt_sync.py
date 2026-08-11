"""Tests for the gate that keeps llms.txt labels matching their error pages.

llms.txt exists so assistants describe SAM Doctor accurately, which makes a
silently stale label worse than a broken one: nothing renders wrong, and the
wrong name propagates. A title pass across the error pages left 37 of 47 labels
describing headings no longer on the page, and no gate noticed.

The failure mode worth testing is the quiet one, the same as the metadata sync:
a substitution that stops matching rewrites nothing, the text compares equal to
itself, and --check reports success while seeing nothing at all.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

PAGE = """<!doctype html>
<html><head><title>{heading} | SAM Doctor</title></head>
<body><main><h1>{heading}</h1></main></body></html>
"""


def _load_sync():
    spec = importlib.util.spec_from_file_location(
        "sync_llms_txt", str(REPO_ROOT / "scripts" / "sync-llms-txt.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load sync-llms-txt.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The script pointed at a throwaway site tree."""

    module = _load_sync()
    site_root = tmp_path / "site"
    errors_root = site_root / "errors"
    errors_root.mkdir(parents=True)
    monkeypatch.setattr(module, "SITE_ROOT", site_root)
    monkeypatch.setattr(module, "ERRORS_ROOT", errors_root)
    monkeypatch.setattr(module, "LLMS_PATH", site_root / "llms.txt")
    return module


def _write(module, entries: list[tuple[str, str]], headings: dict[str, str]) -> None:
    lines = ["# SAM Doctor", "", "## Exact-error guides", ""]
    for slug, label in entries:
        lines.append(
            f"- [{label}]({module.SITE_ORIGIN}/errors/{slug}): a hand-written note."
        )
    module.LLMS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for slug, heading in headings.items():
        (module.ERRORS_ROOT / slug).write_text(
            PAGE.format(heading=heading), encoding="utf-8"
        )


def test_drifted_label_is_rewritten_to_the_page_heading(sync) -> None:
    _write(
        sync,
        [("expired-token.html", "The old descriptive label")],
        {"expired-token.html": "The security token included in the request is expired"},
    )

    drifted, seen = sync.sync_llms_txt(write=True)

    assert seen == 1
    assert drifted == [
        (
            "expired-token.html",
            "The old descriptive label",
            "The security token included in the request is expired",
        )
    ]
    updated = sync.LLMS_PATH.read_text(encoding="utf-8")
    assert (
        "- [The security token included in the request is expired]"
        f"({sync.SITE_ORIGIN}/errors/expired-token.html): a hand-written note."
    ) in updated


def test_check_mode_reports_drift_without_writing(sync) -> None:
    _write(
        sync,
        [("expired-token.html", "Stale")],
        {"expired-token.html": "Fresh heading"},
    )
    before = sync.LLMS_PATH.read_text(encoding="utf-8")

    drifted, _ = sync.sync_llms_txt(write=False)

    assert drifted
    assert sync.LLMS_PATH.read_text(encoding="utf-8") == before


def test_sync_is_idempotent_and_round_trips_bracketed_headings(sync) -> None:
    """Brackets in a heading must survive, or the next run reports false drift."""

    heading = "Requires capabilities : [CAPABILITY_IAM] (InsufficientCapabilities)"
    _write(
        sync,
        [("insufficient-capabilities.html", "Old")],
        {"insufficient-capabilities.html": heading},
    )

    sync.sync_llms_txt(write=True)
    first = sync.LLMS_PATH.read_text(encoding="utf-8")
    assert chr(92) + "[CAPABILITY_IAM" + chr(92) + "]" in first

    drifted, seen = sync.sync_llms_txt(write=True)

    assert seen == 1
    assert drifted == []
    assert sync.LLMS_PATH.read_text(encoding="utf-8") == first


def test_hand_written_description_and_url_are_preserved(sync) -> None:
    _write(
        sync,
        [("expired-token.html", "Old")],
        {"expired-token.html": "New"},
    )

    sync.sync_llms_txt(write=True)

    updated = sync.LLMS_PATH.read_text(encoding="utf-8")
    assert f"({sync.SITE_ORIGIN}/errors/expired-token.html): a hand-written note." in updated


def test_missing_page_fails_instead_of_passing_blind(sync) -> None:
    _write(sync, [("gone.html", "Label")], {})

    with pytest.raises(ValueError, match="gone.html"):
        sync.sync_llms_txt(write=False)


def test_page_without_a_heading_fails(sync) -> None:
    _write(sync, [("empty.html", "Label")], {})
    (sync.ERRORS_ROOT / "empty.html").write_text(
        "<!doctype html><html><body><p>no heading</p></body></html>", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="no usable <h1>"):
        sync.sync_llms_txt(write=False)


def test_matching_nothing_is_reported_as_a_failure(sync, monkeypatch, capsys) -> None:
    """A link-shape change must fail the gate rather than silently pass."""

    _write(sync, [], {})
    monkeypatch.setattr(sys, "argv", ["sync-llms-txt.py", "--check"])

    assert sync.main() == 1
    assert "no error-guide links found" in capsys.readouterr().out


def test_real_site_llms_txt_is_in_sync() -> None:
    """The shipped file must stay aligned; this is the gate CI runs."""

    module = _load_sync()
    drifted, seen = module.sync_llms_txt(write=False)

    assert seen > 0
    assert drifted == []
