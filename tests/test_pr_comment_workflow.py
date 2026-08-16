"""Safety checks for the opt-in pull-request comment example."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / "examples" / "github-actions-pr-comment.yml"


def test_pr_comment_example_keeps_the_safe_event_and_permission_boundary() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request_target" not in workflow
    assert "pull_request:" in workflow
    assert "permissions:\n  contents: read\n  pull-requests: write" in workflow
    assert "if: always()" in workflow
    assert (
        "github.event.pull_request.head.repo.full_name == github.repository"
        in workflow
    )
    assert "summary: true" in workflow
    assert "first-finding-report: sam-doctor-first-finding.md" in workflow
    assert "continue-on-error: true" in workflow


def test_pr_comment_example_reads_the_generated_report_and_is_idempotent() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'fs.readFileSync("sam-doctor-first-finding.md", "utf8")' in workflow
    assert "<!-- sam-doctor:first-finding -->" in workflow
    assert "github.rest.issues.listComments" in workflow
    assert "github.rest.issues.updateComment" in workflow
    assert "github.rest.issues.createComment" in workflow
    assert "${{ steps.sam-doctor.outputs" not in workflow
    assert "actions/upload-artifact" not in workflow
