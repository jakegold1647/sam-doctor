"""Parse and protect the forkable credential-free OIDC demo workflow."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "oidc-diagnostic-demo.yml"


def test_oidc_demo_is_manual_credential_free_and_proves_the_expected_rule() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    triggers = document.get(True, document.get("on", {}))
    assert set(triggers) == {"workflow_dispatch"}
    assert document["permissions"] == {"contents": "read"}

    steps = document["jobs"]["diagnose-sanitized-example"]["steps"]
    action = next(step for step in steps if step.get("uses") == "./")
    assert action["with"] == {
        "log-file": "examples/oidc-assume-role-failure.txt",
        "summary": True,
        "annotations": False,
    }

    check_step = next(
        step for step in steps if step.get("name") == "Write and check the redacted diagnosis"
    )
    assert check_step["env"] == {"PYTHONPATH": "src"}
    checks = check_step["run"]
    assert "python -m sam_doctor.cli diagnose examples/oidc-assume-role-failure.txt" in checks
    assert 'rule_ids == ["github.oidc.assume-role-rejected"]' in checks
    assert 'payload["finding_count"] == 1' in checks
    assert 'assert "123456789012" not in report' in checks
    assert 'assert "builder@example.com" not in report' in checks


def test_oidc_demo_uploads_only_the_redacted_diagnosis() -> None:
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["diagnose-sanitized-example"]["steps"]
    artifact = next(
        step for step in steps if "actions/upload-artifact@" in step.get("uses", "")
    )

    assert artifact["with"]["name"] == "redacted-oidc-diagnosis"
    assert artifact["with"]["path"] == "oidc-diagnosis.json"
    assert artifact["with"]["retention-days"] == 1
    assert artifact["with"]["if-no-files-found"] == "error"
    assert "examples/oidc-assume-role-failure.txt" not in str(artifact)
    assert "deployment.log" not in str(artifact)
