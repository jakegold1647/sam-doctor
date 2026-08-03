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
from typing import Iterable, Mapping, Sequence, Tuple


_EMPTY_SUMMARY: dict[str, object] = {
    "rows": 0,
    "voluntary_stars": 0,
    "voluntary_stars_with_feedback": 0,
    "star_feedback_ratio": 0.0,
    "ethical_signal_strength": 0.0,
    "positive_outcome_count": 0,
    "repeat_contacts": 0,
    "stars_without_feedback": 0,
    "rows_with_feedback": 0,
    "top_channels": [],
    "top_outcomes": [],
    "top_problem_areas": [],
    "top_stages": [],
    "ethical_signal": "no_data",
}


_FEEDBACK_MARKERS = (
    "accepted",
    "follow",
    "asked",
    "pending",
    "scheduled",
    "interested",
    "opened",
    "reported",
    "used",
    "helpful",
)


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
    return any(marker in text for marker in _FEEDBACK_MARKERS)


def _ensure_parent_directory(path: str) -> None:
    parent = str(Path(path).parent)
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)


def _normalize_text(value: str) -> str:
    return (value or "").strip()


def _format_top_list(
    title: str, items: object
) -> list[str]:
    lines = [f"- {title}:"]
    if not isinstance(items, list):
        lines.append("  - unavailable")
        return lines

    pairs: Sequence[Tuple[str, object]] = items  # type: ignore[assignment]
    if not pairs:
        lines.append("  - none recorded")
        return lines

    for name, count in pairs:
        lines.append(f"  - {name}: {count}")
    return lines


def _ethical_recommendation(summary: dict[str, object]) -> str:
    ethical_signal = summary.get("ethical_signal")
    if ethical_signal == "strong":
        return "Keep the loop simple and scale with newer real-failure conversations."
    if ethical_signal == "mixed":
        return (
            "Follow up with stars that lacked feedback; one clear ask for a "
            "follow-up issue or note will improve trust signal."
        )
    return (
        "Prioritize conversation-first outreach. Run this again only after collecting "
        "at least one voluntary star with follow-up signal."
    )


def _next_growth_actions(summary: dict[str, object]) -> list[str]:
    ethical_signal = summary.get("ethical_signal")
    stars = int(summary.get("voluntary_stars", 0))
    stars_without_feedback = int(summary.get("stars_without_feedback", 0))
    repeat_contacts = int(summary.get("repeat_contacts", 0))
    ratio = float(summary.get("star_feedback_ratio", 0.0))
    rows = int(summary.get("rows", 0))

    actions = []

    if rows == 0:
        actions.append("Seed the outreach tracker with a single targeted manual conversation and capture the first source link.")
        actions.append("Prioritize one short conversation to recover baseline ethical signal.")
        return actions

    if ethical_signal == "watch":
        actions.append("Collect at least 1 voluntary star before any founder-outreach ask.")
        actions.append("Run one focused follow-up per non-voluntary contact and record outcomes.")
    elif ethical_signal == "mixed":
        if stars_without_feedback:
            actions.append(
                "Follow up with each volunteer whose feedback signal is missing before re-contacting them."
            )
        else:
            actions.append("Focus on moving mixed outcomes toward explicit follow-up signals (asked / pending / scheduled).")
    elif ethical_signal == "strong":
        actions.append("Keep sending updates to the same cohort and test one new channel per week (GitHub Issue, LinkedIn, or Slack).")

    if ratio < 100 and stars > 0:
        actions.append(
            "Add one consented follow-up prompt to every voluntary star contact until ratio reaches 100%."
        )

    if repeat_contacts == 0 and stars > 0:
        actions.append("Aim for one respectful repeat contact with an existing user who accepted follow-up.")

    if not actions:
        actions.append("Continue one conservative outreach thread at a time and review next results manually.")

    return actions[:3]


def _passes_strict_ethical_policy(summary: dict[str, object], min_feedback_ratio: float) -> tuple[bool, str]:
    if summary.get("ethical_signal") != "strong":
        return (
            False,
            f"ethical_signal is {summary['ethical_signal']}, not strong",
        )

    ratio = float(summary["star_feedback_ratio"])
    if ratio < min_feedback_ratio:
        return (
            False,
            (
                f"ethical star feedback ratio is {ratio:.1f}%, below strict threshold "
                f"{min_feedback_ratio:.1f}%"
            ),
        )
    return True, ""


def empty_summary() -> dict[str, object]:
    return dict(_EMPTY_SUMMARY)


