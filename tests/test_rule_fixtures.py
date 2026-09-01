"""The rule fixture registry must pass the objective gate reviewers rely on.

`scripts/check-rule-fixtures.py` is the fast feedback loop for the fixture
registry; running it inside the suite means CI enforces exactly what the
script reports locally, so a contributor can never pass one and fail the
other.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_checker():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check-rule-fixtures.py"
    spec = importlib.util.spec_from_file_location("check_rule_fixtures", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The module defines a dataclass under `from __future__ import annotations`;
    # dataclass resolves its field types via `sys.modules`, so the module must
    # be registered there before `exec_module` runs the class body.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_registry_passes_every_check() -> None:
    checker = _load_checker()
    assert checker.check_fixtures() == []


def test_flags_an_id_with_no_matching_rule() -> None:
    checker = _load_checker()
    fixtures = {
        "nobody.registered.this-id": checker.RuleFixture(
            positive="anything", negative="anything else"
        )
    }
    problems = checker.check_fixtures(fixtures)
    assert any("no rule in the catalog" in problem for problem in problems)


def test_custom_fixture_diagnostics_ignore_insertion_order() -> None:
    checker = _load_checker()
    entries = [
        (
            "z.unregistered-rule",
            checker.RuleFixture(positive="anything", negative="anything else"),
        ),
        (
            "a.unregistered-rule",
            checker.RuleFixture(positive="anything", negative="anything else"),
        ),
    ]

    forward = checker.check_fixtures(dict(entries))
    reverse = checker.check_fixtures(dict(reversed(entries)))

    assert forward == [
        "'a.unregistered-rule': no rule in the catalog carries this id.",
        "'z.unregistered-rule': no rule in the catalog carries this id.",
    ]
    assert reverse == forward


def test_flags_a_catalog_rule_missing_from_the_registry() -> None:
    checker = _load_checker()
    complete = checker.RULE_FIXTURES
    dropped = dict(complete)
    dropped.pop("iam.deny.explicit")
    checker.RULE_FIXTURES = dropped
    try:
        problems = checker.check_fixtures()
    finally:
        checker.RULE_FIXTURES = complete
    assert any("has no fixture registry entry" in problem for problem in problems)


def test_flags_a_missing_positive_or_negative_example() -> None:
    checker = _load_checker()
    title = next(iter(checker.RULE_FIXTURES))
    fixtures = {title: checker.RuleFixture(positive="", negative="something")}
    problems = checker.check_fixtures(fixtures)
    assert any("no positive example" in problem for problem in problems)


def test_flags_a_positive_fixture_that_does_not_trigger_its_rule() -> None:
    checker = _load_checker()
    title = next(iter(checker.RULE_FIXTURES))
    fixtures = {
        title: checker.RuleFixture(
            positive="Everything completed successfully.",
            negative="Everything completed successfully.",
        )
    }
    problems = checker.check_fixtures(fixtures)
    assert any("does not trigger this rule" in problem for problem in problems)


def test_flags_a_negative_fixture_that_still_triggers_its_rule() -> None:
    checker = _load_checker()
    title = "github.oidc.audience-mismatch"
    fixture = checker.RULE_FIXTURES[title]
    fixtures = {title: checker.RuleFixture(positive=fixture.positive, negative=fixture.positive)}
    problems = checker.check_fixtures(fixtures)
    assert any("still triggers this rule" in problem for problem in problems)


def test_flags_a_fixture_containing_an_account_id() -> None:
    checker = _load_checker()
    title = next(iter(checker.RULE_FIXTURES))
    fixture = checker.RULE_FIXTURES[title]
    fixtures = {
        title: checker.RuleFixture(
            positive=f"{fixture.positive} 123456789012", negative=fixture.negative
        )
    }
    problems = checker.check_fixtures(fixtures)
    assert any("account id" in problem for problem in problems)


def test_rule_filter_narrows_which_fixtures_run() -> None:
    checker = _load_checker()
    argv = sys.argv
    sys.argv = ["check-rule-fixtures.py", "--rule", "audience"]
    try:
        assert checker.main() == 0
    finally:
        sys.argv = argv
