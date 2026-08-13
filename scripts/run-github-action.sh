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
: "${SAM_DOCTOR_RUN_COMMAND:=}"
: "${SAM_DOCTOR_SUMMARY:=false}"
: "${SAM_DOCTOR_ANNOTATIONS:=true}"
: "${SAM_DOCTOR_BATCH:=false}"
: "${SAM_DOCTOR_FAIL_ON_FINDINGS:=false}"
: "${SAM_DOCTOR_FAIL_ON_CONFIDENCE:=}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required.}"

# A runner can inherit TMPDIR from a parent shell even when that directory is
# not mounted in the action environment. Let mktemp use its platform default
# instead of failing before SAM Doctor can read the supplied log.
if [ -n "${TMPDIR:-}" ] && [ ! -d "$TMPDIR" ]; then
  unset TMPDIR
fi

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

if [[ -n "${SAM_DOCTOR_RUN_COMMAND//[[:space:]]/}" && "$SAM_DOCTOR_BATCH" == "true" ]]; then
  echo "SAM_DOCTOR_RUN_COMMAND cannot be combined with SAM_DOCTOR_BATCH=true." >&2
  exit 2
fi

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "true" && "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "false" ]]; then
  echo "SAM_DOCTOR_FAIL_ON_FINDINGS must be 'true' or 'false'." >&2
  exit 2
fi

if [[ -n "$SAM_DOCTOR_FAIL_ON_CONFIDENCE" && "$SAM_DOCTOR_FAIL_ON_CONFIDENCE" != "high" && "$SAM_DOCTOR_FAIL_ON_CONFIDENCE" != "medium" ]]; then
  echo "SAM_DOCTOR_FAIL_ON_CONFIDENCE must be empty, 'high', or 'medium'." >&2
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

deploy_status=0
if [[ -n "${SAM_DOCTOR_RUN_COMMAND//[[:space:]]/}" ]]; then
  # The CLI owns capture safety and streams the command's combined output. The
  # command is workflow-authored input, so run it through the runner's Bash
  # exactly as a normal `run:` block would be executed.
  set +e
  "$PYTHON_BIN" -m sam_doctor.cli run \
    --log-file "$SAM_DOCTOR_LOG_FILE" \
    --format json \
    --output "$report_path" \
    -- bash -lc "$SAM_DOCTOR_RUN_COMMAND"
  deploy_status=$?
  set -e

  # Successful commands intentionally produce no failure report. Diagnose the
  # captured log once so the action still exposes a stable zero-finding payload.
  if [[ ! -s "$report_path" ]]; then
    set +e
    "$PYTHON_BIN" -m sam_doctor.cli diagnose "$SAM_DOCTOR_LOG_FILE" \
      --format json --output "$report_path"
    diagnose_status=$?
    set -e
    if [[ "$diagnose_status" -ne 0 ]]; then
      echo "Could not create the Action report after running the deployment command." >&2
      if [[ "$deploy_status" -ne 0 ]]; then
        exit "$deploy_status"
      fi
      exit 2
    fi
  fi
elif [[ "$SAM_DOCTOR_BATCH" == "true" ]]; then
  "$PYTHON_BIN" -m sam_doctor.cli batch "$SAM_DOCTOR_LOG_FILE" --format json --output "$report_path"
else
  "$PYTHON_BIN" -m sam_doctor.cli diagnose "$SAM_DOCTOR_LOG_FILE" --format json --output "$report_path"
fi

if [[ "$SAM_DOCTOR_BATCH" == "true" ]]; then
  finding_count="$("$PYTHON_BIN" -c 'import json,sys; payload=json.load(open(sys.argv[1], encoding="utf-8")); print(sum(result["finding_count"] for result in payload.get("results", [])))' "$report_path")"
  report_version="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["sam_doctor_version"])' "$report_path")"
else
  finding_count="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["finding_count"])' "$report_path")"
  report_version="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["sam_doctor_version"])' "$report_path")"
fi

if [[ ! "$finding_count" =~ ^[0-9]+$ ]]; then
  echo "Could not parse finding-count from JSON output: $finding_count" >&2
  exit 2
fi
if [[ -z "$report_version" ]]; then
  echo "Could not parse sam_doctor_version from JSON output." >&2
  exit 2
fi

