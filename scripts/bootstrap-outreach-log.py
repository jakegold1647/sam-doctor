#!/usr/bin/env python3
"""Create a local outreach log file for launch tracking.

The log is intentionally kept outside Git history; this helper writes only the
CSV header for a new local tracker.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import sys


_OUTREACH_HEADER = (
    "week,date,contact_channel,problem_area,conversation_stage,next_action,"
    "voluntary_star,outcome,feedback_signal,repeat_contact\n"
)


def bootstrap_log(path: Path) -> tuple[bool, str]:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if not existing.strip():
            path.write_text(_OUTREACH_HEADER, encoding="utf-8")
            return True, f"Initialized empty outreach log: {path}"
        if existing.splitlines() and existing.splitlines()[0] == _OUTREACH_HEADER.rstrip("\n"):
            return False, f"Outreach log already initialized: {path}"
        return False, (
            "outreach log exists but does not match expected header; "
            "please create a separate local tracker file."
        )

    path.write_text(_OUTREACH_HEADER, encoding="utf-8")
    return True, f"Created outreach log: {path}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a local outreach log CSV.")
    parser.add_argument(
        "path",
        nargs="?",
        default="launch/outreach-log-template.csv",
        help="Path for the outreach tracker CSV.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args() if argv is None else _parse_args(argv)
    created, message = bootstrap_log(Path(args.path))
    print(message)
    return 0 if created or "already initialized" in message else 1


if __name__ == "__main__":
    raise SystemExit(main())
