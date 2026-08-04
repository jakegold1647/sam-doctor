#!/usr/bin/env bash

set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Could not find a Python interpreter (python or python3)." >&2
  exit 2
fi

: "${SAM_DOCTOR_LOG_FILE:?SAM_DOCTOR_LOG_FILE is required.}"
: "${SAM_DOCTOR_SUMMARY:=false}"
: "${SAM_DOCTOR_ANNOTATIONS:=true}"
: "${SAM_DOCTOR_BATCH:=false}"
: "${SAM_DOCTOR_FAIL_ON_FINDINGS:=false}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required.}"

if [ -z "${GITHUB_ACTION_PATH:-}" ]; then
  GITHUB_ACTION_PATH="$(cd "$(dirname "$0")/.." && pwd)"
fi

if [ -d "${GITHUB_ACTION_PATH}/src" ]; then
  PYTHONPATH="${GITHUB_ACTION_PATH}/src${PYTHONPATH:+:$PYTHONPATH}"
else
  PYTHONPATH="${GITHUB_ACTION_PATH}${PYTHONPATH:+:$PYTHONPATH}"
fi
export PYTHONPATH

if [[ "$SAM_DOCTOR_SUMMARY" != "true" && "$SAM_DOCTOR_SUMMARY" != "false" ]]; then
  echo "SAM_DOCTOR_SUMMARY must be 'true' or 'false'." >&2
  exit 2
fi

if [[ "$SAM_DOCTOR_ANNOTATIONS" != "true" && "$SAM_DOCTOR_ANNOTATIONS" != "false" ]]; then
  echo "SAM_DOCTOR_ANNOTATIONS must be 'true' or 'false'." >&2
  exit 2
fi

if [[ "$SAM_DOCTOR_BATCH" != "true" && "$SAM_DOCTOR_BATCH" != "false" ]]; then
  echo "SAM_DOCTOR_BATCH must be 'true' or 'false'." >&2
  exit 2
fi

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "true" && "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "false" ]]; then
  echo "SAM_DOCTOR_FAIL_ON_FINDINGS must be 'true' or 'false'." >&2
  exit 2
fi

report_path="$(mktemp)"
STEP_SUMMARY_CREATED=0
if [ -z "${GITHUB_STEP_SUMMARY:-}" ]; then
  GITHUB_STEP_SUMMARY="$(mktemp)"
  STEP_SUMMARY_CREATED=1
fi
trap '
  rm -f "$report_path"
  if [ "${STEP_SUMMARY_CREATED}" = "1" ]; then
    rm -f "$GITHUB_STEP_SUMMARY"
  fi
' EXIT

if ! "$PYTHON_BIN" -c "import sam_doctor.cli" >/dev/null 2>&1; then
  echo "Could not import local action package from ${GITHUB_ACTION_PATH}. Installing fallback." >&2
  if ! "$PYTHON_BIN" -m pip install --disable-pip-version-check -e "$GITHUB_ACTION_PATH"; then
    "$PYTHON_BIN" -m pip install --disable-pip-version-check --break-system-packages -e "$GITHUB_ACTION_PATH" || \
      exit 2
  fi
fi

if [[ "$SAM_DOCTOR_BATCH" == "true" ]]; then
  "$PYTHON_BIN" -m sam_doctor.cli batch "$SAM_DOCTOR_LOG_FILE" --format json --output "$report_path"
else
  "$PYTHON_BIN" -m sam_doctor.cli diagnose "$SAM_DOCTOR_LOG_FILE" --format json --output "$report_path"
fi

if [[ "$SAM_DOCTOR_BATCH" == "true" ]]; then
  finding_count="$("$PYTHON_BIN" -c 'import json,sys; payload=json.load(open(sys.argv[1], encoding="utf-8")); print(sum(result["finding_count"] for result in payload.get("results", [])))' "$report_path")"
else
  finding_count="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["finding_count"])' "$report_path")"
fi

if [[ ! "$finding_count" =~ ^[0-9]+$ ]]; then
  echo "Could not parse finding-count from JSON output: $finding_count" >&2
  exit 2
fi

echo "finding-count=${finding_count}" >> "$GITHUB_OUTPUT"
if [[ "$finding_count" -gt 0 ]]; then
  echo "has-findings=true" >> "$GITHUB_OUTPUT"
else
  echo "has-findings=false" >> "$GITHUB_OUTPUT"
fi

if [[ "$SAM_DOCTOR_SUMMARY" == "true" ]]; then
  "$PYTHON_BIN" - "$report_path" "$SAM_DOCTOR_BATCH" <<'PY' >> "$GITHUB_STEP_SUMMARY"
import json
import sys

from html import escape
from sam_doctor.diagnostics import Finding
from sam_doctor.cli import markdown_report


def write_summary(payload_path: str, is_batch: bool) -> None:
    payload = json.load(open(payload_path, encoding="utf-8"))

    def _as_findings(raw_findings: list[dict[str, object]]) -> list[Finding]:
        findings: list[Finding] = []
        for item in raw_findings:
            findings.append(
                Finding(
                    title=item["title"],
                    confidence=item["confidence"],
                    explanation=item["explanation"],
                    verification=tuple(item["verification"]),
                    documentation_url=item["documentation_url"],
                    evidence=tuple(item["evidence"]),
                    line_number=int(item["line_number"]),
                )
            )
        return findings

    if not is_batch:
        source = payload.get("source", "")
        findings = _as_findings(payload.get("findings", []))
        print(markdown_report(findings, source))
        return

    for result in payload.get("results", []):
        source = str(result.get("source", ""))
        findings = _as_findings(result.get("findings", []))
        print(f"## Source: <code>{escape(source)}</code>")
        print("")
        print(markdown_report(findings, source).rstrip())
        print("")


write_summary(sys.argv[1], sys.argv[2].lower() == "true")
PY
fi

if [[ "$SAM_DOCTOR_ANNOTATIONS" == "true" && "$finding_count" -gt 0 ]]; then
  "$PYTHON_BIN" - "$report_path" "$SAM_DOCTOR_BATCH" <<'PY'
import json
import sys

from sam_doctor.cli import _escape_github_command_property, _escape_github_command_value
from sam_doctor.redaction import redact


def emit_github_notices(payload: dict[str, object], is_batch: bool) -> None:
    if is_batch:
        results = payload.get("results", [])
        for item in results:
            source = str(item.get("source", ""))
            findings = item.get("findings", [])
            for finding in findings:
                _emit_notice(source, finding)
        return

    source = str(payload.get("source", ""))
    findings = payload.get("findings", [])
    for finding in findings:
        _emit_notice(source, finding)


def _emit_notice(source: str, finding: object) -> None:
    finding_dict = dict(finding)
    verification = finding_dict.get("verification", ["Review the documentation link."])[0]
    message = (
        f"{finding_dict.get('title', 'Deployment issue detected')}. Line "
        f"{finding_dict.get('line_number', 0)}: {verification}. "
        f"Docs: {finding_dict.get('documentation_url', 'about:blank')}"
    )
    escaped_source = _escape_github_command_property(redact(source))
    print(
        f"::notice file={escaped_source},line={finding_dict.get('line_number', 0)},title=SAM Doctor::"
        f"{_escape_github_command_value(message)}"
    )


report_path = sys.argv[1]
is_batch = sys.argv[2].lower() == "true"
payload = json.load(open(report_path, encoding="utf-8"))
emit_github_notices(payload, is_batch)
PY
fi

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" == "true" && "$finding_count" -gt 0 ]]; then
  echo "SAM Doctor found ${finding_count} supported issue(s)." >&2
  exit 1
fi
