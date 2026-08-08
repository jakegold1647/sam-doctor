"""Determinism is a stated product claim, so it gets its own tests.

The README promises identical output for identical input, and Windows support
means CRLF-captured logs are a first-class input shape - a finding must not
move or change because a runner wrote \r\n.
"""

from __future__ import annotations

from pathlib import Path

from sam_doctor.cli import _render_findings
from sam_doctor.diagnostics import diagnose

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "src" / "sam_doctor" / "data"

FORMATS = ("terminal", "markdown", "json", "github", "sarif")


def _composite_log() -> str:
    return "\n".join(
        sample.read_text(encoding="utf-8")
        for sample in sorted(SAMPLES_DIR.glob("*.txt"))
    )


def test_every_format_is_byte_identical_across_runs() -> None:
    text = _composite_log()
    first = {
        fmt: _render_findings(diagnose(text), "composite.log", fmt)
        for fmt in FORMATS
    }
    second = {
        fmt: _render_findings(diagnose(text), "composite.log", fmt)
        for fmt in FORMATS
    }
    assert first == second


def test_crlf_input_produces_the_same_findings_as_lf() -> None:
    text = _composite_log()
    lf_findings = diagnose(text)
    crlf_findings = diagnose(text.replace("\n", "\r\n"))

    assert [f.rule_id for f in lf_findings] == [f.rule_id for f in crlf_findings]
    assert [f.line_number for f in lf_findings] == [
        f.line_number for f in crlf_findings
    ]
    assert [f.evidence for f in lf_findings] == [f.evidence for f in crlf_findings]


def test_finding_order_follows_first_matching_line() -> None:
    text = _composite_log()
    findings = diagnose(text)
    assert findings, "the composite of bundled samples must produce findings"
    assert [f.line_number for f in findings] == sorted(
        f.line_number for f in findings
    )
