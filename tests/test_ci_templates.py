"""Keep non-GitHub CI starters from hiding a failed deployment."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
STARTERS = (
    "examples/gitlab-ci-sam-doctor.yml",
    "examples/circleci-sam-doctor.yml",
    "examples/azure-pipelines-sam-doctor.yml",
    "examples/bitbucket-pipelines-sam-doctor.yml",
)


@pytest.mark.parametrize("relative_path", STARTERS)
def test_non_github_starter_preserves_deploy_status(relative_path: str) -> None:
    path = ROOT / relative_path
    content = path.read_text(encoding="utf-8")

    # The pipeline must be allowed to capture PIPESTATUS before restoring errexit;
    # otherwise a failed deploy exits before SAM Doctor can inspect its log.
    assert "set -o pipefail" in content
    assert content.count("set +e") >= 2
    assert "deploy_status=${PIPESTATUS[0]}" in content
    assert "set -e" in content
    assert 'if [ "$deploy_status" -ne 0 ]; then' in content
    assert 'exit "$deploy_status"' in content

    # Diagnosis is advisory in the starter, but the deployment itself is not.
    assert "--fail-on-findings" not in content
    assert "|| true" not in content
    assert "allow_failure" not in content
    assert "continueOnError" not in content


@pytest.mark.parametrize("relative_path", STARTERS)
def test_non_github_starter_is_valid_yaml(relative_path: str) -> None:
    yaml.safe_load((ROOT / relative_path).read_text(encoding="utf-8"))
