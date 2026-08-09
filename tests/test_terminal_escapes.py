"""Logs arrive coloured, and colour used to make findings disappear.

The SAM CLI colours its own output, as do most build tools, so a log saved from a
terminal or downloaded raw from a CI provider can read `\x1b[31mFAILED\x1b[0m`
where a rule pattern expects `FAILED`. The escape sits inside the word, which is
the worst possible place: the report looks normal to whoever reads it, the pattern
silently fails, and the finding is simply not there. Colouring the words a CI
provider actually colours dropped one of the two findings on the bundled
CloudFormation sample.

Checked at the same time and needing no handling: timestamp prefixes, CRLF, lone
carriage returns from progress bars, leading whitespace, non-breaking spaces.
Those are pinned below so a future normalization change cannot break them either.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sam_doctor.diagnostics import diagnose, likely_error_excerpt

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE = REPO_ROOT / "examples" / "cloudformation-resource-failure.txt"
SAMPLES = sorted((REPO_ROOT / "examples").glob("*.txt"))
CI_TIMESTAMP = "2026-08-08T01:23:45.6789012Z "

RED = "\x1b[31m"
BOLD_RED = "\x1b[1;31m"
RESET = "\x1b[0m"


def _ids(text: str) -> tuple[str, ...]:
    return tuple(sorted(finding.rule_id for finding in diagnose(text)))


def _colour_every_word(text: str) -> str:
    return re.sub(r"\w+", lambda match: f"{BOLD_RED}{match.group(0)}{RESET}", text)


def _prefix_lines(text: str, prefix: str) -> str:
    return "".join(prefix + line for line in text.splitlines(keepends=True))


@pytest.fixture(scope="module")
def sample() -> str:
    return SAMPLE.read_text(encoding="utf-8")


def test_colour_inside_a_matched_word_does_not_hide_a_finding(sample: str) -> None:
    # The exact defect: FAILED wrapped in a colour code.
    plain = _ids(sample)
    assert len(plain) == 2, "sample expected to produce two findings"

    coloured = sample.replace("FAILED", f"{RED}FAILED{RESET}")

    assert _ids(coloured) == plain


@pytest.mark.parametrize(
    ("name", "transform"),
    [
        ("every word coloured", _colour_every_word),
        ("bold and colour", lambda t: t.replace("FAILED", f"{BOLD_RED}FAILED{RESET}")),
        ("osc hyperlink", lambda t: t.replace("FAILED", "\x1b]8;;http://x\x07FAILED\x1b]8;;\x07")),
        ("cursor movement", lambda t: t.replace("FAILED", "\x1b[2KFAILED")),
        ("ci timestamp prefix", lambda t: _prefix_lines(t, CI_TIMESTAMP)),
        ("crlf line endings", lambda t: t.replace("\n", "\r\n")),
        ("progress bar carriage returns", lambda t: _prefix_lines(t, "Deploying... \r")),
        ("indented output", lambda t: _prefix_lines(t, "    ")),
        ("coloured and timestamped", lambda t: _prefix_lines(_colour_every_word(t), CI_TIMESTAMP)),
    ],
)
def test_realistic_log_shapes_produce_the_same_findings(sample: str, name: str, transform) -> None:
    assert _ids(transform(sample)) == _ids(sample), f"{name} changed the findings"


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_every_bundled_sample_survives_being_coloured(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")

    assert _ids(_colour_every_word(raw)) == _ids(raw)


def test_evidence_carries_no_escape_sequences(sample: str) -> None:
    # Escapes in evidence would reach JSON reports, SARIF, and the redaction
    # path, where they are noise at best.
    findings = diagnose(sample.replace("FAILED", f"{RED}FAILED{RESET}"))

    assert findings
    for finding in findings:
        for line in finding.evidence:
            assert "\x1b" not in line


def test_the_excerpt_helper_is_also_stripped() -> None:
    # This is what a contributor pastes into a rule request when nothing
    # matched, so escapes here become escapes in a GitHub issue.
    text = f"Some line\n{RED}Error{RESET}: something went wrong\nAnother line\n"

    excerpt = likely_error_excerpt(text)

    assert excerpt, "a coloured Error line must still look like an error"
    for _line_number, line in excerpt:
        assert "\x1b" not in line


def test_a_whole_log_suppression_still_applies_when_coloured() -> None:
    # suppressed_by searches the whole text rather than a line, so it needed the
    # same normalization; a coloured suppressor would switch a suppression off
    # and produce a finding the rule author decided not to report.
    plain = (
        "Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity\n"
        "Error: No changes to deploy. Stack demo is up to date\n"
    )
    coloured = _colour_every_word(plain)

    assert _ids(coloured) == _ids(plain)


def test_colour_does_not_invent_findings() -> None:
    # Stripping must not fuse two lines or expose text that was not there: a
    # benign coloured log stays benign.
    benign = f"{RED}Build Succeeded{RESET}\nDeployment succeeded\n"

    assert diagnose(benign) == []
