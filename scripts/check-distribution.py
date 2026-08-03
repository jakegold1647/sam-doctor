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
from datetime import datetime, timezone
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Tuple


GITHUB_REPO = "jakegold1647/sam-doctor"
PYPI_PROJECT = "sam-doctor"
MARKETPLACE_URL = (
    "https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics"
)
SITE_URL = "https://jakegold1647.github.io/sam-doctor/"


@dataclass
class Status:
    name: str
    ok: bool
    details: str


def _get_json(url: str, token: str | None) -> Tuple[Any, int]:
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

    release_count = _list_release_count(repo, token)
    discussions_ping = _count_discussions(repo, token)

    pypi_status = _check_http_status(f"https://pypi.org/pypi/{PYPI_PROJECT}/json")
    marketplace_status = _check_http_status(MARKETPLACE_URL)
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
        },
        "site_status": {"ok": site_status.ok, "details": site_status.details},
    }


def _append_csv(snapshot: dict[str, object], csv_path: str) -> None:
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
        "site_ok",
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
                "pypi_ok": snapshot["pypi_status"]["ok"] if isinstance(snapshot["pypi_status"], dict) else "",
                "marketplace_ok": snapshot["marketplace_status"]["ok"] if isinstance(snapshot["marketplace_status"], dict) else "",
                "site_ok": snapshot["site_status"]["ok"] if isinstance(snapshot["site_status"], dict) else "",
            }
        )


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
    args = parser.parse_args()

    repo = args.repo
    token = args.token or None
    try:
        snapshot = _collect_snapshot(repo, token)
    except RuntimeError as error:
        print(f"Unable to read repo metadata: {error}")
        return 1

    if args.output_format == "json":
        print(json.dumps(snapshot, indent=2, sort_keys=True))
        if args.output:
            with open(args.output, "w", encoding="utf-8") as stream:
                json.dump(snapshot, stream, indent=2, sort_keys=True)
    if args.append_csv:
        _append_csv(snapshot, args.append_csv)
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
    print(
        f"pypi_status: 200={pypi_status['ok']} ({pypi_status['details']})"
    )
    print(
        "marketplace_status: 200="
        f"{marketplace_status['ok']} ({marketplace_status['details']})"
    )
    print(f"site_status: 200={site_status['ok']} ({site_status['details']})")

    if marketplace_status["ok"] and pypi_status["ok"]:
        print("channels: marketplace, pypi, pages, and github release metadata are visible")

    if snapshot["repo_stars"] == 0:
        print("signal: no stars yet, keep outreach conversation-first")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
