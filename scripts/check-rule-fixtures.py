#!/usr/bin/env python3
"""Objective quality gate for the diagnostic-rule fixture registry.

`docs/contributing-a-diagnostic-rule.md` asks every rule for a sanitized
positive fixture and a nearby non-match. Until now that convention lived only
in `tests/test_diagnostics.py`, discoverable by reading the file rather than
by running one command. `RULE_FIXTURES` below is the inventory: one entry per
rule title, each entry a positive log line that must trigger the rule and a
negative log line that must not.

The registry does not need every rule on day one - `check_fixtures()` only
checks the rules that are actually registered, so a PR can migrate one rule
family at a time. `supported_rules()` minus `RULE_FIXTURES` is the remaining
backlog.

Checks:

- the fixture's rule title still exists in the catalog
- both a positive and a negative example are present
- the positive example triggers its rule; the negative example does not
- neither example contains an account id, ARN, access key, or email address

Exit code 0 when every registered fixture is clean, 1 when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor.diagnostics import diagnose, supported_rules


@dataclass(frozen=True)
class RuleFixture:
    """A minimal, sanitized positive and nearby-negative pair for one rule."""

    positive: str
    negative: str


# One rule family per PR, per `docs/contributing-a-diagnostic-rule.md`. This
# PR establishes the registry and migrates the GitHub Actions OIDC family;
# later PRs can add the remaining rules the same way.
RULE_FIXTURES: dict[str, RuleFixture] = {
    "The GitHub Actions job cannot request an OIDC token": RuleFixture(
        positive="Unable to get ID Token: missing id-token: write permission",
        negative=(
            "The job requested id-token: write and received a token without "
            "incident."
        ),
    ),
    "GitHub Actions cannot assume the configured AWS role through OIDC": RuleFixture(
        positive="Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        negative="AssumeRoleWithWebIdentity request succeeded after a brief retry",
    ),
    "GitHub OIDC token audience does not match AWS STS": RuleFixture(
        positive="InvalidIdentityToken: Incorrect token audience",
        negative="OIDC token audience was accepted after a handled retry",
    ),
    "The target AWS account is missing the GitHub Actions OIDC provider": RuleFixture(
        positive="No OpenIDConnect provider found in your account",
        negative=(
            "The GitHub Actions OpenIDConnect provider was already registered "
            "in the account"
        ),
    ),
}

# Identifier shapes the fixture text must never contain, independent of the
# report-time redaction rules in `sam_doctor.redaction` - a fixture should be
# clean before a rule ever runs on it.
_DISALLOWED_PATTERNS = {
    "AWS account id": re.compile(r"(?<!\d)\d{12}(?!\d)"),
    "ARN": re.compile(r"arn:aws"),
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
}


def check_fixtures(
    fixtures: dict[str, RuleFixture] | None = None,
) -> list[str]:
    """Return every fixture registry problem as a human-readable string."""

    fixtures = RULE_FIXTURES if fixtures is None else fixtures
    rules_by_title = {rule.title: rule for rule in supported_rules()}
    problems: list[str] = []

    for title, fixture in fixtures.items():
        if title not in rules_by_title:
            problems.append(f"{title!r}: no rule in the catalog has this title.")
            continue

        if not fixture.positive.strip():
            problems.append(f"{title!r}: fixture has no positive example.")
        if not fixture.negative.strip():
            problems.append(f"{title!r}: fixture has no nearby-negative example.")
        if not fixture.positive.strip() or not fixture.negative.strip():
            continue

        for label, text in (("positive", fixture.positive), ("negative", fixture.negative)):
            for kind, pattern in _DISALLOWED_PATTERNS.items():
                if pattern.search(text):
                    problems.append(
                        f"{title!r}: {label} fixture looks like it contains a {kind}."
                    )

        positive_titles = {finding.title for finding in diagnose(fixture.positive)}
        if title not in positive_titles:
            problems.append(f"{title!r}: positive fixture does not trigger this rule.")

        negative_titles = {finding.title for finding in diagnose(fixture.negative)}
        if title in negative_titles:
            problems.append(f"{title!r}: negative fixture still triggers this rule.")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rule",
        help="only check fixtures whose rule title contains this text (case-insensitive)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="github emits one ::error workflow command per problem",
    )
    args = parser.parse_args()

    fixtures = RULE_FIXTURES
    if args.rule:
        needle = args.rule.lower()
        fixtures = {
            title: fixture for title, fixture in fixtures.items() if needle in title.lower()
        }
        if not fixtures:
            print(f"No fixture registry entry matches --rule {args.rule!r}.")
            return 1

    problems = check_fixtures(fixtures)
    total_rules = len(supported_rules())
    if not problems:
        print(
            f"Rule fixture registry OK: {len(fixtures)} checked, "
            f"{len(RULE_FIXTURES)} of {total_rules} catalog rules registered."
        )
        return 0

    for problem in problems:
        if args.format == "github":
            print(f"::error title=Rule fixture check::{problem}")
        else:
            print(f"ERROR: {problem}")
    print(f"{len(problems)} problem(s) across {len(fixtures)} checked fixture(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
