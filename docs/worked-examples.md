# Worked examples

Three end-to-end examples showing how to run SAM Doctor on a real failure and
what to do with the output. Each starts from the smallest useful log excerpt.

## Blocked IAM OIDC role assumption (single incident)

**Situation**

- A deployment stopped with:

```text
Not authorized to perform: sts:AssumeRoleWithWebIdentity
```

**Steps**

1. Save the smallest useful excerpt as `deployment-failure.log`.
2. Run:

```bash
sam-doctor diagnose deployment-failure.log --format markdown
```

**Result**

SAM Doctor reports one finding first:

- *GitHub Actions cannot assume the configured AWS role through OIDC (high confidence)*
- Evidence line around the exact failure
- Verification step to confirm the `id-token: write` permission and OIDC trust-policy

The triage moves from "debug everywhere" to one targeted check, and a teammate
can run the same command and compare results.

Copy/paste handoff:

```text
Top finding: OIDC token trust mismatch
Verify: confirm workflow permissions include `id-token: write`
Next action: verify role trust `aud` and `sub` against GitHub OIDC claims
```

---

## Rollback noise hides the first failure

**Situation**

- CI shows a final stack state like `ROLLBACK_COMPLETE`.
- It is not obvious which resource failed first.

**Steps**

```bash
sam-doctor diagnose deployment.log --format json --output diagnosis.json
```

**Result**

SAM Doctor identifies the earliest actionable event and ranks the next check.

- It avoids chasing the rollback terminus.
- It points to the original create/update failure first.
- The report includes the exact command to verify before any cleanup or policy
  changes.

---

## Non-blocking CI diagnostics, then strict gating

**Situation**

- A team wants diagnostics in CI without changing failure behavior immediately.

**Steps**

1. Run SAM Doctor in non-blocking mode first:

```yaml
- name: Diagnose deployment log
  if: always()
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
    fail-on-findings: false
```

2. Review outputs from:

- Workflow summary
- `finding-count`
- `has-findings`

3. Once the high-confidence rules have proven reliable on your own logs, gate
   on them alone - medium-confidence findings still report but do not fail
   the job:

```yaml
fail-on-confidence: high
```

4. When the medium-confidence findings have also earned trust, switch to
   strict mode:

```yaml
fail-on-findings: true
```

**Result**

The change is incremental and reversible: diagnostics run on every deploy from
day one, and each tightening step is enabled only after the output has been
reviewed against real failures.

---

Related docs:

- [GitHub Actions integration](github-actions-integration.md)
- [On-call playbook](on-call-playbook.md)
