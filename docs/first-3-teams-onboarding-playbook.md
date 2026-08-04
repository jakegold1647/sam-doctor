# First-3 teams onboarding playbook

Use this playbook when you want 3 initial teams to adopt SAM Doctor with low friction
and minimal noise.

## Day 0 (30 minutes): unblock one deployment failure

1. Install and run once:

```bash
python -m pip install sam-doctor
python scripts/run-smoke.py
```

2. For each test failure family in your organization, run:

```bash
sam-doctor diagnose deployment.log --format markdown
```

3. Send this one-thread format:

```text
I ran @sam-doctor on the failing excerpt.
Finding: [top finding]
Evidence: [top evidence line]
Safety check: [one command or doc link]
Next step: [one action]
```

## Week 1: onboard Team A (on-call + one owner)

- Add one diagnosis step after your deploy step (`if: always()`).
- Keep `fail-on-findings: false` for the first 3 deploys.
- Capture and share only:
  - top finding title
  - first verification command
  - a sanitized excerpt line
- Ask:
  - “Did the suggested verification match the incident outcome?”

## Week 2: onboard Team B (SRE/DevOps)

- Copy the same workflow shape into their CI.
- Start one non-blocking dashboard report:
  - summarize findings per day in a team note
  - no ticket creation until two repeated supported findings are confirmed
- Enable strict gating only if Team A has validated stable behavior:
  - `fail-on-findings: true`

## Week 3: onboard Team C (platform/reviewer)

- Adopt the packet workflow for reproducible sharing:

```bash
sam-doctor packet deployment.log --output-dir artifacts/team-c-onboarding
```

- Share only:
  - `artifacts/diagnosis.md`
  - `artifacts/diagnosis.json`
  - `artifacts/researcher-notes.md`
- If a real miss or unsafe output appears, file a report with a sanitized excerpt.

## Copy/paste announcement templates

### Slack/Teams first touch

```text
I'm piloting SAM Doctor for deployment triage. If we can run one diagnose on a live
deployment excerpt first, we usually get: top finding, safe next check, and a redacted
shareable output.
```

### Second touch

```text
Try command: sam-doctor diagnose deployment.log --format markdown
If your failure is OIDC, rollback noise, or capability-related, this is often the fastest first pass.
```

### Third touch (with decision)

```text
If this helps your failure loop, we can add one strict gate step (`fail-on-findings: true`)
after a short warm-up.
```

## Success criteria before expanding beyond 3 teams

- At least 2 of 3 teams have run at least one real on-call or incident case with SAM
  Doctor.
- At least 2 of 3 teams have run `sam-doctor packet` at least once and can share
  one sanitized packet.
- There are no recurring raw-log leaks in team handoffs.

If not, pause and fix the first friction point before next promotion step.