echo "finding-count=${finding_count}" >> "$GITHUB_OUTPUT"
echo "sam-doctor-version=${report_version}" >> "$GITHUB_OUTPUT"
echo "deploy-exit-status=${deploy_status}" >> "$GITHUB_OUTPUT"
if [[ "$finding_count" -gt 0 ]]; then
  echo "has-findings=true" >> "$GITHUB_OUTPUT"
else
  echo "has-findings=false" >> "$GITHUB_OUTPUT"
fi

if [[ "$SAM_DOCTOR_SUMMARY" == "true" ]]; then
  "$PYTHON_BIN" - "$report_path" "$SAM_DOCTOR_BATCH" "$SAM_DOCTOR_LOG_FILE" <<'PY' >> "$GITHUB_STEP_SUMMARY"
import json
import os
import sys

from html import escape
from sam_doctor.diagnostics import Finding
from sam_doctor.cli import _decode_log_bytes, markdown_report


def _source_is_empty(source: str) -> bool:
    """Whether the diagnosed log had no content to read.

    The summary is rebuilt from the JSON payload, which reports zero findings
    for an empty log and for an unrecognized one alike. The wrapper runs on the
    same machine as the log, so it can tell the two apart by looking. Anything
    past a few kilobytes is content by definition, which keeps a large log from
    being read a second time.
    """

    try:
        if os.path.getsize(source) > 4096:
            return False
        with open(source, "rb") as handle:
            return not _decode_log_bytes(handle.read()).strip()
    except OSError:
        return False


def write_summary(payload_path: str, is_batch: bool, log_file: str) -> None:
    payload = json.load(open(payload_path, encoding="utf-8"))

    def _as_findings(raw_findings: list[dict[str, object]]) -> list[Finding]:
        findings: list[Finding] = []
        for item in raw_findings:
            findings.append(
                Finding(
                    rule_id=str(item.get("rule_id", "")),
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
        empty = not findings and _source_is_empty(log_file)
        print(markdown_report(findings, source, input_is_empty=empty))
        return

    for result in payload.get("results", []):
        source = str(result.get("source", ""))
        findings = _as_findings(result.get("findings", []))
        empty = not findings and _source_is_empty(source)
        print(f"## Source: <code>{escape(source)}</code>")
        print("")
        print(markdown_report(findings, source, input_is_empty=empty).rstrip())
        print("")


write_summary(sys.argv[1], sys.argv[2].lower() == "true", sys.argv[3])
PY
fi

if [[ "$SAM_DOCTOR_ANNOTATIONS" == "true" && "$finding_count" -gt 0 ]]; then
  "$PYTHON_BIN" - "$report_path" "$SAM_DOCTOR_BATCH" <<'PY'
import json
import sys

from sam_doctor.cli import github_notices_from_payload

payload = json.load(open(sys.argv[1], encoding="utf-8"))
is_batch = sys.argv[2].lower() == "true"
notices = github_notices_from_payload(payload, is_batch)
if notices:
    print(notices, end="")
PY
fi

# A wrapped deployment owns the workflow status. The report, summary, and
# annotations above are still emitted, but an advisory gate must not replace a
# real deploy failure with status 1 or 2.
if [[ -n "${SAM_DOCTOR_RUN_COMMAND//[[:space:]]/}" && "$deploy_status" -ne 0 ]]; then
  exit "$deploy_status"
fi

if [[ -n "$SAM_DOCTOR_FAIL_ON_CONFIDENCE" ]]; then
  # The threshold is its own opt-in gate: count findings at or above it and
  # fail on those alone, so reports keep showing everything.
  gated_count="$("$PYTHON_BIN" - "$report_path" "$SAM_DOCTOR_BATCH" "$SAM_DOCTOR_FAIL_ON_CONFIDENCE" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
is_batch = sys.argv[2].lower() == "true"
rank = {"low": 0, "medium": 1, "high": 2}
threshold = rank[sys.argv[3]]
if is_batch:
    findings = [f for result in payload.get("results", []) for f in result.get("findings", [])]
else:
    findings = payload.get("findings", [])
print(sum(1 for f in findings if rank.get(f.get("confidence"), 0) >= threshold))
PY
)"
  if [[ "$gated_count" -gt 0 ]]; then
    echo "SAM Doctor found ${gated_count} issue(s) at ${SAM_DOCTOR_FAIL_ON_CONFIDENCE} confidence or above." >&2
    exit 1
  fi
elif [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" == "true" && "$finding_count" -gt 0 ]]; then
  echo "SAM Doctor found ${finding_count} supported issue(s)." >&2
  exit 1
fi
