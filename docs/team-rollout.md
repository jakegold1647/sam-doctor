# Rolling out SAM Doctor on a team

Ready-to-run commands by role, plus a short checklist for putting SAM Doctor
into a team's CI without changing failure behavior on day one.

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
- You hit a **failure family SAM Doctor does not cover**:
  open a [rule request issue](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)
  with the sanitized excerpt and command family.

## 2) Commands by role

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

To generate the exact workflow in one step:

```bash
sam-doctor init \
  --deploy-command "sam deploy --no-confirm-changeset" \
  --annotations \
  --summary
```

When ready for strict mode:

```bash
sam-doctor init \
  --deploy-command "sam deploy --no-confirm-changeset" \
  --annotations \
  --summary \
  --fail-on-findings \
  --force
```

For multi-log workflows, generate batch mode with `--batch` and then point the
generated `log-file` at `logs/` or a glob.

### C) Team lead / reviewer

Use this output pack for every incident handoff:

```bash
sam-doctor diagnose deployment.log --format markdown > diagnosis.md
sam-doctor diagnose deployment.log --format json --output diagnosis.json
sam-doctor packet deployment.log
```

Share only sanitized outputs, never full raw logs.

### D) Researcher

Provide reproducibility and controls:

```bash
sam-doctor diagnose deployment.log --output artifacts/diagnosis.json --format json
sam-doctor diagnose deployment.log --format markdown > artifacts/diagnosis.md
sam-doctor packet deployment.log
```

Pair with `docs/researcher-evidence-packet.md` if writing for publication or review.

### E) Platform engineer setting this up

Run a smoke check first:

```bash
python scripts/run-smoke.py
```

Then have one or two other engineers run the same command on a non-sensitive
failure and compare output.

## 3) Rollout checklist

- [ ] Run `python scripts/run-smoke.py` on a clean machine
- [ ] Add the starter workflow to one active pipeline, non-blocking
- [ ] Run one real incident through it and produce a packet
- [ ] Share only sanitized outputs in handoffs
- [ ] File a rule request if a real non-covered failure appears
- [ ] Enable `fail-on-findings: true` only after 2-3 stable runs

## 4) Safe sharing reminder

Never include:

- account IDs
- ARNs
- secrets
- full raw logs

See the [worked examples](worked-examples.md) for full incident flows,
including the non-blocking-to-strict gating sequence.
