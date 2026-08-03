#!/usr/bin/env bash

set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Could not find a Python interpreter (python3 or python)." >&2
  exit 2
fi

: "${SAM_DOCTOR_LOG_FILE:?SAM_DOCTOR_LOG_FILE is required.}"
: "${SAM_DOCTOR_SUMMARY:=false}"
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

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "true" && "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "false" ]]; then
  echo "SAM_DOCTOR_FAIL_ON_FINDINGS must be 'true' or 'false'." >&2
  exit 2
fi

STEP_SUMMARY_CREATED=0
if [ -z "${GITHUB_STEP_SUMMARY:-}" ]; then
  GITHUB_STEP_SUMMARY="$(mktemp)"
  STEP_SUMMARY_CREATED=1
fi

report_path="$(mktemp)"
trap '
  rm -f "$report_path"
  if [ "$STEP_SUMMARY_CREATED" = "1" ]; then
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

"$PYTHON_BIN" -m sam_doctor.cli diagnose "$SAM_DOCTOR_LOG_FILE" --format json --output "$report_path"

finding_count="$($PYTHON_BIN -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["finding_count"])' "$report_path")"

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
  "$PYTHON_BIN" -m sam_doctor.cli diagnose "$SAM_DOCTOR_LOG_FILE" --format markdown >> "$GITHUB_STEP_SUMMARY"
fi

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" == "true" && "$finding_count" -gt 0 ]]; then
  echo "SAM Doctor found ${finding_count} supported issue(s)." >&2
  exit 1
fi
