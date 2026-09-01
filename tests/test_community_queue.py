from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check-community-queue.py"
SPEC = importlib.util.spec_from_file_location("check_community_queue", SCRIPT)
assert SPEC and SPEC.loader
QUEUE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUEUE)


def _issue(*, labels: tuple[str, ...], body: str, assigned: bool = False) -> dict:
    assignee = {"login": "someone"} if assigned else None
    return {
        "user": {"login": "jakegold1647"},
        "labels": [{"name": label} for label in labels],
        "body": body,
        "assignee": assignee,
        "assignees": [assignee] if assignee else [],
    }


def test_ready_issue_accepts_rule_issue_shape_and_claim_prompt() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body="## Where to add it\n## Sample log excerpts to test against",
    )

    assert QUEUE.validate_ready_issue(issue, [{"body": "I'd like to take this"}]) == []


def test_ready_issue_accepts_claim_prompt_in_body_before_comments() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body=(
            "## Acceptance criteria\n"
            "Comment `I'd like to take this` before starting so work stays coordinated."
        ),
    )

    assert QUEUE.validate_ready_issue(issue, []) == []


def test_ready_issue_reports_missing_labels_and_claim_prompt() -> None:
    issue = _issue(labels=("status: ready",), body="## Acceptance criteria")

    problems = QUEUE.validate_ready_issue(issue, [])

    assert "missing `good first issue` label" in problems
    assert "missing `mentor available` label" in problems
    assert (
        "missing one of `effort: small`, `effort: medium`, or `effort: large`"
        in problems
    )
    assert "missing maintainer claim prompt" in problems


def test_ready_issue_reports_invalid_effort_label() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: tiny"),
        body="## Acceptance criteria",
    )

    problems = QUEUE.validate_ready_issue(issue, [{"body": "Claim it when ready"}])

    assert "invalid effort label(s): effort: tiny" in problems
    assert (
        "missing one of `effort: small`, `effort: medium`, or `effort: large`"
        in problems
    )


def test_ready_issue_reports_multiple_effort_labels() -> None:
    issue = _issue(
        labels=(
            "status: ready",
            "good first issue",
            "mentor available",
            "effort: small",
            "effort: medium",
        ),
        body="## Acceptance criteria",
    )

    problems = QUEUE.validate_ready_issue(issue, [{"body": "Claim it when ready"}])

    assert "multiple `effort:*` labels" in problems


def test_ready_issue_reports_assignment_and_missing_scope() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body="A short issue with no implementation details.",
        assigned=True,
    )

    problems = QUEUE.validate_ready_issue(issue, [{"body": "Claim it when ready"}])

    assert "assigned work still carries `status: ready`" in problems
    assert "missing scoped acceptance or implementation details" in problems


def test_ready_issue_reports_unassigned_contributor_claim() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body="## Acceptance criteria",
    )

    problems = QUEUE.validate_ready_issue(
        issue,
        [
            {"user": {"login": "newcomer"}, "body": "I'd like to take this"},
        ],
    )

    assert "unassigned work has a contributor claim in comments" in problems


def test_ready_issue_reports_curly_apostrophe_contributor_claim() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body="## Acceptance criteria",
    )

    problems = QUEUE.validate_ready_issue(
        issue,
        [
            {
                "user": {"login": "newcomer"},
                "body": "I\u2019d like to take this",
            },
        ],
    )

    assert "unassigned work has a contributor claim in comments" in problems


def test_maintainer_invitation_is_not_an_active_claim() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body="## Acceptance criteria",
    )

    problems = QUEUE.validate_ready_issue(
        issue,
        [
            {
                "user": {"login": "jakegold1647"},
                "body": "Comment `I'd like to take this` if you want it.",
            },
        ],
    )

    assert "unassigned work has a contributor claim in comments" not in problems


def test_collaborator_invitation_is_not_an_active_claim() -> None:
    issue = _issue(
        labels=("status: ready", "good first issue", "mentor available", "effort: small"),
        body="## Acceptance criteria",
    )

    problems = QUEUE.validate_ready_issue(
        issue,
        [
            {
                "user": {"login": "another-maintainer"},
                "author_association": "COLLABORATOR",
                "body": "Comment `I'd like to take this` if you want it.",
            },
        ],
    )

    assert "unassigned work has a contributor claim in comments" not in problems


def test_main_reports_violations_in_issue_number_order(monkeypatch, capsys) -> None:
    issues = []
    for number in (10, 2):
        issue = _issue(
            labels=(
                "status: ready",
                "good first issue",
                "mentor available",
                "effort: small",
            ),
            body="## Acceptance criteria\nComment `claim this` before starting.",
            assigned=True,
        )
        issue["number"] = number
        issues.append(issue)

    def fake_paged_json(path: str, *_args, **_kwargs) -> list[dict]:
        return issues if path == "issues" else []

    monkeypatch.setattr(QUEUE, "_paged_json", fake_paged_json)

    assert QUEUE.main(["--repo", "owner/repository"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "#2: assigned work still carries `status: ready`",
        "#10: assigned work still carries `status: ready`",
    ]
