"""SARIF output is a rendering of existing findings, so the contract to hold
is structural: one 2.1.0 run, a deduplicated rule table for the rules that
fired, and results whose locations point back at the right log and line."""

from __future__ import annotations

import json
from pathlib import Path

from sam_doctor import __version__
from sam_doctor.cli import main
from sam_doctor.diagnostics import diagnose, sarif_report

_OIDC_LINE = (
    "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
    "arn:aws:iam::123456789012:role/deploy"
)
_EXPIRED_LINE = "An error occurred (ExpiredToken): The security token is expired"


def _single_run(document: str) -> dict[str, object]:
    payload = json.loads(document)
    assert payload["$schema"] == "https://json.schemastore.org/sarif-2.1.0.json"
    assert payload["version"] == "2.1.0"
    assert len(payload["runs"]) == 1
    return payload["runs"][0]


def test_sarif_document_shape_for_a_single_finding() -> None:
    findings = diagnose(_OIDC_LINE)
    assert findings, "fixture line must keep producing a finding"

    run = _single_run(sarif_report([("deploy.log", findings)]))
    driver = run["tool"]["driver"]
    assert driver["name"] == "sam-doctor"
    assert driver["version"] == __version__

    assert len(driver["rules"]) == len(findings)
    for rule, result in zip(driver["rules"], run["results"]):
        assert rule["id"] == result["ruleId"]
        assert rule["shortDescription"]["text"]
        assert rule["helpUri"].startswith("https://")
        assert result["ruleIndex"] == driver["rules"].index(rule)
        assert result["level"] in ("error", "warning", "note")
        assert result["message"]["text"]
        location = result["locations"][0]["physicalLocation"]
        assert location["artifactLocation"]["uri"] == "deploy.log"
        assert location["region"]["startLine"] >= 1


def test_confidence_maps_to_sarif_levels() -> None:
    findings = diagnose(_EXPIRED_LINE)
    run = _single_run(sarif_report([("deploy.log", findings)]))
    by_confidence = {finding.rule_id: finding.confidence for finding in findings}
    for result in run["results"]:
        expected = {"high": "error", "medium": "warning"}[by_confidence[result["ruleId"]]]
        assert result["level"] == expected


def test_empty_findings_produce_a_valid_empty_run() -> None:
    run = _single_run(sarif_report([("clean.log", [])]))
    assert run["results"] == []
    assert run["tool"]["driver"]["rules"] == []


def test_batch_run_dedupes_rules_and_keeps_per_file_locations() -> None:
    first = diagnose(_EXPIRED_LINE)
    second = diagnose(_EXPIRED_LINE)
    run = _single_run(sarif_report([("a.log", first), ("b.log", second)]))

    rule_ids = [rule["id"] for rule in run["tool"]["driver"]["rules"]]
    assert len(rule_ids) == len(set(rule_ids)), "rule table must be deduplicated"
    assert len(run["results"]) == len(first) + len(second)

    uris = {
        result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        for result in run["results"]
    }
    assert uris == {"a.log", "b.log"}
    for result in run["results"]:
        index = result["ruleIndex"]
        assert run["tool"]["driver"]["rules"][index]["id"] == result["ruleId"]


def test_artifact_uris_are_redacted_and_forward_slashed() -> None:
    findings = diagnose(_OIDC_LINE)
    run = _single_run(
        sarif_report([(r"logs\123456789012\deploy.log", findings)])
    )
    uri = run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert "\\" not in uri
    assert "123456789012" not in uri


def test_cli_diagnose_emits_sarif(tmp_path: Path, capsys) -> None:
    log = tmp_path / "deploy.log"
    log.write_text(_OIDC_LINE, encoding="utf-8")

    exit_code = main(["diagnose", str(log), "--format", "sarif"])
    assert exit_code == 0
    run = _single_run(capsys.readouterr().out)
    assert run["results"], "the CLI must surface the finding as a SARIF result"


def test_cli_batch_emits_one_sarif_document(tmp_path: Path, capsys) -> None:
    (tmp_path / "one.log").write_text(_OIDC_LINE, encoding="utf-8")
    (tmp_path / "two.log").write_text("Build Succeeded", encoding="utf-8")

    exit_code = main(["batch", str(tmp_path)])
    capsys.readouterr()
    assert exit_code == 0

    exit_code = main(["batch", str(tmp_path), "--format", "sarif"])
    assert exit_code == 0
    run = _single_run(capsys.readouterr().out)
    uris = {
        result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        for result in run["results"]
    }
    assert any(uri.endswith("one.log") for uri in uris)
    assert not any(uri.endswith("two.log") for uri in uris), "clean file adds no results"


def test_sarif_output_matches_the_published_schema(tmp_path: Path) -> None:
    import jsonschema

    schema = json.loads(
        (Path(__file__).resolve().parent.parent / "docs" / "schemas" / "sarif-report.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = jsonschema.Draft202012Validator(schema)

    findings = diagnose(_OIDC_LINE + "\n" + _EXPIRED_LINE)
    validator.validate(json.loads(sarif_report([("deploy.log", findings)])))
    validator.validate(json.loads(sarif_report([("clean.log", [])])))
