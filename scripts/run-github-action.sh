#!/usr/bin/env bash

set -euo pipefail

: "${SAM_DOCTOR_LOG_FILE:?SAM_DOCTOR_LOG_FILE is required.}"
: "${SAM_DOCTOR_SUMMARY:=false}"
: "${SAM_DOCTOR_FAIL_ON_FINDINGS:=false}"
: "${GITHUB_ACTION_PATH:?GITHUB_ACTION_PATH is required.}"
: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required.}"

if [[ "$SAM_DOCTOR_SUMMARY" != "true" && "$SAM_DOCTOR_SUMMARY" != "false" ]]; then
  echo "SAM_DOCTOR_SUMMARY must be 'true' or 'false'." >&2
  exit 2
fi

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "true" && "$SAM_DOCTOR_FAIL_ON_FINDINGS" != "false" ]]; then
  echo "SAM_DOCTOR_FAIL_ON_FINDINGS must be 'true' or 'false'." >&2
  exit 2
fi

report_path="$(mktemp)"
trap 'rm -f "$report_path"' EXIT

python -m pip install --disable-pip-version-check "$GITHUB_ACTION_PATH"
sam-doctor diagnose "$SAM_DOCTOR_LOG_FILE" --format json --output "$report_path"

finding_count="$(python - "$report_path" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as report_file:
    print(json.load(report_file)["finding_count"])
PY
)"

echo "finding-count=${finding_count}" >> "$GITHUB_OUTPUT"
if [[ "$finding_count" -gt 0 ]]; then
  echo "has-findings=true" >> "$GITHUB_OUTPUT"
else
  echo "has-findings=false" >> "$GITHUB_OUTPUT"
fi

if [[ "$SAM_DOCTOR_SUMMARY" == "true" ]]; then
  sam-doctor diagnose "$SAM_DOCTOR_LOG_FILE" --format markdown >> "$GITHUB_STEP_SUMMARY"
fi

if [[ "$SAM_DOCTOR_FAIL_ON_FINDINGS" == "true" && "$finding_count" -gt 0 ]]; then
  echo "SAM Doctor found ${finding_count} supported issue(s)." >&2
  exit 1
fi
