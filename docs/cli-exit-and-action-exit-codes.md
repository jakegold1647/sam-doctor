# CLI and GitHub Action exit behavior

SAM Doctor supports explicit, scriptable exit behavior so you can use it directly in
CI and local automation without guessing.

## CLI exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | Command completed successfully and no enforced fail gate was hit. |
| `1` | `--fail-on-findings` was used and one or more supported findings were found, or a finding met the `--fail-on-confidence` threshold. |
| `2` | CLI usage or runtime failure (missing input, invalid command path, invalid arguments, or other precondition failure). |

### Command-by-command behavior

- `sam-doctor diagnose`
  - Default: exits `0` even when findings exist.
  - `--fail-on-findings`: exits `1` if one or more findings are detected.
  - `--fail-on-confidence high` (or `medium`): exits `1` only when a finding at
    that confidence or above is detected. Reports still show every finding;
    when given, the threshold is the gate even if `--fail-on-findings` is also
    set.

- `sam-doctor batch`
  - Scans all provided inputs and reports all matches.
  - Default: exits `0` even when findings exist.
  - `--fail-on-findings`: exits `1` if any file has at least one finding.
  - `--fail-on-confidence high` (or `medium`): exits `1` only when any file has
    a finding at that confidence or above.

- `sam-doctor packet`
  - Returns evidence packets and exits `0` when files are readable and report writes succeed.

- `sam-doctor request-packet`
  - Writes a small, sanitized excerpt for a rule request and exits `0`, whether or not a
    likely error line was found. Exits `2` on a read/write failure (for example, empty stdin).

- `sam-doctor init`, `demo`, `rules`
  - Exit `0` on successful command execution.

Use these codes with shell CI gates, for example:

```bash
sam-doctor diagnose deployment.log --format json --output diagnosis.json --fail-on-findings
```

## GitHub Action behavior

The Action wraps the CLI and exposes three stable outputs:

- `finding-count`: total supported findings for all scanned inputs.
- `has-findings`: `true` if `finding-count` is greater than `0`.
- `sam-doctor-version`: version string used by the action run.

Action exit behavior:

| Exit code | Meaning |
| --- | --- |
| `0` | Action run succeeded and no enforced action-level failure occurred. |
| `1` | `fail-on-findings: true` and findings were detected, or a finding met the `fail-on-confidence` threshold. |
| `2` | Runtime/precondition failure (invalid inputs, missing Python, or internal CLI command failure). |

Example non-blocking routing:

```yaml
- name: Diagnose deployment log
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true

- name: Route only when findings exist
  if: steps.sam-doctor.outputs.has-findings == 'true'
  run: |
    echo "Routing ${{ steps.sam-doctor.outputs.finding-count }} findings to triage."
```

Use `fail-on-findings: true` only after you have observed stable behavior in a few
non-blocking runs. For a gentler rollout, gate on high confidence first:

```yaml
- name: Diagnose deployment log
  if: always()
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    fail-on-confidence: high
```

Medium-confidence findings still show up in the report and annotations; they
just do not fail the job until you tighten the threshold to `medium` (or switch
to `fail-on-findings: true`).
