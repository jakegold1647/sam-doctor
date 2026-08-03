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


_EMPTY_SUMMARY: dict[str, object] = {
    "rows": 0,
    "voluntary_stars": 0,
    "positive_outcome_count": 0,
    "repeat_contacts": 0,
    "stars_without_feedback": 0,
    "top_channels": [],
    "top_outcomes": [],
    "top_problem_areas": [],
    "top_stages": [],
    "ethical_signal": "no_data",
}


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


def _contains_feedback_signal(value: str) -> bool:
    text = (value or "").strip().lower()
    if not text:
        return False
    return any(
        marker in text
        for marker in (
            "follow",
            "asked",
            "accepted",
            "scheduled",
            "pending",
        )
    )


def _ensure_parent_directory(path: str) -> None:
    parent = str(Path(path).parent)
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def empty_summary() -> dict[str, object]:
    return dict(_EMPTY_SUMMARY)


def summarize(path: Path) -> dict[str, object]:
    rows = _read_rows(path)
    if not rows:
        return empty_summary()

    voluntary_stars = sum(_to_bool(row.get("voluntary_star", "")) for row in rows)
    repeat_contacts = sum(_to_bool(row.get("repeat_contact", "")) for row in rows)
    positive_signals = sum(
        1 for row in rows if "asked" in _normalize_text(row.get("feedback_signal", "")).lower()
    )
    stars_without_feedback = sum(
        1
        for row in rows
        if _to_bool(row.get("voluntary_star", ""))
        and not _contains_feedback_signal(row.get("feedback_signal", ""))
    )
    contact_channels = _count((row.get("contact_channel", "") for row in rows))
    outcomes = _count((row.get("outcome", "") for row in rows))
    problem_areas = _count((row.get("problem_area", "") for row in rows))
    stages = _count((row.get("conversation_stage", "") for row in rows))

    return {
        "rows": len(rows),
        "voluntary_stars": voluntary_stars,
        "positive_outcome_count": positive_signals,
        "repeat_contacts": repeat_contacts,
        "stars_without_feedback": stars_without_feedback,
        "ethical_signal": (
            "strong"
            if stars_without_feedback == 0 and voluntary_stars > 0
            else "mixed"
            if voluntary_stars > 0
            else "watch"
        ),
        "top_channels": _sorted_counts(contact_channels)[:3],
        "top_outcomes": _sorted_counts(outcomes)[:3],
        "top_problem_areas": _sorted_counts(problem_areas)[:3],
        "top_stages": _sorted_counts(stages)[:3],
    }


def _write_summary(summary: dict[str, object], path: str) -> None:
    _ensure_parent_directory(path)
    lines = [
        "# SAM Doctor ethical outreach status",
        f"- rows: {summary['rows']}",
        f"- voluntary_stars: {summary['voluntary_stars']}",
        f"- feedback_signals: {summary['positive_outcome_count']}",
        f"- repeat_contacts: {summary['repeat_contacts']}",
        f"- stars_without_feedback: {summary['stars_without_feedback']}",
        f"- ethical_signal: {summary['ethical_signal']}",
        f"- top_channels: {summary['top_channels']}",
        f"- top_outcomes: {summary['top_outcomes']}",
        f"- top_problem_areas: {summary['top_problem_areas']}",
        f"- top_stages: {summary['top_stages']}",
    ]
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


def _print_summary(summary: dict[str, object]) -> None:
    print(f"outreach rows: {summary['rows']}")
    print(f"voluntary_stars: {summary['voluntary_stars']}")
    print(f"repeat_contacts: {summary['repeat_contacts']}")
    print(f"feedback_signals: {summary['positive_outcome_count']}")
    print(f"stars_without_feedback: {summary['stars_without_feedback']}")
    print(f"ethical_signal: {summary['ethical_signal']}")
    print(f"top_channels: {summary['top_channels']}")
    print(f"top_outcomes: {summary['top_outcomes']}")
    print(f"top_problem_areas: {summary['top_problem_areas']}")
    print(f"top_stages: {summary['top_stages']}")


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
