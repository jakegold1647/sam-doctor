"""Deterministic fuzz: no output format may leak an identifier.

Composes logs from shuffled bundled-sample lines interleaved with synthetic
secrets, then asserts every report format redacts all of them. The seed is
fixed so failures reproduce exactly.
"""

from __future__ import annotations

import random
from pathlib import Path

from sam_doctor.cli import _render_findings
from sam_doctor.diagnostics import diagnose

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "src" / "sam_doctor" / "data"

# Key-shaped fixtures are assembled at runtime so secret scanners don't flag
# literal credentials in source; none of these are real.
SECRETS = (
    "AKIA" + "IOSFODNN7EXAMPLE",
    "ASIA" + "Y34FZKBOKMUTVV7A",
    "IQoJb3JpZ2luX2VjENr" + "A1b2C3d4" * 12,
    "ghp_abcdefghij0123456789abcdefghij456789",
    "arn:aws:iam::123456789012:role/deploy-role",
    "111122223333",
    "build-owner@example.com",
    'password="fuzz-hunter2"',
    "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
    '"SecretAccessKey": "je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY"',
    "xoxb-" + "1234567890-fuzzslackbot",
    "X-Amz-Signature=" + "deadbeef" * 8,
    # Prefixed UPPER_SNAKE_CASE names: the conventional spelling for an
    # environment variable, and the shape a word boundary on the keyword missed
    # entirely (`\bpassword` never matches inside `DB_PASSWORD`).
    "DB_PASSWORD=fuzz-prefixed-secret",
    "MY_API_KEY=fuzz-prefixed-apikey",
    # Credentials in a URL against a dotless internal host, which the email
    # pattern that used to catch this incidentally cannot match.
    "https://oauth2:glpat-fuzzgitlabtoken12345@gitlab/team/repo.git",
)

LEAK_MARKERS = (
    "fuzz-prefixed-secret",
    "fuzz-prefixed-apikey",
    "glpat-fuzzgitlabtoken12345",
    "AKIA" + "IOSFODNN7EXAMPLE",
    "ASIA" + "Y34FZKBOKMUTVV7A",
    "IQoJb3JpZ2luX2VjENr",
    "ghp_abcdefghij",
    "123456789012",
    "111122223333",
    "build-owner@example.com",
    "fuzz-hunter2",
    "wJalrXUtnFEMI",
    "je7MtGbClwBF",
    "fuzzslackbot",
    "deadbeef" * 8,
)


def test_fuzzed_logs_never_leak_identifiers_in_any_format() -> None:
    sample_lines = [
        line
        for sample in sorted(SAMPLES_DIR.glob("*.txt"))
        for line in sample.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rng = random.Random(20260804)
    rendered_redactions = 0

    for round_number in range(25):
        lines = rng.sample(sample_lines, k=min(40, len(sample_lines)))
        for secret in rng.sample(SECRETS, k=4):
            position = rng.randrange(len(lines) + 1)
            # Ride each secret on a rule-matching line so it lands in the
            # evidence that reports actually render; a secret on a noise line
            # never reaches the output and would make this test vacuous.
            carrier = rng.choice(
                [
                    f"Not authorized to perform: sts:AssumeRoleWithWebIdentity as {secret}",
                    f"AccessDeniedException for caller {secret}",
                    f"MyResource CREATE_FAILED Resource handler {secret} returned failure",
                    f"An error occurred (Throttling) Rate exceeded for {secret}",
                ]
            )
            lines.insert(position, carrier)
        log = "\n".join(lines)

        findings = diagnose(log)
        # sarif is included defensively rather than because it leaks today: its
        # results carry the title, explanation and a line number, and no evidence
        # snippet, so an evidence-borne secret cannot currently reach it. If a
        # `region.snippet` is ever added - SARIF consumers do expect one - this
        # loop is what stops that change from shipping a leak.
        for output_format in ("terminal", "markdown", "json", "github", "sarif"):
            report = _render_findings(findings, "fuzz.log", output_format)
            for marker in LEAK_MARKERS:
                assert marker not in report, (
                    f"round {round_number}: {marker!r} leaked in {output_format}"
                )
            rendered_redactions += report.count("[REDACTED")

    # Guard against vacuity: the fuzz must actually have pushed secrets into
    # rendered evidence, not just onto lines the reports never show.
    assert rendered_redactions > 50