def summarize(path: Path) -> dict[str, object]:
    rows = _read_rows(path)
    if not rows:
        return empty_summary()

    voluntary_stars = sum(_to_bool(row.get("voluntary_star", "")) for row in rows)
    voluntary_stars_with_feedback = sum(
        1
        for row in rows
        if _to_bool(row.get("voluntary_star", ""))
        and _contains_feedback_signal(row.get("feedback_signal", ""))
    )
    star_feedback_ratio = (
        (voluntary_stars_with_feedback / voluntary_stars * 100)
        if voluntary_stars
        else 0.0
    )
    repeat_contacts = sum(_to_bool(row.get("repeat_contact", "")) for row in rows)
    positive_signals = sum(
        1 for row in rows if _contains_feedback_signal(row.get("feedback_signal", ""))
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
        "voluntary_stars_with_feedback": voluntary_stars_with_feedback,
        "star_feedback_ratio": star_feedback_ratio,
        "ethical_signal_strength": min(100.0, star_feedback_ratio),
        "positive_outcome_count": positive_signals,
        "repeat_contacts": repeat_contacts,
        "stars_without_feedback": stars_without_feedback,
        "rows_with_feedback": sum(
            1 for row in rows if _contains_feedback_signal(row.get("feedback_signal", ""))
        ),
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
        f"- voluntary_stars_with_feedback: {summary['voluntary_stars_with_feedback']}",
        f"- star_feedback_ratio: {summary['star_feedback_ratio']:.1f}%",
        f"- ethical_signal_strength: {summary['ethical_signal_strength']:.1f}%",
        f"- feedback_signals: {summary['positive_outcome_count']}",
        f"- repeat_contacts: {summary['repeat_contacts']}",
        f"- stars_without_feedback: {summary['stars_without_feedback']}",
        f"- rows_with_feedback: {summary['rows_with_feedback']}",
        f"- ethical_signal: {summary['ethical_signal']}",
        f"- recommendation: {_ethical_recommendation(summary)}",
    ]
    lines.extend(_format_top_list("top_channels", summary.get("top_channels")))
    lines.extend(_format_top_list("top_outcomes", summary.get("top_outcomes")))
    lines.extend(_format_top_list("top_problem_areas", summary.get("top_problem_areas")))
    lines.extend(_format_top_list("top_stages", summary.get("top_stages")))
    lines.append("")
    lines.append("## next_growth_actions")
    for action in _next_growth_actions(summary):
        lines.append(f"- {action}")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


def _print_summary(summary: dict[str, object]) -> None:
    print(f"outreach rows: {summary['rows']}")
    print(f"voluntary_stars: {summary['voluntary_stars']}")
    print(
        f"voluntary_stars_with_feedback: {summary['voluntary_stars_with_feedback']}"
    )
    print(f"star_feedback_ratio: {summary['star_feedback_ratio']:.1f}%")
    print(f"ethical_signal_strength: {summary['ethical_signal_strength']:.1f}%")
    print(f"rows_with_feedback: {summary['rows_with_feedback']}")
    print(f"repeat_contacts: {summary['repeat_contacts']}")
    print(f"feedback_signals: {summary['positive_outcome_count']}")
    print(f"stars_without_feedback: {summary['stars_without_feedback']}")
    print(f"ethical_signal: {summary['ethical_signal']}")
    print(f"recommendation: {_ethical_recommendation(summary)}")
    print(f"top_channels: {summary['top_channels']}")
    print(f"top_outcomes: {summary['top_outcomes']}")
    print(f"top_problem_areas: {summary['top_problem_areas']}")
    print(f"top_stages: {summary['top_stages']}")
    print("next_growth_actions:")
    for action in _next_growth_actions(summary):
        print(f"- {action}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="launch/outreach-log-template.csv",
        help="Path to the outreach CSV.",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Write outreach summary file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if ethical signal is not strong.",
    )
    parser.add_argument(
        "--min-feedback-ratio",
        type=float,
        default=100.0,
        help="Strict ethical minimum for supportive follow-up ratio.",
    )
    args = parser.parse_args()

    csv_path = Path(args.path)
    if not csv_path.exists():
        print(f"outreach log not found: {csv_path}")
        return 1

    summary = summarize(csv_path)
    _print_summary(summary)
    if args.summary:
        _write_summary(summary, args.summary)
    if args.strict:
        passed, reason = _passes_strict_ethical_policy(summary, args.min_feedback_ratio)
        if not passed:
            print(reason)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
