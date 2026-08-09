"""Every tracked text file must actually be text.

Written because I put a NUL byte into `docs/rule-roadmap.md` and nothing noticed. It
survived ruff, the site QA gate, the link checks and the full test suite; the only
reason it surfaced at all was `grep` refusing to search the file and printing
"Binary file matches". A NUL or a broken encoding in a shipped file breaks rendering
on GitHub, breaks diffs, and makes tools quietly skip the file - the worst outcome
being that a *check* skips it.

The cause is worth naming because it will recur: the byte came from a shell heredoc
collapsing `\\x00` into a real escape on its way into Python. Anything that writes
files through a shell can do this, which is most automation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Extensions that must be text. Anything else tracked in this repository - the demo
# SVG aside, which is text anyway - is an image or an archive and is skipped.
TEXT_SUFFIXES = frozenset(
    {".py", ".md", ".yml", ".yaml", ".txt", ".html", ".css", ".json", ".toml", ".cfg", ".sh", ".xml", ".svg"}
)


def _tracked_text_files() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    return [
        REPO_ROOT / name
        for name in listing
        if Path(name).suffix.lower() in TEXT_SUFFIXES and (REPO_ROOT / name).is_file()
    ]


@pytest.fixture(scope="module")
def text_files() -> list[Path]:
    files = _tracked_text_files()
    # Guards the guard: a `git ls-files` that returns nothing would make every
    # assertion below trivially true.
    assert len(files) > 100, f"only {len(files)} text files found; the listing looks wrong"
    return files


def test_no_tracked_text_file_contains_a_nul_byte(text_files: list[Path]) -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in text_files
        if b"\x00" in path.read_bytes()
    ]

    assert offenders == [], f"NUL bytes in: {offenders}"


def test_every_tracked_text_file_decodes_as_utf8(text_files: list[Path]) -> None:
    offenders: list[str] = []
    for path in text_files:
        try:
            path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as error:
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {error}")

    assert offenders == [], "not valid UTF-8:\n  " + "\n  ".join(offenders)


def test_no_tracked_text_file_starts_with_a_byte_order_mark(text_files: list[Path]) -> None:
    # A BOM is legal UTF-8 and still breaks things: a shebang stops working, YAML
    # parsers reject the first key, and the CLI has its own BOM-stripping code for
    # *input* logs precisely because tools emit them by accident on Windows. None of
    # this repository's own files should carry one.
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in text_files
        if path.read_bytes().startswith(b"\xef\xbb\xbf")
    ]

    assert offenders == [], f"byte-order marks in: {offenders}"
