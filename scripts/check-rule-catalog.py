#!/usr/bin/env python3
"""Objective quality gate for the diagnostic rule catalog.

Reviewers and first-time contributors get the same fast feedback: run this
script (or the test suite, which runs the same checks) and every structural
problem with a new or edited rule is reported at once, before a human review
gets to the judgement calls that actually need a human.

Checks are deliberately objective — anything that needs taste stays out:

- every pattern (primary, suppression, exclusion) compiles under IGNORECASE
- no primary pattern matches the empty string (an always-firing rule)
- no primary pattern matches a corpus of ordinary, successful deploy output,
  so over-broad patterns fail here instead of in a user's clean CI log
- ids are unique, non-empty, and match the `lower.dotted-with-hyphens` shape
- ids are unique, non-empty, and match the `lower.dotted-with-hyphens` shape
- titles are unique and non-empty; confidence is high/medium/low
- explanation, verification steps, and an https documentation link exist

Exit code 0 when the catalog is clean, 1 when any check fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor.diagnostics import Rule, supported_rules

_CONFIDENCE_LEVELS = ("high", "medium", "low")
_MAX_VERIFICATION_STEPS = 6
_RULE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$")
_RULE_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$")

# Ordinary, successful deployment output. A primary pattern that matches any
# of these lines would raise findings on clean logs, which is the single worst
# failure mode for a diagnostic tool people run on every CI job.
BENIGN_LOG_LINES = (
    "Uploading to my-bucket/artifact.zip (100%)",
    "Successfully created/updated stack - my-app in us-east-1",
    "Creating the required S3 bucket if one does not exist",
    "Build Succeeded",
    "Built Artifacts  : .aws-sam/build",
    "Waiting for changeset to be created",
    "Changeset created successfully",
    "MyStack UPDATE_COMPLETE",
    "MyFunction CREATE_COMPLETE AWS::Lambda::Function",
    "Deploying with following values",
    "Initiating deployment",
    "Previewing changes before deployment",
)


def _compile_problems(rule: Rule, field: str, patterns: tuple[str, ...]) -> list[str]:
    problems = []
    for pattern in patterns:
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            problems.append(
                f"{rule.title!r}: {field} pattern {pattern!r} does not compile: {error}"
            )
    return problems


def check_rules(rules: tuple[Rule, ...] = ()) -> list[str]:
    """Return every catalog problem as a human-readable string."""

    rules = rules or supported_rules()
    problems: list[str] = []
    seen_titles: set[str] = set()
    seen_ids: set[str] = set()

    for rule in rules:
        title = rule.title.strip()
        if not title:
            problems.append("A rule has an empty title.")
        elif title in seen_titles:
            problems.append(f"Duplicate rule title: {title!r}.")
        seen_titles.add(title)

        rule_id = rule.id.strip()
        if not rule_id:
            problems.append(f"{title!r}: has no id.")
        elif rule_id in seen_ids:
            problems.append(f"Duplicate rule id: {rule_id!r}.")
        elif not _RULE_ID_PATTERN.match(rule_id):
            problems.append(
                f"{title!r}: id {rule_id!r} does not match the "
                "lower.dotted-with-hyphens shape, e.g. `aws.iam.explicit-deny`."
            )
        seen_ids.add(rule_id)

        if rule.confidence not in _CONFIDENCE_LEVELS:
            problems.append(
                f"{title!r}: confidence {rule.confidence!r} is not one of "
                f"{'/'.join(_CONFIDENCE_LEVELS)}."
            )

        if not rule.patterns:
            problems.append(f"{title!r}: has no patterns.")
        problems.extend(_compile_problems(rule, "primary", rule.patterns))
        problems.extend(_compile_problems(rule, "suppressed_by", rule.suppressed_by))
        problems.extend(
            _compile_problems(rule, "excluded_line_patterns", rule.excluded_line_patterns)
        )

        for pattern in rule.patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error:
                continue  # already reported above
            if compiled.search(""):
                problems.append(
                    f"{title!r}: pattern {pattern!r} matches the empty string."
                )
            for line in BENIGN_LOG_LINES:
                if compiled.search(line):
                    problems.append(
                        f"{title!r}: pattern {pattern!r} matches benign log line "
                        f"{line!r}."
                    )

        if not rule.explanation.strip():
            problems.append(f"{title!r}: explanation is empty.")
        if not rule.verification:
            problems.append(f"{title!r}: has no verification steps.")
        elif len(rule.verification) > _MAX_VERIFICATION_STEPS:
            problems.append(
                f"{title!r}: {len(rule.verification)} verification steps; keep it "
                f"to {_MAX_VERIFICATION_STEPS} or fewer focused steps."
            )
        if any(not step.strip() for step in rule.verification):
            problems.append(f"{title!r}: has an empty verification step.")
        if not rule.documentation_url.startswith("https://"):
            problems.append(
                f"{title!r}: documentation_url must be an https:// link, got "
                f"{rule.documentation_url!r}."
            )

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

    problems = check_rules()
    rule_count = len(supported_rules())
    if not problems:
        print(f"Rule catalog OK: {rule_count} rules passed every check.")
        return 0

    for problem in problems:
        if args.format == "github":
            print(f"::error title=Rule catalog check::{problem}")
        else:
            print(f"ERROR: {problem}")
    print(f"{len(problems)} problem(s) across {rule_count} rules.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
