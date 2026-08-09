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


def test_every_relative_markdown_link_resolves() -> None:
    """Relative links between docs need no network, and nothing checked them.

    The scheduled check above walks rule `documentation_url` values, which are all
    external. The 58 relative links inside the README, CONTRIBUTING and the docs
    directory - the ones that carry a reader from a rule to its worked example -
    were verified by nobody. They are also the ones a rename breaks, which is the
    same defect already closed today for the sitemap and for site HTML.

    Kept in the per-push gate rather than the weekly one precisely because it needs
    no network: a contributor should learn this from their own commit.
    """

    import re

    sources = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CONTRIBUTING.md",
        *sorted((REPO_ROOT / "docs").glob("*.md")),
    ]

    broken: list[str] = []
    checked = 0
    for markdown in sources:
        if not markdown.is_file():
            continue
        for raw_target in re.findall(r"\]\(([^)]+)\)", markdown.read_text(encoding="utf-8")):
            target = raw_target.strip().split()[0]
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            checked += 1
            relative = target.split("#")[0]
            if relative and not (markdown.parent / relative).exists():
                broken.append(f"{markdown.relative_to(REPO_ROOT)} -> {target}")

    assert checked > 40, f"only {checked} relative links found; the scan probably broke"
    assert broken == [], "broken relative links:\n  " + "\n  ".join(broken)


def test_roadmap_documentation_links_are_discovered(checker) -> None:
    # Contributors are pointed at these as the authoritative reference for a rule
    # they are about to write, and nothing checked them before.
    links = checker.roadmap_documentation_links()

    assert len(links) >= 10, f"only found {len(links)}; the roadmap parse looks broken"
    for url, label in links.items():
        assert url.startswith("https://")
        assert label.startswith("rule-roadmap entry ")


def test_the_roadmap_links_join_the_checked_set(checker, monkeypatch) -> None:
    from sam_doctor.diagnostics import supported_rules

    _stub_status(checker, monkeypatch, [404])
    problems = checker.check_doc_links()

    rule_urls = {rule.documentation_url for rule in supported_rules()}
    roadmap_only = set(checker.roadmap_documentation_links()) - rule_urls
    assert roadmap_only, "expected at least one link that only the roadmap uses"

    reported = {problem.split(" returned ")[0] for problem in problems}
    assert roadmap_only <= reported, f"unchecked roadmap links: {sorted(roadmap_only - reported)}"


def test_a_roadmap_only_failure_names_the_entry(checker, monkeypatch) -> None:
    # The message has to say where to fix it. "used by rule-roadmap entry 14" sends
    # the maintainer straight to the paragraph; a bare URL does not.
    from sam_doctor.diagnostics import supported_rules

    _stub_status(checker, monkeypatch, [404])
    rule_urls = {rule.documentation_url for rule in supported_rules()}
    problems = checker.check_doc_links()

    roadmap_only = set(checker.roadmap_documentation_links()) - rule_urls
    for problem in problems:
        url = problem.split(" returned ")[0]
        if url in roadmap_only:
            assert "rule-roadmap entry" in problem, problem


def test_a_missing_roadmap_file_is_not_an_error(checker, monkeypatch, tmp_path) -> None:
    # The checker must survive the file being renamed rather than crashing a
    # scheduled run over it.
    monkeypatch.setattr(checker, "_ROADMAP", tmp_path / "absent.md")

    assert checker.roadmap_documentation_links() == {}
