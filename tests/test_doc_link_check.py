"""Offline tests for the documentation-link checker.

The check itself needs the network and runs on a schedule, deliberately outside
the pull-request gate - so its logic had no coverage at all. These tests stub the
one function that touches the network, which is the whole point: the decision
about what counts as rot is testable without leaving the machine.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_doc_links", str(REPO_ROOT / "scripts" / "check-doc-links.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load check-doc-links.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def checker(monkeypatch: pytest.MonkeyPatch):
    module = _load_checker()
    # No real sleeping: these tests assert behaviour, not patience.
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    return module


def _stub_status(module, monkeypatch: pytest.MonkeyPatch, answers: list):
    """Answer each call with the next value, recording how many calls happened."""
    calls: list[str] = []

    def fake_status(url: str):
        calls.append(url)
        value = answers[min(len(calls) - 1, len(answers) - 1)]
        return value, url

    monkeypatch.setattr(module, "_status", fake_status)
    return calls


def test_a_resolving_link_is_not_retried(checker, monkeypatch) -> None:
    calls = _stub_status(checker, monkeypatch, [200])

    code, _ = checker._status_with_retry("https://example.com/ok")

    assert code == 200
    assert len(calls) == 1, "a link that resolved must not be fetched twice"


def test_a_404_is_taken_at_its_word(checker, monkeypatch) -> None:
    # Retrying a definitive answer only doubles the load on a host that already
    # told us the truth.
    calls = _stub_status(checker, monkeypatch, [404])

    code, _ = checker._status_with_retry("https://example.com/gone")

    assert code == 404
    assert len(calls) == 1


@pytest.mark.parametrize("transient", [503, 502, 500, 429, 408, "TimeoutError"])
def test_a_transient_failure_is_retried_once(checker, monkeypatch, transient) -> None:
    calls = _stub_status(checker, monkeypatch, [transient, 200])

    code, _ = checker._status_with_retry("https://example.com/flaky")

    assert code == 200, f"{transient} should have been retried and recovered"
    assert len(calls) == 2


def test_a_persistent_transient_failure_is_still_reported(checker, monkeypatch) -> None:
    # One retry, not an unbounded loop: a host that is genuinely down must still
    # produce a maintenance signal.
    calls = _stub_status(checker, monkeypatch, [503, 503])

    code, _ = checker._status_with_retry("https://example.com/down")

    assert code == 503
    assert len(calls) == 2


def test_a_problem_names_every_rule_using_the_link(checker, monkeypatch) -> None:
    # The message has to say which rules to fix, or the maintainer has to go
    # looking for them.
    _stub_status(checker, monkeypatch, [404])

    problems = checker.check_doc_links()

    assert problems, "a 404 on every link must produce problems"
    for problem in problems:
        assert "returned 404" in problem
        assert "used by " in problem
        assert "." in problem.split("used by ")[1]


def test_all_links_resolving_reports_no_problems(checker, monkeypatch) -> None:
    _stub_status(checker, monkeypatch, [200])

    assert checker.check_doc_links() == []


def test_every_rule_url_is_https_and_checked_once(checker) -> None:
    # The catalog gate already requires https; this asserts the checker looks at
    # the deduplicated set, so a link shared by several rules is fetched once.
    from sam_doctor.diagnostics import supported_rules

    urls = [rule.documentation_url for rule in supported_rules()]
    assert all(url.startswith("https://") for url in urls)
    assert len(set(urls)) < len(urls), (
        "some rules are expected to share a documentation link; if that stops "
        "being true this assertion can go, but the dedup path should stay tested"
    )
