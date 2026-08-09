"""No secret may reach any artifact meant for sharing.

The fuzz suite covers `_render_findings`, which is the four report formats. It does
not cover the two artifacts built specifically to leave the machine: the evidence
packet, and the rule-request excerpt that the docs tell contributors to paste into
a public GitHub issue. Those are assembled by separate code paths, so passing the
format tests says nothing about them.

This walks every surface at once with one log carrying one secret of each kind, so
a new output surface that forgets to redact fails here rather than in someone's
issue thread.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sam_doctor.cli import main

# Assembled at runtime so secret scanners do not flag literals in source. None of
# these are real, and each marker is unique so a failure names the leaking kind.
SECRET_LINES = (
    "Authorization: Basic " + "WxlYWt5LWJhc2ljLWNyZWQ" + "lbnRpYWw=",
    "POST https://hooks.slack.com/services/T00000000/B00000000/"
    + "leakmarkerslackhook"
    + " failed",
    "https://discord.com/api/webhooks/123456789012/" + "leakmarkerdiscordhook",
    "AWS_SECRET_ACCESS_KEY=" + "leakmarkerawssecret",
    "DB_PASSWORD=" + "leakmarkerdbpassword",
    "cloning https://git:" + "leakmarkerurlcred" + "@internal-git/team/repo.git",
    "using " + "AKIA" + "IOSFODNN7EXAMPLE",
    "role arn:aws:iam::" + "123456789012" + ":role/deploy",
    "contact " + "release-owner@example.test",
    "token " + "ghp_" + "abcdefghij0123456789abcdefghij456789",
)
SCENARIO_SECRET = "leakmarkerscenario"

LEAK_MARKERS = (
    "WxlYWt5LWJhc2ljLWNyZWQ",
    "leakmarkerslackhook",
    "leakmarkerdiscordhook",
    "leakmarkerawssecret",
    "leakmarkerdbpassword",
    "leakmarkerurlcred",
    "AKIA" + "IOSFODNN7EXAMPLE",
    "123456789012",
    "release-owner@example.test",
    "ghp_" + "abcdefghij",
    SCENARIO_SECRET,
)

# A real failure keeps the log diagnosable, so the artifacts have findings in them
# rather than being trivially empty.
#
# The secret is repeated *on* the failing line as well as on lines of its own,
# and that distinction is the point. A report format quotes only the matched
# evidence line, so a secret sitting elsewhere in the log never reaches it - the
# format surfaces would pass no matter what redaction did. The packet and the rule
# request embed surrounding text, so they see both. Covering both placements is
# what makes this a check on redaction rather than on which lines get quoted.
FAILURE_LINE = (
    "Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity "
    "Authorization: Basic " + "WxlYWt5LWJhc2ljLWNyZWQ" + "lbnRpYWw= "
    "AWS_SECRET_ACCESS_KEY=" + "leakmarkerawssecret"
)
LOG_TEXT = "\n".join((*SECRET_LINES, FAILURE_LINE, ""))


@pytest.fixture
def log(tmp_path: Path) -> Path:
    path = tmp_path / "deployment.log"
    path.write_text(LOG_TEXT, encoding="utf-8")
    return path


def _assert_clean(text: str, surface: str) -> None:
    for marker in LEAK_MARKERS:
        assert marker not in text, f"{marker!r} leaked into {surface}"


@pytest.mark.parametrize(
    "output_format", ["terminal", "markdown", "json", "github", "sarif"]
)
def test_no_report_format_leaks(log: Path, capsys, output_format: str) -> None:
    assert main(["diagnose", str(log), "--format", output_format]) == 0

    _assert_clean(capsys.readouterr().out, f"diagnose --format {output_format}")


def test_no_packet_file_leaks(log: Path, tmp_path: Path) -> None:
    output_dir = tmp_path / "packet"

    assert (
        main(
            [
                "packet",
                str(log),
                "--output-dir",
                str(output_dir),
                "--scenario",
                "DB_PASSWORD=" + SCENARIO_SECRET,
            ]
        )
        == 0
    )

    written = sorted(output_dir.iterdir())
    assert written, "the packet wrote nothing to check"
    for path in written:
        _assert_clean(path.read_text(encoding="utf-8"), f"packet/{path.name}")
    notes = (output_dir / "researcher-notes.md").read_text(encoding="utf-8")
    assert "- Scenario: DB_PASSWORD=[REDACTED_SECRET]" in notes


def test_the_rule_request_excerpt_does_not_leak(log: Path, tmp_path: Path) -> None:
    # The highest-risk surface in the project: the docs tell contributors to paste
    # this file into a public issue.
    output_dir = tmp_path / "request"

    assert main(["request-packet", str(log), "--output-dir", str(output_dir)]) == 0

    written = sorted(output_dir.iterdir())
    assert written, "the rule request wrote nothing to check"
    for path in written:
        _assert_clean(path.read_text(encoding="utf-8"), f"request-packet/{path.name}")


def test_a_written_report_file_does_not_leak(log: Path, tmp_path: Path) -> None:
    # --output writes through a different path than stdout.
    target = tmp_path / "diagnosis.json"

    assert main(["diagnose", str(log), "--format", "json", "--output", str(target)]) == 0

    _assert_clean(target.read_text(encoding="utf-8"), "diagnose --output")


@pytest.mark.parametrize("output_format", ("terminal", "markdown"))
def test_batch_output_does_not_leak(
    log: Path, tmp_path: Path, capsys, output_format: str
) -> None:
    second = tmp_path / f"DB_PASSWORD={SCENARIO_SECRET}.log"
    second.write_text(LOG_TEXT, encoding="utf-8")

    assert main(["batch", str(log), str(second), "--format", output_format]) == 0

    rendered = capsys.readouterr().out
    _assert_clean(rendered, f"batch --format {output_format}")
    assert "DB_PASSWORD=[REDACTED_SECRET]" in rendered


def test_the_log_is_still_diagnosed_through_all_that_noise(log: Path, capsys) -> None:
    # Guards the guard: if the secrets somehow stopped the rule from matching, the
    # assertions above would pass against empty reports.
    assert main(["diagnose", str(log), "--format", "markdown"]) == 0

    assert "sts:AssumeRoleWithWebIdentity" in capsys.readouterr().out


def test_annotations_do_not_double_the_sentence_period(log: Path, capsys) -> None:
    # The period was appended unconditionally while every rule already ends its
    # first verification step with one, so every annotation ever written read
    # `write`..` in the GitHub UI - the surface most people actually see.
    from sam_doctor.cli import _render_findings
    from sam_doctor.diagnostics import Finding, supported_rules

    for rule in supported_rules():
        finding = Finding(
            rule_id=rule.id,
            title=rule.title,
            confidence=rule.confidence,
            explanation=rule.explanation,
            verification=rule.verification,
            documentation_url=rule.documentation_url,
            evidence=("some log line",),
            line_number=1,
        )
        rendered = _render_findings([finding], "deploy.log", "github")
        assert ".." not in rendered, f"{rule.id} renders a doubled period"


def test_an_annotation_still_ends_its_verification_sentence(log: Path) -> None:
    # Removing the doubling must not remove the punctuation altogether for a rule
    # whose step happens not to end with any.
    from sam_doctor.cli import _render_findings
    from sam_doctor.diagnostics import Finding

    finding = Finding(
        rule_id="test.rule",
        title="A title",
        confidence="high",
        explanation="An explanation",
        verification=("Check the thing",),
        documentation_url="https://example.test/docs",
        evidence=("some log line",),
        line_number=3,
    )

    rendered = _render_findings([finding], "deploy.log", "github")

    assert "Check the thing. Docs:" in rendered
