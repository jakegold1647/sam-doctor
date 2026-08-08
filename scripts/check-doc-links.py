#!/usr/bin/env python3
"""Check that every rule's documentation link still resolves.

Each finding points a user at official documentation, and those URLs rot
quietly: AWS reorganizes its docs and a link that shipped fine a year ago
starts answering 404. Nothing in the offline test suite can notice, because
noticing requires the network.

That is also why this check is deliberately NOT part of the pull-request gate.
sam-doctor's whole premise is that it runs offline and deterministically, and
a network call in the PR gate would make contributors' builds depend on the
reachability of someone else's website. It runs on a schedule instead, where a
failure is a maintenance signal rather than a blocked contribution.

Exit code 0 when every link resolves, 1 when any does not.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor.diagnostics import supported_rules

_TIMEOUT_SECONDS = 30
# Plain courtesy to the documentation hosts, and enough of a gap that a burst
# of requests is not mistaken for scraping.
_DELAY_SECONDS = 0.4
_USER_AGENT = "sam-doctor-doc-link-check (+https://github.com/jakegold1647/sam-doctor)"


def _status(url: str) -> tuple[int | str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return response.status, response.geturl()
    except urllib.error.HTTPError as error:
        return error.code, url
    except Exception as error:  # noqa: BLE001 - any failure is worth reporting
        return f"{type(error).__name__}", url


def check_doc_links() -> list[str]:
    """Return one human-readable problem per unreachable documentation link."""

    urls: dict[str, list[str]] = {}
    for rule in supported_rules():
        urls.setdefault(rule.documentation_url, []).append(rule.id)

    problems: list[str] = []
    for url in sorted(urls):
        code, _final = _status(url)
        if code != 200:
            problems.append(
                f"{url} returned {code}; used by {', '.join(sorted(urls[url]))}."
            )
        time.sleep(_DELAY_SECONDS)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="github emits one ::error workflow command per problem",
    )
    args = parser.parse_args()

    problems = check_doc_links()
    link_count = len({rule.documentation_url for rule in supported_rules()})
    if not problems:
        print(f"Documentation links OK: {link_count} unique links all resolve.")
        return 0

    for problem in problems:
        if args.format == "github":
            print(f"::error title=Documentation link check::{problem}")
        else:
            print(f"ERROR: {problem}")
    print(f"{len(problems)} unreachable link(s) across {link_count} checked.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
