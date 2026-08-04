# SAM Doctor adopter onboarding kit

Use this when sharing SAM Doctor with a new team, community, or partner.
It gives ready-to-run commands by role and a one-thread handoff template.

## 1) 20-second decision path

- You have a **deployment log file**:
  `sam-doctor diagnose deployment.log --format markdown`
- You use **GitHub Actions for deploys**:
  add the [starter workflow](../examples/github-actions-workflow.yml) from docs or run:

  ```bash
  sam-doctor init
  ```
- You need **CI-safe machine output**:
  `sam-doctor diagnose deployment.log --format json --output diagnosis.json`
- You need a **review-ready packet**:
  `sam-doctor packet deployment.log`
- You are evaluating a **new failure family**:
  open a [rule request issue](https://github.com/jakegold1647/sam-doctor/issues/new?title=Rule%20request:%20new%20failure%20family&labels=rule-request)
  with the sanitized excerpt and command family.

## 2) Team-specific command set

### A) On-call engineer

Paste one short excerpt into a ticket:

```bash
sam-doctor diagnose deployment.log --format markdown
```

Reply with exactly:

1. Top finding title
2. First verification command from the report
3. One follow-up question: "did this check pass?"

### B) SRE / DevOps owner

Add this in CI immediately after deploy writes logs:

```yaml
- name: Diagnose deployment log
  if: always()
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
```

Keep non-blocking initially (`fail-on-findings: false`), then switch to strict
gating after 2-3 stable runs.

### C) Team lead / reviewer

Use this output pack for every incident handoff:

```bash
sam-doctor diagnose deployment.log --format markdown > diagnosis.md
sam-doctor diagnose deployment.log --format json --output diagnosis.json
sam-doctor packet deployment.log
```

Share only sanitized outputs, never full raw logs.

### D) Research partner

Provide reproducibility and controls:

```bash
sam-doctor diagnose deployment.log --output artifacts/diagnosis.json --format json
sam-doctor diagnose deployment.log --format markdown > artifacts/diagnosis.md
sam-doctor packet deployment.log
```

Pair with `docs/researcher-evidence-packet.md` if writing for publication or review.

### E) Platform engineer introducing SAM Doctor

Use a smoke check before announcing:

```bash
python scripts/run-smoke.py
```

Then ask two adopters to run the same command on a non-sensitive failure.

## 3) Shareable one-thread message template

```text
Trying SAM Doctor on a live failure:
- Finding: [top finding title]
- Verified: [safe follow-up command]
- Result: [pass/fail]
- Next: [one exact action]

If this matches your failure family, we can add a tailored starter workflow in 10 minutes.
```

## 4) Outreach-ready 3-message sequence

1. **Starter post (first touch)**  
   "I'm sharing a quick OSS tool for deterministic AWS deployment triage:
   SAM Doctor. You can install in 60s and get one redacted, actionable finding from a deployment log."

2. **How it works (second touch)**  
   "Run `sam-doctor diagnose deployment.log --format markdown`, add one follow-up check, then proceed."

3. **Proof + invite (third touch)**  
   "I can share the exact starter for GitHub Actions / your CI system and a copy/paste issue template for your first rule request."

## 5) 5-minute rollout checklist

- [ ] Run `python scripts/run-smoke.py` on a clean machine
- [ ] Add starter to one active workflow
- [ ] Run one real incident and produce a packet
- [ ] Share only sanitized outputs in handoff
- [ ] File one rule request if a real non-covered failure appears
- [ ] Link to the ecosystem context (`RESEARCHER_OVERVIEW.md`, `docs/researcher-evidence-packet.md`)

## 6) Safe sharing reminder

Never include:

- account IDs
- ARNs
- secrets
- full raw logs

The same workflow that helps adoption also protects privacy and makes the tool credible in external collaboration.
