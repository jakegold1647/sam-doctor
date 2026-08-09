from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "commit-metadata.yml"
ZERO_SHA = "0000000000000000000000000000000000000000"


def test_commit_metadata_workflow_has_only_the_trailers_job() -> None:
    parsed = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert parsed["name"] == "Commit metadata"
    assert set(parsed["jobs"]) == {"trailers"}


def test_push_scan_fails_closed_instead_of_scanning_only_the_tip() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "BEFORE: ${{ github.event_name == 'push' && github.event.before || '' }}" in workflow
    assert f'if [ "$BEFORE" = "{ZERO_SHA}" ]; then' in workflow
    assert 'RANGE="$HEAD"' in workflow
    assert "HEAD~1..$HEAD" not in workflow
    assert '|| echo "$HEAD"' not in workflow

    assert '::error::Previous SHA $BEFORE is unavailable; refusing a partial commit scan' in workflow
    assert 'echo "::error::Unable to enumerate the complete commit range $RANGE"' in workflow
    assert 'COMMITS=$(git rev-list "$RANGE" 2>/dev/null) || {' in workflow
