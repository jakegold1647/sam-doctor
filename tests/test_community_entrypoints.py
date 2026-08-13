from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_public_entry_points_keep_a_ready_issue_path() -> None:
    """Keep the first-contribution queue discoverable from every public surface."""

    assert "Find a mentored first issue" in _read("README.md")
    assert "[Code of Conduct](CODE_OF_CONDUCT.md)" in _read("README.md")
    assert "ready newcomer queue" in _read("CONTRIBUTING.md")
    assert "[Code of Conduct](CODE_OF_CONDUCT.md)" in _read("CONTRIBUTING.md")
    assert "ready newcomer queue" in _read("CONTRIBUTORS.md")
    assert "Find a mentored first issue" in _read(".github/ISSUE_TEMPLATE/config.yml")
    assert "https://github.com/jakegold1647/sam-doctor/discussions/1" in _read(
        ".github/ISSUE_TEMPLATE/config.yml"
    )
    assert "community welcome discussion" in _read("SUPPORT.md")
    assert "docs/community-outreach-plan.md" in _read("README.md")
    assert "docs/community-outreach-plan.md" in _read("CONTRIBUTING.md")
    assert "Browse mentored first issues" in _read("site/index.html")
    assert "Ask in the welcome discussion" in _read("site/index.html")
    assert "https://github.com/jakegold1647/sam-doctor/discussions/1" in _read(
        "site/index.html"
    )


def test_public_entry_points_make_early_feedback_welcome() -> None:
    """Keep draft work visibly welcome before a newcomer has a finished PR."""

    assert "Draft PRs are welcome" in _read("CONTRIBUTING.md")
    assert "Draft PRs and partial work are welcome" in _read(
        ".github/pull_request_template.md"
    )
    assert "Draft PRs are welcome" in _read("site/index.html")


def test_public_quickstart_keeps_the_credential_free_first_run_complete() -> None:
    """Keep the no-account demo reproducible, bounded, and easy to report."""

    quickstart = _read("site/quickstart.html")
    examples = _read("examples/README.md")

    assert "sam-doctor demo" in quickstart
    assert "src/sam_doctor/data/oidc-assume-role-failure.txt" in quickstart
    assert "github.oidc.assume-role-rejected" in quickstart
    assert "blob/main/SUPPORT.md" in quickstart
    assert "template=usage_feedback.yml" in quickstart

    assert (
        "sam-doctor diagnose examples/oidc-assume-role-failure.txt --format markdown"
        in examples
    )
    assert "github.oidc.assume-role-rejected" in examples
    assert "tests/test_bundled_samples.py tests/test_run_smoke.py" in examples


def test_community_triage_keeps_four_copy_ready_public_routes() -> None:
    """Keep each common report outcome safe, actionable, and contributor-ready."""

    playbook = _read("docs/community-triage.md")
    for heading in (
        "### The diagnosis helped",
        "### The failure was missed",
        "### The report is unclear or unsafe",
        "### Setup or workflow friction",
    ):
        assert heading in playbook

    assert playbook.count("**Escalation:**") == 4
    assert "[Support boundaries](../SUPPORT.md)" in playbook
    assert "template=usage_feedback.yml" in playbook
    assert "[Contributing a diagnostic rule](contributing-a-diagnostic-rule.md)" in playbook
    assert "discussions/categories/show-and-tell" in playbook
    assert (
        "None of these documentation, fixture, or test follow-ups requires "
        "repository\nadmin access"
    ) in playbook


def test_contributing_explains_the_claim_to_pr_path() -> None:
    """Make the maintainer handoff explicit for a first-time contributor."""

    contributing = _read("CONTRIBUTING.md")
    assert "What happens after you claim" in contributing
    assert "assign the" in contributing
    assert "Open a draft PR" in contributing
    assert "credit preserved" in contributing
    assert "welcome discussion" in contributing


def test_pull_request_template_keeps_issue_handoff_explicit() -> None:
    """Keep first PRs connected to the issue a maintainer prepared."""

    template = _read(".github/pull_request_template.md")
    assert 'Fixes #123' in template
    assert 'Related to #123' in template


def test_queue_check_runs_when_issue_availability_changes() -> None:
    """Keep claim and label changes from waiting for the weekly sweep."""

    workflow = _read(".github/workflows/community-queue.yml")
    assert (
        "types: [assigned, unassigned, labeled, unlabeled, edited, closed, reopened]"
        in workflow
    )
    assert "issue_comment:" in workflow
    assert "types: [created, edited, deleted]" in workflow
