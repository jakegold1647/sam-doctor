"""What the shipped sample logs report, frozen.

`src/sam_doctor/data/*.txt` are shipped inside the wheel: `sam-doctor demo` runs
one, the README quotes them, and the composite Action's own CI asserts a finding
count against `examples/oidc-assume-role-failure.txt`. So the finding set for
each one is a published behaviour, not an implementation detail.

Tightening a rule is supposed to remove false positives without removing real
detections, and the difference between those two is invisible unless something
pins it. These expectations were captured by running v0.11.0's own code against
the same files and confirming every set matched, so the baseline is what shipped
rather than what happened to be true afterwards.

A deliberate change here is fine - update the expectation and say why in the
changelog. An accidental one is what this catches.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sam_doctor.diagnostics import diagnose

DATA_DIR = Path(__file__).resolve().parents[1] / "src" / "sam_doctor" / "data"
EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"

EXPECTED: dict[str, set[str]] = {
    "api-gateway-no-methods-failure.txt": {"apigateway.deployment.no-methods"},
    "capability-acknowledgement-failure.txt": {"cloudformation.capabilities.required"},
    "cloudformation-resource-failure.txt": {
        "cloudformation.resource.create-update-failed",
        "cloudformation.stack.rollback-complete",
    },
    "esbuild-missing-failure.txt": {"sam.build.esbuild-missing"},
    "interactive-changeset-failure.txt": {
        "sam.deploy.interactive-confirmation-required"
    },
    "oidc-assume-role-failure.txt": {"github.oidc.assume-role-rejected"},
    # The resolution rule is suppressed here by "Binary validation failed", which
    # lets the validation rule own the line. That is deliberate, not a miss.
    "python-pip-build-failure.txt": {
        "sam.build.python-dependency-validation-failed",
        "sam.build.python-runtime-mismatch",
    },
    "s3-bucket-conflict-failure.txt": {"sam.deploy.bucket-config-conflict"},
}


def test_every_bundled_sample_is_covered_by_an_expectation() -> None:
    on_disk = {path.name for path in DATA_DIR.glob("*.txt")}

    unexpected = sorted(on_disk - set(EXPECTED))
    assert not unexpected, (
        "a new sample ships with no expectation here, so nothing pins what it "
        f"reports: {unexpected}"
    )

    missing = sorted(set(EXPECTED) - on_disk)
    assert not missing, f"expectations name samples that no longer exist: {missing}"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_bundled_sample_reports_exactly_what_it_shipped_reporting(name: str) -> None:
    text = (DATA_DIR / name).read_text(encoding="utf-8")

    assert {finding.rule_id for finding in diagnose(text)} == EXPECTED[name]


@pytest.mark.parametrize(
    "name", sorted(path.name for path in EXAMPLES_DIR.glob("*.txt"))
)
def test_example_log_still_produces_a_finding(name: str) -> None:
    # examples/ is what the README points a first-time reader at, and the
    # Action's CI asserts a count against the OIDC one. An example that reports
    # nothing is worse than no example.
    text = (EXAMPLES_DIR / name).read_text(encoding="utf-8")

    assert diagnose(text), f"{name} produces no finding"


def test_the_oidc_example_still_produces_exactly_one_finding() -> None:
    # ci.yml asserts finding-count == 1 against this file through the composite
    # action, in both the Linux and Windows jobs. If a new rule ever matched it
    # a second time, that assertion would fail in CI rather than here - this
    # names the constraint where someone adding a rule will see it.
    text = (EXAMPLES_DIR / "oidc-assume-role-failure.txt").read_text(encoding="utf-8")

    assert len(diagnose(text)) == 1


def test_the_public_oidc_example_matches_the_packaged_demo_sample() -> None:
    """Keep the documented first run and the installed demo on one fixture."""

    public_sample = (EXAMPLES_DIR / "oidc-assume-role-failure.txt").read_text(
        encoding="utf-8"
    )
    packaged_sample = (DATA_DIR / "oidc-assume-role-failure.txt").read_text(
        encoding="utf-8"
    )

    assert public_sample.rstrip("\r\n") == packaged_sample.rstrip("\r\n")
