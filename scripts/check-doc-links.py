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

# Statuses meaning "ask again later" rather than "this link is gone". A 404 is a
# real answer and is not retried. A timeout or a 503 is the host having a moment,
# and reporting that as rot is how a weekly maintenance signal earns a reputation
# for crying wolf - after which nobody reads it.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_RETRY_DELAY_SECONDS = 3.0


def _status(url: str) -> tuple[int | str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return response.status, response.geturl()
    except urllib.error.HTTPError as error:
        return error.code, url
    except Exception as error:  # noqa: BLE001 - any failure is worth reporting
        return f"{type(error).__name__}", url


def _status_with_retry(url: str) -> tuple[int | str, str]:
    """Fetch a status, asking a second time when the first answer was not final.

    One attempt makes a weekly check as reliable as the flakiest host it touches.
    A definitive 404 is taken at its word; anything transient gets one more try
    after a pause.
    """

    code, final = _status(url)
    if code == 200:
        return code, final
    # A string code is an exception name: a timeout, DNS failure, reset connection.
    if isinstance(code, str) or code in _RETRYABLE_STATUS:
        time.sleep(_RETRY_DELAY_SECONDS)
        code, final = _status(url)
    return code, final


def check_doc_links() -> list[str]:
    """Return one human-readable problem per unreachable documentation link."""

    urls: dict[str, list[str]] = {}
    for rule in supported_rules():
        urls.setdefault(rule.documentation_url, []).append(rule.id)

    problems: list[str] = []
    for url in sorted(urls):
        code, _final = _status_with_retry(url)
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
