"""Every tracked file with a shebang must carry the executable bit.

Ruff's EXE001 enforces this on Linux CI but silently passes on Windows
checkouts, so contributors on Windows cannot see the failure locally. This
test reads the git index mode instead of filesystem permissions, which works
identically on every platform.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_shebanged_files_are_executable_in_git() -> None:
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    missing_bit = []
    missing_shebang = []
    for line in listing.splitlines():
        meta, _, path = line.partition("\t")
        mode = meta.split()[0]
        if mode not in ("100644", "100755"):
            continue
        file_path = REPO_ROOT / path
        try:
            with open(file_path, "rb") as handle:
                starts_with_shebang = handle.read(2) == b"#!"
        except OSError:
            continue
        if mode == "100644" and starts_with_shebang:
            missing_bit.append(path)
        if mode == "100755" and not starts_with_shebang:
            missing_shebang.append(path)

    assert not missing_bit, (
        "Files with a shebang must be executable in the git index "
        f"(git update-index --chmod=+x <file>): {missing_bit}"
    )
    assert not missing_shebang, (
        f"Executable files must start with a shebang: {missing_shebang}"
    )


def test_new_scripts_are_flagged_before_they_are_committed() -> None:
    """Catch a missing executable bit locally instead of one commit later.

    The check above reads the git index, so a script that exists but has never
    been added is invisible to it: the suite passes, the commit lands, and CI
    fails on the very next push. Looking at untracked files under scripts/ too
    moves that failure to where the author can fix it before pushing.
    """

    untracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--others", "--exclude-standard", "scripts"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    unstaged_shebangs = []
    for path in untracked:
        try:
            with open(REPO_ROOT / path, "rb") as handle:
                if handle.read(2) == b"#!":
                    unstaged_shebangs.append(path)
        except OSError:
            continue

    assert not unstaged_shebangs, (
        "These scripts have a shebang but are not tracked yet. Add them and set "
        "the executable bit in the same step, or CI will fail on the next push: "
        f"git add <file> && git update-index --chmod=+x <file>: {unstaged_shebangs}"
    )
