#!/usr/bin/env python3
"""Summarize launch outreach logs with a minimal ethical-growth signal.

The summary is intentionally lightweight: it reports what happened and does not
store customer logs or sensitive details.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _sorted_counts(values: Mapping[str, int]) -> list[tuple[str, int]]:
    return sorted(values.items(), key=lambda item: (-item[1], item[0]))


def _count(values: Iterable[str]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for value in values:
        normalized = (value or "").strip()
        if normalized:
            counter[normalized] += 1
    return counter


def summarize(path: Path) -> dict[str, object]:
    rows = _read_rows(path)
    if not rows:
        return {
            "rows": 0,
            "voluntary_stars": 0,
            "positive_outcome_count": 0,
            "repeat_contacts": 0,
            "top_channels": [],
            "top_outcomes": [],
        }

    voluntary_stars = sum(_to_bool(row.get("voluntary_star", "")) for row in rows)
    repeat_contacts = sum(_to_bool(row.get("repeat_contact", "")) for row in rows)
    positive_signals = sum(
        1 for row in rows if "asked" in (row.get("feedback_signal", "") or "").lower()
    )
    contact_channels = _count((row.get("contact_channel", "") for row in rows))
    outcomes = _count((row.get("outcome", "") for row in rows))

    return {
        "rows": len(rows),
        "voluntary_stars": voluntary_stars,
        "positive_outcome_count": positive_signals,
        "repeat_contacts": repeat_contacts,
        "top_channels": _sorted_counts(contact_channels)[:3],
        "top_outcomes": _sorted_counts(outcomes)[:3],
    }


def _print_summary(summary: dict[str, object]) -> None:
    print(f"outreach rows: {summary['rows']}")
    print(f"voluntary_stars: {summary['voluntary_stars']}")
    print(f"repeat_contacts: {summary['repeat_contacts']}")
    print(f"feedback_signals: {summary['positive_outcome_count']}")
    print(f"top_channels: {summary['top_channels']}")
    print(f"top_outcomes: {summary['top_outcomes']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="launch/outreach-log-template.csv",
        help="Path to the outreach CSV.",
    )
    args = parser.parse_args()

    csv_path = Path(args.path)
    if not csv_path.exists():
        print(f"outreach log not found: {csv_path}")
        return 1

    summary = summarize(csv_path)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
