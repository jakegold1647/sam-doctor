"""Offline tests for the field-detection measurement.

The measurement itself needs the network and runs on a schedule, but the decisions
it makes do not: what counts as a real failure line, what gets grouped as one
signature, and whether a redacted excerpt is safe to print. Those are the parts that
could quietly start measuring nothing - a `FAILURE_SIGNAL` that matches issue prose
inflates the denominator and makes detection look worse than it is, and one that
matches too little makes it look better.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_measurement():
    spec = importlib.util.spec_from_file_location(
        "measure_field_detection", str(REPO_ROOT / "scripts" / "measure-field-detection.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load measure-field-detection.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def measurement():
    return _load_measurement()


REAL_FAILURE_LINES = (
    "MyBucket CREATE_FAILED Resource handler returned message: something",
    "An error occurred (AccessDenied) when calling the CreateChangeSet operation",
    "User is not authorized to perform sts:AssumeRoleWithWebIdentity",
    "Waiter ChangeSetCreateComplete failed: terminal failure",
    "Error: Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable",
    "Stack is in ROLLBACK_COMPLETE state and can not be updated",
    "AssemblyError: Assembly builder failed",
    "[BackendBuildError] Caused by: [_AssemblyError] Assembly builder failed",
)

NOT_FAILURE_LINES = (
    "I am trying to deploy my SAM application and it does not work",
    "Resources:\n  MyFunction:\n    Type: AWS::Serverless::Function",
    "sam deploy --guided --stack-name my-app",
    "Deployment succeeded and the stack is now CREATE_COMPLETE",
)


@pytest.mark.parametrize("line", REAL_FAILURE_LINES)
def test_real_failure_lines_are_recognized(measurement, line: str) -> None:
    body = f"```\n{line}\n{'padding to clear the length floor. ' * 3}\n```"

    assert measurement.failure_excerpts(body), f"not recognized as a failure: {line!r}"


@pytest.mark.parametrize("text", NOT_FAILURE_LINES)
def test_prose_and_templates_are_excluded_from_the_denominator(measurement, text: str) -> None:
    # Counting these would make the percentage a measure of how much unrelated text
    # people paste into issues.
    body = f"```\n{text}\n{'more padding to clear the length floor. ' * 3}\n```"

    assert measurement.failure_excerpts(body) == []


def test_a_body_with_no_fenced_block_still_yields_its_failure_line(measurement) -> None:
    # Plenty of issues paste a log inline. Requiring a fence would drop them.
    body = "Deploy broke today: An error occurred (ValidationError) when calling CreateChangeSet " + (
        "and here is some more context about it. " * 3
    )

    assert measurement.failure_excerpts(body)


def test_signatures_group_runs_that_differ_only_by_identifiers(measurement) -> None:
    first = measurement.signature(
        "2026-08-02T10:00:00Z MyRole CREATE_FAILED for account 123456789012 "
        "request 4f2c9a1b-1111-2222-3333-444455556666"
    )
    second = measurement.signature(
        "2026-08-09T22:31:07Z MyRole CREATE_FAILED for account 210987654321 "
        "request 9a8b7c6d-9999-8888-7777-666655554444"
    )

    assert first == second, f"{first!r} != {second!r}"


def test_a_signature_carries_no_identifiers(measurement) -> None:
    # These are other people's logs, printed into a CI summary.
    signature = measurement.signature(
        "CREATE_FAILED arn:aws:iam::123456789012:role/deploy for build-owner@example.test"
    )

    assert "123456789012" not in signature
    assert "build-owner@example.test" not in signature
    assert "REDACTED" in signature


def test_measure_counts_diagnosed_and_groups_the_rest(measurement) -> None:
    samples = [
        ("u1", "Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity"),
        ("u2", "Error: Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable"),
        ("u3", "An error occurred (SomethingNobodyHasARuleFor) when calling the Frobnicate operation"),
    ]

    diagnosed, missed = measurement.measure(samples)

    assert diagnosed == 2
    assert sum(missed.values()) == 1


def test_collect_deduplicates_the_same_excerpt_posted_twice(measurement) -> None:
    body = (
        "```\nMyBucket CREATE_FAILED Resource handler returned message: boom. "
        + ("padding " * 10)
        + "\n```"
    )
    items = [
        {"html_url": "https://example.test/1", "body": body},
        {"html_url": "https://example.test/2", "body": body},
    ]

    assert len(measurement.collect(items)) == 1


def test_collect_and_measure_are_independent_of_api_order(measurement) -> None:
    shared_prefix = (
        "An error occurred (SomethingNobodyHasARuleFor) when calling the "
        "Frobnicate operation "
    )
    shared_prefix += "x" * (400 - len(shared_prefix))
    preferred_excerpt = shared_prefix + " alpha"
    later_excerpt = shared_prefix + " omega"
    separate_excerpt = (
        "zzz context\n"
        "An error occurred (AnotherUnknownFailure) when calling the Quux operation "
        + " ".join(["padding"] * 10)
    )

    def item(url: str, excerpt: str) -> dict[str, str]:
        return {"html_url": url, "body": f"```\n{excerpt}\n```"}

    items = [
        item("https://example.test/z", later_excerpt),
        item("https://example.test/b", preferred_excerpt),
        item("https://example.test/a", preferred_excerpt),
        item("https://example.test/separate", separate_excerpt),
    ]

    forward_samples = measurement.collect(items)
    reverse_samples = measurement.collect(list(reversed(items)))

    assert forward_samples == reverse_samples
    assert forward_samples == [
        ("https://example.test/a", preferred_excerpt),
        ("https://example.test/separate", separate_excerpt),
    ]
    assert measurement.measure(forward_samples) == measurement.measure(reverse_samples)
    diagnosed, missed = measurement.measure(forward_samples)
    assert diagnosed == 0
    assert sum(missed.values()) == 2


def test_main_output_is_independent_of_api_order_for_tied_misses(
    measurement, monkeypatch, capsys
) -> None:
    alpha_signature_excerpt = (
        "zzz context\n"
        "An error occurred (AlphaUnknownFailure) when calling the Quux operation "
        + " ".join(["padding"] * 10)
    )
    zeta_signature_excerpt = (
        "aaa context\n"
        "An error occurred (ZetaUnknownFailure) when calling the Frobnicate operation "
        + " ".join(["padding"] * 10)
    )

    def item(url: str, excerpt: str) -> dict[str, str]:
        return {"html_url": url, "body": f"```\n{excerpt}\n```"}

    items = [
        item("https://example.test/zeta", zeta_signature_excerpt),
        item("https://example.test/alpha", alpha_signature_excerpt),
    ]
    monkeypatch.setattr(measurement, "QUERIES", ("offline query",))
    monkeypatch.setattr(sys, "argv", ["measure-field-detection.py", "--floor", "0"])

    monkeypatch.setattr(measurement, "_search", lambda *_args: items)
    forward_status = measurement.main()
    forward_output = capsys.readouterr().out

    monkeypatch.setattr(measurement, "_search", lambda *_args: list(reversed(items)))
    reverse_status = measurement.main()
    reverse_output = capsys.readouterr().out

    assert forward_status == reverse_status == 0
    assert forward_output == reverse_output
    assert forward_output.index("AlphaUnknownFailure") < forward_output.index(
        "ZetaUnknownFailure"
    )


def test_no_samples_is_inconclusive_rather_than_a_failure(measurement, monkeypatch) -> None:
    # A rate-limited or offline scheduled run must not be reported as the catalog
    # having regressed. That is how a maintenance signal loses its meaning.
    monkeypatch.setattr(measurement, "QUERIES", ())
    monkeypatch.setattr(measurement, "_search", lambda *_args: [])
    monkeypatch.setattr(sys, "argv", ["measure-field-detection.py"])

    assert measurement.main() == 0
