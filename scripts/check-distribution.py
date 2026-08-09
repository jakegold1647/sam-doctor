#!/usr/bin/env python3
"""Collect public launch signals for SAM Doctor.

This script keeps the launch loop human and ethical by reporting distribution
signals without guessing popularity from private or manipulated data.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

GITHUB_REPO = "jakegold1647/sam-doctor"
PYPI_PROJECT = "sam-doctor"
MARKETPLACE_URL = (
    "https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics"
)
SITE_URL = "https://sam-doctor.jacobgoldstein.dev/"
EXPECTED_TOPICS = {
    "aws",
    "aws-sam",
    "cloudformation",
    "github-actions",
    "iam",
    "cli",
    "python",
    "serverless",
}
EXPECTED_HOMEPAGE = SITE_URL


@dataclass
class Status:
    name: str
    ok: bool
    details: str


def _get_json(url: str, token: str | None) -> tuple[Any, int]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sam-doctor-launch-check",
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8")), response.status
    except urllib.error.HTTPError as exc:  # pragma: no cover - network dependent
        raise RuntimeError(f"{exc.code} {exc.reason} @ {url}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network dependent
        raise RuntimeError(f"Network error @ {url}: {exc}") from exc


def _check_http_status(url: str) -> Status:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, method="HEAD"), timeout=20
        ) as response:
            return Status(url, response.status == 200, str(response.status))
    except urllib.error.HTTPError as exc:
        return Status(url, False, f"{exc.code} {exc.reason}")
    except urllib.error.URLError as exc:
        return Status(url, False, f"error: {exc.reason}")


def _marketplace_pre_release_status(url: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "sam-doctor-launch-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            has_pre_release_marker = "Latest pre-release" in body
            return {
                "ok": response.status == 200,
                "details": str(response.status),
                "pre_release_listed": has_pre_release_marker,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "details": f"{exc.code} {exc.reason}",
            "pre_release_listed": False,
        }
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "details": f"error: {exc.reason}",
            "pre_release_listed": False,
        }


def _normalize_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item.strip().lower() for item in value if isinstance(item, str) and item.strip()]


def _normalize_url(value: object) -> str:
    return str(value or "").strip().rstrip("/")


def _evaluate_launch_readiness(repo_data: dict[str, object]) -> dict[str, object]:
    homepage = _normalize_url(repo_data.get("homepage"))
    topics = _normalize_list(repo_data.get("topics"))
    topics_set = set(topics)
    required = set(EXPECTED_TOPICS)
    missing_topics = sorted(required - topics_set)

    return {
        "homepage_ok": bool(homepage and _normalize_url(homepage) == _normalize_url(EXPECTED_HOMEPAGE)),
        "homepage": homepage,
        "topics_ok": len(missing_topics) == 0,
        "topics_count": len(topics_set),
        "missing_topics": missing_topics,
    }


def _count_discussions(repo: str, token: str | None) -> int:
    # Discussions is not always visible without auth; return 0 if it fails.
    url = f"https://api.github.com/repos/{repo}/discussions?per_page=1"
    try:
        payload, _ = _get_json(url, token)
    except RuntimeError as error:
        print(f"# discussions unavailable: {error}", file=sys.stderr)
        return 0

    return len(payload) if isinstance(payload, list) else 0


def _list_release_count(repo: str, token: str | None) -> int:
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    try:
        payload, _ = _get_json(url, token)
    except RuntimeError as error:
        print(f"# releases unavailable: {error}", file=sys.stderr)
        return 0

    return len(payload) if isinstance(payload, list) else 0


def _collect_snapshot(repo: str, token: str | None) -> dict[str, object]:
    repo_url = f"https://api.github.com/repos/{repo}"
    data, _ = _get_json(repo_url, token)
    launch_readiness = _evaluate_launch_readiness(data)

    release_count = _list_release_count(repo, token)
    discussions_ping = _count_discussions(repo, token)

    pypi_status = _check_http_status(f"https://pypi.org/pypi/{PYPI_PROJECT}/json")
    marketplace_status = _check_http_status(MARKETPLACE_URL)
    marketplace_listing = _marketplace_pre_release_status(MARKETPLACE_URL)
    site_status = _check_http_status(SITE_URL)

    return {
        "repo": repo,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_stars": data.get("stargazers_count", "unknown"),
        "forks": data.get("forks_count", "unknown"),
        "open_issues": data.get("open_issues_count", "unknown"),
        "watchers": data.get("subscribers_count", "unknown"),
        "releases": release_count,
        "discussions_ping": discussions_ping,
        "pypi_status": {"ok": pypi_status.ok, "details": pypi_status.details},
        "marketplace_status": {
            "ok": marketplace_status.ok,
            "details": marketplace_status.details,
            "pre_release_listed": marketplace_listing["pre_release_listed"],
            "listing_status": marketplace_listing["details"],
        },
        "site_status": {"ok": site_status.ok, "details": site_status.details},
        "launch_readiness": launch_readiness,
    }


def _append_csv(snapshot: dict[str, object], csv_path: str) -> None:
    _ensure_parent_directory(csv_path)

    header = [
        "timestamp",
        "repo",
        "repo_stars",
        "forks",
        "open_issues",
        "watchers",
        "releases",
        "discussions_ping",
        "pypi_ok",
        "marketplace_ok",
        "marketplace_pre_release",
        "site_ok",
        "homepage_ok",
        "topics_ok",
        "topics_count",
    ]
    is_new = not os.path.exists(csv_path)

    with open(csv_path, "a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": snapshot["timestamp"],
                "repo": snapshot["repo"],
                "repo_stars": snapshot["repo_stars"],
                "forks": snapshot["forks"],
                "open_issues": snapshot["open_issues"],
                "watchers": snapshot["watchers"],
                "releases": snapshot["releases"],
                "discussions_ping": snapshot["discussions_ping"],
                "pypi_ok": snapshot["pypi_status"]["ok"]
                if isinstance(snapshot["pypi_status"], dict)
                else "",
                "marketplace_ok": snapshot["marketplace_status"]["ok"]
                if isinstance(snapshot["marketplace_status"], dict)
                else "",
                "marketplace_pre_release": snapshot["marketplace_status"].get(
                    "pre_release_listed", ""
                )
                if isinstance(snapshot["marketplace_status"], dict)
                else "",
                "site_ok": snapshot["site_status"]["ok"]
                if isinstance(snapshot["site_status"], dict)
                else "",
                "homepage_ok": snapshot.get("launch_readiness", {}).get("homepage_ok", ""),
                "topics_ok": snapshot.get("launch_readiness", {}).get("topics_ok", ""),
                "topics_count": snapshot.get("launch_readiness", {}).get("topics_count", ""),
            }
        )


def _read_last_csv_row(csv_path: str) -> dict[str, str] | None:
    if not os.path.exists(csv_path):
        return None

    with open(csv_path, "r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return None
    return rows[-1]


def _ensure_parent_directory(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _strict_distribution_violations(snapshot: dict[str, object]) -> list[str]:
    """Return high-signal launch violations for pre-publish validation."""

    violations: list[str] = []
    pypi_status = snapshot.get("pypi_status")
    marketplace_status = snapshot.get("marketplace_status")
    site_status = snapshot.get("site_status")
    launch_readiness = snapshot.get("launch_readiness", {})

    if not isinstance(pypi_status, dict) or not pypi_status.get("ok", False):
        violations.append("PyPI download channel is not reachable")
    if not isinstance(marketplace_status, dict) or not marketplace_status.get("ok", False):
        violations.append("GitHub Marketplace listing is not reachable")
    if not isinstance(site_status, dict) or not site_status.get("ok", False):
        violations.append("Project website is not reachable")
    if not isinstance(launch_readiness, dict) or not launch_readiness.get("homepage_ok", False):
        violations.append("Repository homepage is missing or not set to the public site URL")
    if not isinstance(launch_readiness, dict) or not launch_readiness.get("topics_ok", False):
        missing_topics = launch_readiness.get("missing_topics")
        topics_text = (
            ", ".join(missing_topics)
            if isinstance(missing_topics, list) and missing_topics
            else "topics not configured as expected"
        )
        violations.append(f"Required repository topics are missing: {topics_text}")

    if isinstance(marketplace_status, dict) and marketplace_status.get("pre_release_listed"):
        violations.append("Marketplace listing is still marked as latest pre-release")

    return violations


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _delta(snapshot_value: object, previous: dict[str, str] | None, key: str) -> int:
    previous_value = 0 if previous is None else _to_int(previous.get(key, "0"))
    return _to_int(snapshot_value) - previous_value


def _trend_text(
    snapshot: dict[str, object], previous: dict[str, str] | None
) -> str:
    if previous is None:
        return "baseline: no previous row for comparison"

    return (
        f"stars={_delta(snapshot['repo_stars'], previous, 'repo_stars'):+d}, "
        f"forks={_delta(snapshot['forks'], previous, 'forks'):+d}, "
        f"open_issues={_delta(snapshot['open_issues'], previous, 'open_issues'):+d}, "
        f"watchers={_delta(snapshot['watchers'], previous, 'watchers'):+d}, "
        f"releases={_delta(snapshot['releases'], previous, 'releases'):+d}"
    )


def _print_trend(snapshot: dict[str, object], previous: dict[str, str] | None) -> None:
    if previous is None:
        print("trend: no previous snapshot yet, establishing baseline")
        return

    print(f"trend: {_trend_text(snapshot, previous)}")


def _summary_lines(
    snapshot: dict[str, object], previous: dict[str, str] | None
) -> list[str]:
    pypi_status = snapshot["pypi_status"]
    marketplace_status = snapshot["marketplace_status"]
    site_status = snapshot["site_status"]
    launch_readiness = snapshot.get("launch_readiness", {})
    launch_readiness_summary = "launch-setup: off (unavailable)"

    pypi_up = "up" if isinstance(pypi_status, dict) and pypi_status["ok"] else "down"
    marketplace_up = (
        "up"
        if isinstance(marketplace_status, dict) and marketplace_status["ok"]
        else "down"
    )
    site_up = "up" if isinstance(site_status, dict) and site_status["ok"] else "down"

    trend_text = (
        f"delta {_trend_text(snapshot, previous)}"
        if previous
        else "baseline: no previous row for comparison"
    )
    missing_topics = []
    launch_ok = "off"
    if isinstance(launch_readiness, dict):
        missing_topics = launch_readiness.get("missing_topics")
        if launch_readiness.get("homepage_ok") and launch_readiness.get("topics_ok"):
            launch_ok = "ready"
        elif launch_readiness.get("homepage_ok") or launch_readiness.get("topics_ok"):
            launch_ok = "partial"
        details = ", ".join(missing_topics) if isinstance(missing_topics, list) else "unavailable"
        launch_readiness_summary = f"launch-setup: {launch_ok} ({details})"

    channel_health = []
    if pypi_up == "up":
        channel_health.append("PyPI: up")
    if marketplace_up == "up":
        channel_health.append("Marketplace: up")
    if site_up == "up":
        channel_health.append("Site: up")
    if not channel_health:
        channel_health.append("channels: investigate")

    star_signal = (
        "no stars yet; prioritize conversation-first outreach"
        if snapshot["repo_stars"] == 0
        else "has organic follow-through signal"
    )

    return [
        "# SAM Doctor launch status",
        f"- timestamp: {snapshot['timestamp']}",
        f"- repository: {snapshot['repo']}",
        f"- repo_stars: {snapshot['repo_stars']}",
        f"- forks: {snapshot['forks']}",
        f"- open_issues: {snapshot['open_issues']}",
        f"- watchers: {snapshot['watchers']}",
        f"- releases: {snapshot['releases']}",
        f"- discussions_ping: {snapshot['discussions_ping']}",
        f"- {launch_readiness_summary}",
        f"- channel_health: {', '.join(channel_health)}",
        f"- launch_setup_homepage_ok: {launch_readiness.get('homepage_ok', 'unavailable')}",
        f"- launch_setup_topics_ok: {launch_readiness.get('topics_ok', 'unavailable')}",
        f"- launch_setup_topics_count: {launch_readiness.get('topics_count', 'unavailable')}",
        f"- launch_setup_missing_topics: {', '.join(launch_readiness.get('missing_topics', ['unavailable']))}",
        f"- marketplace_pre_release_listed: {marketplace_status.get('pre_release_listed', 'unavailable')}",
        f"- trend_vs_previous: {trend_text}",
        f"- signal: {star_signal}",
    ]


def _write_summary(
    snapshot: dict[str, object],
    previous: dict[str, str] | None,
    summary_path: str,
) -> None:
    with open(summary_path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(_summary_lines(snapshot, previous)) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo",
        default=GITHUB_REPO,
        help="GitHub repository owner/name",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="Optional GitHub API token",
    )
    parser.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output file path for JSON snapshots",
    )
    parser.add_argument(
        "--append-csv",
        default="",
        help="Append machine-readable snapshot rows to a CSV file",
    )
    parser.add_argument(
        "--print-trend",
        action="store_true",
        help="Print trend deltas from the most recent CSV snapshot",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Write launch summary markdown to this file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when launch-critical signals indicate pre-publish issues",
    )
    args = parser.parse_args()

    repo = args.repo
    token = args.token or None
    try:
        snapshot = _collect_snapshot(repo, token)
    except RuntimeError as error:
        print(f"Unable to read repo metadata: {error}")
        return 1

    should_read_previous = args.print_trend or bool(args.summary)
    previous_row = (
        _read_last_csv_row(args.append_csv)
        if should_read_previous and args.append_csv
        else None
    )
    if args.output_format == "json":
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        if args.output:
            _ensure_parent_directory(args.output)
            with open(args.output, "w", encoding="utf-8") as stream:
                json.dump(snapshot, stream, indent=2, sort_keys=True)
        if args.summary:
            _ensure_parent_directory(args.summary)
            _write_summary(snapshot, previous_row, args.summary)
    if args.append_csv:
        _append_csv(snapshot, args.append_csv)
    if args.print_trend:
        _print_trend(snapshot, previous_row)
    if args.strict:
        violations = _strict_distribution_violations(snapshot)
        if violations:
            print("strict launch health: FAIL")
            for violation in violations:
                print(f"- {violation}")
            return 1
    if args.output_format == "json":
        return 0

    print(f"sam-doctor distribution snapshot for {repo}")
    print(f"repo_stars: {snapshot['repo_stars']}")
    print(f"forks: {snapshot['forks']}")
    print(f"open_issues: {snapshot['open_issues']}")
    print(f"watchers: {snapshot['watchers']}")
    print(f"releases: {snapshot['releases']}")
    print(f"discussions_ping: {snapshot['discussions_ping']}")
    pypi_status = snapshot["pypi_status"]
    marketplace_status = snapshot["marketplace_status"]
    site_status = snapshot["site_status"]
    launch_readiness = snapshot.get("launch_readiness", {})
    print(
        f"pypi_status: 200={pypi_status['ok']} ({pypi_status['details']})"
    )
    print(
        "marketplace_status: 200="
        f"{marketplace_status['ok']} ({marketplace_status['details']})"
    )
    print(f"site_status: 200={site_status['ok']} ({site_status['details']})")
    marketplace_pre_release = marketplace_status.get("pre_release_listed", False)
    print(f"marketplace_pre_release_listed: {marketplace_pre_release}")
    print(f"homepage_ok: {launch_readiness.get('homepage_ok', 'unavailable')}")
    print(f"topics_ok: {launch_readiness.get('topics_ok', 'unavailable')}")
    print(f"topics_count: {launch_readiness.get('topics_count', 'unavailable')}")
    print(
        f"missing_topics: {', '.join(launch_readiness.get('missing_topics', ['unavailable']))}"
    )

    if marketplace_status["ok"] and pypi_status["ok"] and site_status["ok"]:
        print(
            "channels: marketplace, pypi, pages, and github release metadata are visible"
        )

    if snapshot["repo_stars"] == 0:
        print("signal: no stars yet, keep outreach conversation-first")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
