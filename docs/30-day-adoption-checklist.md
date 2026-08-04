# 30-day SAM Doctor adoption checklist

Run this once your team is ready to standardize fast, low-risk deployment
triage. Use the structure as a planning issue in your internal tracker.

## Before starting

- Choose one deployment failure class to start (for example OIDC, rollback, or
  capability failures).
- Pick one repo or service as the pilot target.
- Confirm one SME can approve the rollout and one on-call engineer can own the weekly
  review.

## Week 1: baseline and local trust

- Install SAM Doctor and run locally on one failing failure snippet.
- Add one non-blocking CI step with `summary: true` and `fail-on-findings: false`.
- Agree on report-sharing format (`finding`, `verify`, `next action`) in a handoff.
- Track first 5 incidents in a simple table.

```text
Date | Context | Finding | Verification command | Result | Follow-up
```

## Week 2: team rollout

- Enable SAM Doctor in one on-call channel or service team.
- Add one non-blocking `sam-doctor` check in every incident runbook.
- Add one automation rule for follow-up routing when `has-findings == 'true'`.
- Ask for one feedback entry per adopter and archive it.

## Week 3: signal hardening

- Review all false positives and unclear findings; create rule requests for strong gaps.
- Tighten the rollout path to one preferred log capture pattern.
- Run at least 10 real incidents through the same command sequence.
- Add `community-sharing-kit` templates if outcomes are stable.

## Week 4: enforcement decision

- Compare finding quality across teams/owners.
- If quality is stable, switch pilot jobs to `fail-on-findings: true`.
- Keep one low-friction manual path for incidents where findings are not supported.
- Publish one concise internal case note for each high-signal rule added.

## Completion gate

Move to enterprise rollout only when all conditions are met for 2 consecutive weeks:

- <1 false-positive triage loop per 10 incidents.
- 100% of team incidents using one shared handoff template.
- At least one reviewer confirms reproducibility and evidence quality.

Use this template in GitHub Issues as:  
`30-day adoption checklist` (starter issue body below in the template).
