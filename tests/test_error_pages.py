"""The website error-page map must pass the objective gate reviewers rely on.

`scripts/check-error-pages.py` is the fast feedback loop for keeping
`site/errors/` in sync with the rule catalog; running it inside the suite
means CI enforces exactly what the script reports locally, so a contributor
can never pass one and fail the other.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_checker():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check-error-pages.py"
    spec = importlib.util.spec_from_file_location("check_error_pages", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_mapping_passes_every_check() -> None:
    checker = _load_checker()
    assert checker.check_error_pages() == []


def test_flags_a_title_with_no_matching_rule() -> None:
    checker = _load_checker()
    mapping = {"nobody.registered.this-id": "expired-token.html"}
    problems = checker.check_error_pages(mapping)
    assert any("no rule in the catalog carries this id" in problem for problem in problems)


def test_flags_a_mapped_page_that_does_not_exist() -> None:
    checker = _load_checker()
    title = next(iter(checker.ERROR_PAGE_MAP))
    mapping = {title: "this-page-does-not-exist.html"}
    problems = checker.check_error_pages(mapping)
    assert any("does not exist" in problem for problem in problems)


def test_flags_two_rules_mapped_to_the_same_page() -> None:
    checker = _load_checker()
    titles = list(checker.ERROR_PAGE_MAP)
    page = checker.ERROR_PAGE_MAP[titles[0]]
    mapping = {titles[0]: page, titles[1]: page}
    problems = checker.check_error_pages(mapping)
    assert any("is mapped from both" in problem for problem in problems)


def test_custom_mapping_diagnostics_ignore_insertion_order() -> None:
    checker = _load_checker()
    entries = [
        ("z.unregistered-rule", "shared-missing-page.html"),
        ("a.unregistered-rule", "shared-missing-page.html"),
    ]

    forward = checker.check_error_pages(dict(entries))
    reverse = checker.check_error_pages(dict(reversed(entries)))

    assert forward == reverse
    assert (
        "'shared-missing-page.html' is mapped from both "
        "'a.unregistered-rule' and 'z.unregistered-rule'."
    ) in forward


def test_flags_a_page_missing_from_the_mapping() -> None:
    checker = _load_checker()
    mapping = dict(checker.ERROR_PAGE_MAP)
    mapping.popitem()
    problems = checker.check_error_pages(mapping)
    assert any("has no mapping entry" in problem for problem in problems)


def test_flags_a_mapped_page_not_linked_from_the_index() -> None:
    checker = _load_checker()
    mapping = dict(checker.ERROR_PAGE_MAP)
    mapping["nobody.registered.this-id"] = "not-linked-anywhere.html"
    problems = checker.check_error_pages(mapping)
    assert any("not linked from site/errors/index.html" in problem for problem in problems)


def test_flags_a_page_whose_confidence_claim_drifted(tmp_path) -> None:
    checker = _load_checker()
    page = checker.SITE_ERRORS_DIR / "operation-in-progress.html"
    html = page.read_text(encoding="utf-8")
    assert "(high confidence)" in html, "fixture assumption: the page states high"
    drifted = html.replace("(high confidence)", "(medium confidence)")
    backup = html
    try:
        page.write_text(drifted, encoding="utf-8")
        problems = checker.check_error_pages()
    finally:
        page.write_text(backup, encoding="utf-8")
    assert any("confidence" in problem and "operation-in-progress" in problem for problem in problems)
