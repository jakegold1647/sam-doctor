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

Entries are keyed by stable rule id, the same convention
`check-rule-fixtures.py` uses for its registry, so a reworded title cannot
orphan a page. The map does not need every rule on day one; it only needs to
stay honest about the pages that already exist.

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
    "github.oidc.assume-role-rejected": "assume-role-with-web-identity.html",
    "aws.credentials.expired": "expired-token.html",
    "ecr.auth.login-failed": "no-basic-auth-credentials.html",
    "iam.deny.explicit": "access-denied-explicit-deny.html",
    "iam.deny.implicit": "access-denied-no-policy-allows.html",
    "cloudformation.stack.failed-recreate-required": (
        "rollback-complete-cannot-be-updated.html"
    ),
    "cloudformation.stack.delete-failed": "delete-failed.html",
    "cloudformation.capabilities.required": "insufficient-capabilities.html",
    "cloudformation.api.throttled": "rate-exceeded.html",
    "cloudformation.deploy.no-changes": "no-changes-to-deploy.html",
    "cloudformation.resource.stabilization-timeout": "resource-did-not-stabilize.html",
    "cloudformation.export.in-use": "export-in-use.html",
    "cloudformation.stack.operation-in-progress": "operation-in-progress.html",
    "cloudformation.template.quota-exceeded": "template-limit-exceeded.html",
    "sam.build.docker-required": "docker-unavailable.html",
    "sam.build.esbuild-missing": "esbuild-not-found.html",
    "sam.template.schema-validation-failed": "invalid-sam-document.html",
    "s3.bucket-name.already-taken": "bucket-already-exists.html",
    "s3.artifact-bucket.access-denied": "s3-access-denied-changeset.html",
    "apigateway.deployment.no-methods": "rest-api-no-methods.html",
    "lambda.package.size-limit-exceeded": "lambda-package-size-limit.html",
    "lambda.code-storage.limit-exceeded": "code-storage-limit-exceeded.html",
    "sam.deploy.interactive-confirmation-required": "confirm-changeset-prompt.html",
    "cloudformation.stack.termination-protection": "termination-protection.html",
    "sam.deploy.artifact-upload-failed": "unable-to-upload-artifact.html",
    "lambda.ecr-image.access-denied": "lambda-ecr-image-access.html",
    "apigateway.cors.preflight-conflict": "cors-options-conflict.html",
    "sam.build.python-dependency-resolution-failed": "pip-dependency-resolution.html",
    "sam.build.python-runtime-mismatch": "python-runtime-mismatch.html",
    "sam.deploy.bucket-config-conflict": "resolve-s3-conflict.html",
    "github.oidc.token-request-denied": "unable-to-get-id-token.html",
    "github.oidc.audience-mismatch": "incorrect-token-audience.html",
    "github.oidc.provider-missing": "no-oidc-provider.html",
    "iam.trust-policy.resource-field-invalid": "prohibited-field-resource.html",
    "lambda.code-signing.image-incompatible": "code-signing-container-image.html",
    "s3.bucket-name.invalid": "invalid-bucket-name.html",
    "cloudformation.lambda-layer.artifact-unreadable": "layer-artifact-access-denied.html",
    "sam.build.python-dependency-validation-failed": "binary-validation-failed.html",
    "cloudformation.rollback.iam-role-delete-failed": "rollback-role-delete-failed.html",
}

_LOCAL_HTML_LINK = re.compile(r'href="\./([a-z0-9-]+\.html)"')


def _linked_pages(index_html: str) -> set[str]:
    return set(_LOCAL_HTML_LINK.findall(index_html))


def check_error_pages(mapping: dict[str, str] | None = None) -> list[str]:
    """Return every error-page mapping problem as a human-readable string."""

    mapping = ERROR_PAGE_MAP if mapping is None else mapping
    rules_by_id = {rule.id: rule for rule in supported_rules()}
    problems: list[str] = []

    pages_seen: dict[str, str] = {}
    for rule_id, page in mapping.items():
        if rule_id not in rules_by_id:
            problems.append(f"{rule_id!r}: no rule in the catalog carries this id.")

        earlier_id = pages_seen.get(page)
        if earlier_id is not None:
            problems.append(
                f"{page!r} is mapped from both {earlier_id!r} and {rule_id!r}."
            )
        else:
            pages_seen[page] = rule_id

        if not (SITE_ERRORS_DIR / page).is_file():
            problems.append(f"{rule_id!r}: mapped page {page!r} does not exist.")

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
