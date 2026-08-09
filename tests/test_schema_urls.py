"""`sam-doctor schemas` hands out URLs, and nothing checked they resolve.

The four URLs are hard-coded strings pointing at raw.githubusercontent.com on
`main`. Rename or move a schema file and every local gate still passes - the files
exist, the reports still validate against them, the tests that read them read them
by path - while the command tells users to fetch a 404. The weekly documentation
link check does not cover these either: it walks rule `documentation_url` values.

Checking the URL against the repository closes that offline and immediately, which
beats finding out from a user. What cannot be checked here is whether the file has
been pushed to `main` yet, so a brand-new schema is briefly a 404 by design.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

from sam_doctor.cli import _SCHEMA_URLS, main

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_PREFIX = "https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/"


@pytest.mark.parametrize("name", sorted(_SCHEMA_URLS))
def test_each_published_schema_url_points_at_a_file_in_this_repository(name: str) -> None:
    url = _SCHEMA_URLS[name]
    assert url.startswith(RAW_PREFIX), f"{name} schema URL is not a raw link on main: {url}"

    relative = url[len(RAW_PREFIX) :]
    target = REPO_ROOT / relative

    assert target.is_file(), (
        f"`sam-doctor schemas` publishes {url} for {name!r}, and {relative} does not "
        "exist in this repository - the command is handing users a 404"
    )


@pytest.mark.parametrize("name", sorted(_SCHEMA_URLS))
def test_each_published_schema_is_valid_json_with_a_declared_dialect(name: str) -> None:
    relative = _SCHEMA_URLS[name][len(RAW_PREFIX) :]
    schema = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))

    assert "$schema" in schema, f"{relative} declares no dialect"
    assert schema.get("type") or schema.get("oneOf") or schema.get("$ref"), (
        f"{relative} constrains nothing"
    )


def test_the_schemas_command_lists_every_machine_readable_output() -> None:
    # A format that emits JSON without a published schema leaves a consumer
    # guessing, which is the situation this command exists to prevent.
    assert set(_SCHEMA_URLS) == {"diagnose", "batch", "rules", "sarif"}, (
        "a machine-readable output was added or removed; publish or retire its "
        "schema URL alongside it"
    )


def test_the_json_form_of_the_command_is_parseable(capsys) -> None:
    assert main(["schemas", "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload == _SCHEMA_URLS


def test_the_text_form_names_every_schema(capsys) -> None:
    assert main(["schemas"]) == 0

    out = capsys.readouterr().out
    for name, url in _SCHEMA_URLS.items():
        assert re.search(rf"^{re.escape(name)}:\s*{re.escape(url)}$", out, re.MULTILINE), (
            f"{name} is missing from the text output"
        )


def test_every_schema_url_is_https_and_unique() -> None:
    urls = list(_SCHEMA_URLS.values())

    assert len(set(urls)) == len(urls), "two outputs share one schema URL"
    for url in urls:
        assert urlparse(url).scheme == "https"


def test_the_diagnose_schema_accepts_a_report_containing_every_rule() -> None:
    """The schema is validated against sample reports, which exercise a few rules.

    A schema can be too narrow for one rule out of fifty-four - a longer
    explanation, a different confidence, a rule whose verification list is a
    different length - and a sample-based check will never notice. Validating a
    single report that carries all of them costs nothing and closes that gap.
    """

    from jsonschema import Draft202012Validator

    from sam_doctor.diagnostics import Finding, json_report, supported_rules

    schema = json.loads(
        (REPO_ROOT / "docs" / "schemas" / "diagnose-report.schema.json").read_text(
            encoding="utf-8"
        )
    )
    findings = [
        Finding(
            rule_id=rule.id,
            title=rule.title,
            confidence=rule.confidence,
            explanation=rule.explanation,
            verification=rule.verification,
            documentation_url=rule.documentation_url,
            evidence=("2026-08-02 CREATE_FAILED some log line",),
            line_number=index + 1,
        )
        for index, rule in enumerate(supported_rules())
    ]

    payload = json.loads(json_report(findings, "deploy.log"))
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path))

    assert errors == [], "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


def test_the_rules_and_sarif_schemas_accept_full_catalog_payloads() -> None:
    # Same reasoning as the diagnose case above, for the other two schemas that can
    # be produced offline. `rules --format json` is inherently full-catalog; the
    # SARIF one is not, so it gets two sources' worth of every rule.
    from jsonschema import Draft202012Validator

    from sam_doctor.diagnostics import (
        Finding,
        rules_report,
        sarif_report,
        supported_rules,
    )

    findings = [
        Finding(
            rule_id=rule.id,
            title=rule.title,
            confidence=rule.confidence,
            explanation=rule.explanation,
            verification=rule.verification,
            documentation_url=rule.documentation_url,
            evidence=("2026-08-02 CREATE_FAILED some log line",),
            line_number=index + 1,
        )
        for index, rule in enumerate(supported_rules())
    ]

    payloads = {
        "rules-report.schema.json": json.loads(rules_report("json")),
        "sarif-report.schema.json": json.loads(
            sarif_report([("a.log", findings), ("b.log", findings)])
        ),
    }

    for schema_file, payload in payloads.items():
        schema = json.loads(
            (REPO_ROOT / "docs" / "schemas" / schema_file).read_text(encoding="utf-8")
        )
        errors = sorted(
            Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path)
        )
        assert errors == [], f"{schema_file}: " + "; ".join(
            f"{list(e.path)}: {e.message}" for e in errors[:3]
        )
