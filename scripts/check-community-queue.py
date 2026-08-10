#!/usr/bin/env python3
"""Keep the public ready-issue queue actionable for newcomers.

This is a scheduled maintainer check, not part of the offline pull-request
gate. It reads the public GitHub issue queue and reports drift when a ready
issue loses its newcomer labels, is assigned without being re-triaged, or no
longer has enough context for a first contribution.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_REPOSITORY = "jakegold1647/sam-doctor"
READY_LABEL = "status: ready"
REQUIRED_LABELS = ("good first issue", "mentor available")
CLAIM_MARKERS = ("take this", "claim this", "claim it")
SCOPE_MARKERS = (
    "acceptance criteria",
    "proposed behavior",
    "where to add it",
    "suggested command output",
    "sample log excerpts to test against",
)
API_ROOT = "https://api.github.com"


def _get_json(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sam-doctor-community-queue-check",
        },
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:  # pragma: no cover - network dependent
        raise RuntimeError(f"GitHub API returned {error.code} {error.reason}") from error
    except urllib.error.URLError as error:  # pragma: no cover - network dependent
        raise RuntimeError(f"GitHub API request failed: {error.reason}") from error


def _paged_json(path: str, repository: str, token: str, **params: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    page = 1
    while True:
        query = {**params, "per_page": "100", "page": str(page)}
        url = f"{API_ROOT}/repos/{repository}/{path}?{urllib.parse.urlencode(query)}"
        payload = _get_json(url, token)
        if not isinstance(payload, list):
            raise TypeError(f"GitHub API returned a non-list for {path}")
        values.extend(item for item in payload if isinstance(item, dict))
        if len(payload) < 100:
            return values
        page += 1


def validate_ready_issue(issue: dict[str, Any], comments: list[dict[str, Any]]) -> list[str]:
    """Return actionable queue problems for one open ready issue."""

    labels = {
        str(label.get("name"))
        for label in issue.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    }
    problems: list[str] = []
    for required in REQUIRED_LABELS:
        if required not in labels:
            problems.append(f"missing `{required}` label")

    if issue.get("assignee") or issue.get("assignees"):
        problems.append("assigned work still carries `status: ready`")

    body = str(issue.get("body") or "").lower()
    if not any(marker in body for marker in SCOPE_MARKERS):
        problems.append("missing scoped acceptance or implementation details")

    has_claim_prompt = any(
        marker in str(comment.get("body") or "").lower()
        for comment in comments
        for marker in CLAIM_MARKERS
    )
    if not has_claim_prompt:
        problems.append("missing maintainer claim prompt")
    return problems


def _message(text: str, output_format: str, *, error: bool = False) -> None:
    if output_format == "github":
        level = "error" if error else "notice"
        print(f"::{level} title=Community queue::{text}")
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY),
        help="GitHub repository in OWNER/NAME form",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="Optional GitHub API token; the scheduled workflow supplies one",
    )
    parser.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="Output format for local or GitHub Actions logs",
    )
    args = parser.parse_args(argv)

    try:
        issues = _paged_json(
            "issues",
            args.repo,
            args.token,
            state="open",
            labels=READY_LABEL,
        )
        ready_issues = [issue for issue in issues if "pull_request" not in issue]
        violations: list[tuple[int, str]] = []
        for issue in ready_issues:
            number = int(issue["number"])
            comments = _paged_json(f"issues/{number}/comments", args.repo, args.token)
            violations.extend(
                (number, problem)
                for problem in validate_ready_issue(issue, comments)
            )
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        _message(f"Unable to check the community queue: {error}", args.format, error=True)
        return 1

    if not ready_issues:
        _message("Community queue OK: no open `status: ready` issues.", args.format)
        return 0

    if violations:
        for number, problem in violations:
            _message(f"#{number}: {problem}", args.format, error=True)
        return 1

    _message(
        f"Community queue OK: {len(ready_issues)} open ready issues have labels, "
        "acceptance criteria, and a maintainer claim prompt.",
        args.format,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
