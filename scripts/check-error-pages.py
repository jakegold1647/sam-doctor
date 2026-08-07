#!/usr/bin/env python3
"""Objective quality gate for the website error index -> rule catalog mapping.

`docs/v1-milestone.md` flags the maintenance risk: the public error index
under `site/errors/` and the rule catalog in `diagnostics.py` are maintained
separately, so a rule can be reworded or removed and its page never catches
up, or a page can keep describing an error the catalog no longer recognizes.
`ERROR_PAGE_MAP` below is the inventory: one entry per rule that has a
dedicated page. A rule without an entry is represented by the shared index
page instead of a one-off write-up - `site/errors/index.html` already closes
with a prompt to request a page for anything unmatched, so that fallback
needs no extra plumbing.

Stable rule ids have not landed yet, so entries are keyed by rule title, the
same convention `check-rule-fixtures.py` uses for its registry. The map does
not need every rule on day one; it only needs to stay honest about the pages
that already exist.

Checks:

- every mapped rule title still exists in the catalog
- every mapped page file exists under site/errors/
- no two entries point at the same page
- every non-index page under site/errors/ has a mapping entry
- every mapped page is linked from site/errors/index.html, and every page
  linked from the index has a mapping entry

Exit code 0 when the mapping is clean, 1 when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor.diagnostics import supported_rules

SITE_ERRORS_DIR = REPO_ROOT / "site" / "errors"
INDEX_PAGE = SITE_ERRORS_DIR / "index.html"

# One entry per rule with a dedicated error page, in the same order they
# appear on the index page. Add an entry here in the same PR that adds or
# renames a page; a rule without an entry falls back to the shared index -
# see the module docstring.
ERROR_PAGE_MAP: dict[str, str] = {
    "GitHub Actions cannot assume the configured AWS role through OIDC": (
        "assume-role-with-web-identity.html"
    ),
    "The AWS credentials used by the deployment have expired": "expired-token.html",
    "The CI runner could not authenticate to ECR to push the image": (
        "no-basic-auth-credentials.html"
    ),
    "An explicit deny blocked a deployment action": "access-denied-explicit-deny.html",
    "A deployment action was denied because no policy allows it": (
        "access-denied-no-policy-allows.html"
    ),
    "A failed initial stack must be recreated before it can be deployed again": (
        "rollback-complete-cannot-be-updated.html"
    ),
    "CloudFormation could not delete one or more stack resources": "delete-failed.html",
    "CloudFormation needs an explicit capability acknowledgement": (
        "insufficient-capabilities.html"
    ),
    "CloudFormation throttled the deployment's API calls": "rate-exceeded.html",
    "The deployment failed only because there were no changes to deploy": (
        "no-changes-to-deploy.html"
    ),
    "A resource was accepted by its service but never reached a stable state": (
        "resource-did-not-stabilize.html"
    ),
    "A stack export cannot change while another stack imports it": "export-in-use.html",
    "SAM build requires Docker for containerized builds": "docker-unavailable.html",
    "SAM build cannot find the configured esbuild dependency": "esbuild-not-found.html",
    "API Gateway deployment started before the API had any methods": (
        "rest-api-no-methods.html"
    ),
}

_LOCAL_HTML_LINK = re.compile(r'href="\./([a-z0-9-]+\.html)"')


def _linked_pages(index_html: str) -> set[str]:
    return set(_LOCAL_HTML_LINK.findall(index_html))


def check_error_pages(mapping: dict[str, str] | None = None) -> list[str]:
    """Return every error-page mapping problem as a human-readable string."""

    mapping = ERROR_PAGE_MAP if mapping is None else mapping
    rules_by_title = {rule.title: rule for rule in supported_rules()}
    problems: list[str] = []

    pages_seen: dict[str, str] = {}
    for title, page in mapping.items():
        if title not in rules_by_title:
            problems.append(f"{title!r}: no rule in the catalog has this title.")

        earlier_title = pages_seen.get(page)
        if earlier_title is not None:
            problems.append(
                f"{page!r} is mapped from both {earlier_title!r} and {title!r}."
            )
        else:
            pages_seen[page] = title

        if not (SITE_ERRORS_DIR / page).is_file():
            problems.append(f"{title!r}: mapped page {page!r} does not exist.")

    mapped_pages = set(mapping.values())
    if SITE_ERRORS_DIR.is_dir():
        actual_pages = {
            path.name for path in SITE_ERRORS_DIR.glob("*.html") if path.name != "index.html"
        }
        for orphan in sorted(actual_pages - mapped_pages):
            problems.append(
                f"{orphan!r} exists under site/errors/ but has no mapping entry."
            )

    if INDEX_PAGE.is_file():
        linked = _linked_pages(INDEX_PAGE.read_text(encoding="utf-8"))
        for page in sorted(mapped_pages - linked):
            problems.append(
                f"{page!r} is mapped but not linked from site/errors/index.html."
            )
        for page in sorted(linked - mapped_pages):
            problems.append(
                f"{page!r} is linked from site/errors/index.html but has no mapping entry."
            )
    else:
        problems.append("site/errors/index.html does not exist.")

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

    problems = check_error_pages()
    total_rules = len(supported_rules())
    if not problems:
        print(
            f"Error page mapping OK: {len(ERROR_PAGE_MAP)} of {total_rules} catalog "
            "rules have a dedicated page."
        )
        return 0

    for problem in problems:
        if args.format == "github":
            print(f"::error title=Error page mapping check::{problem}")
        else:
            print(f"ERROR: {problem}")
    print(f"{len(problems)} problem(s) across {len(ERROR_PAGE_MAP)} mapped page(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
