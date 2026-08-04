"""The rule catalog must pass the objective quality gate reviewers rely on.

`scripts/check-rule-catalog.py` is the fast feedback loop for rule PRs; running
it inside the suite means CI enforces exactly what the script reports locally,
so a contributor can never pass one and fail the other.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sam_doctor.diagnostics import Rule


def _load_checker():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check-rule-catalog.py"
    spec = importlib.util.spec_from_file_location("check_rule_catalog", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rule(**overrides) -> Rule:
    defaults = {
        "title": "A well-formed example rule",
        "confidence": "high",
        "patterns": (r"ExampleFailureException",),
        "explanation": "Something specific failed.",
        "verification": ("Check the specific thing.",),
        "documentation_url": "https://docs.aws.amazon.com/example",
    }
    defaults.update(overrides)
    return Rule(**defaults)


def test_current_catalog_passes_every_check() -> None:
    checker = _load_checker()
    assert checker.check_rules() == []


def test_flags_pattern_matching_benign_output() -> None:
    checker = _load_checker()
    problems = checker.check_rules((_rule(patterns=(r"Uploading to",)),))
    assert any("benign log line" in problem for problem in problems)


def test_flags_pattern_matching_empty_string() -> None:
    checker = _load_checker()
    problems = checker.check_rules((_rule(patterns=(r"(?:optional)?",)),))
    assert any("empty string" in problem for problem in problems)


def test_flags_broken_regex_and_bad_metadata() -> None:
    checker = _load_checker()
    problems = checker.check_rules(
        (
            _rule(
                patterns=(r"(unclosed",),
                confidence="certain",
                documentation_url="http://insecure.example.com",
            ),
        )
    )
    text = "\n".join(problems)
    assert "does not compile" in text
    assert "confidence" in text
    assert "https://" in text


def test_flags_duplicate_titles() -> None:
    checker = _load_checker()
    problems = checker.check_rules((_rule(), _rule()))
    assert any("Duplicate rule title" in problem for problem in problems)
