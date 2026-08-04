# SAM Doctor case studies

These examples show concrete, production-like flows with the minimal excerpt you
need to send.

## Case study: blocked IAM OIDC role assumption (single incident)

**Situation**

- A deployment stopped with:

```text
Not authorized to perform: sts:AssumeRoleWithWebIdentity
```

**Action**

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

**Why this converts**

- The triage moves from “debug everywhere” to one targeted check.
- A teammate can run the same flow and report one concrete verification command.

Copy/paste handoff:

```text
Top finding: OIDC token trust mismatch
Verify: confirm workflow permissions include `id-token: write`
Next action: verify role trust `aud` and `sub` against GitHub OIDC claims
```

---

## Case study: rollback noise hides first failure

**Situation**

- CI shows a final stack state like `ROLLBACK_COMPLETE`.
- The team can’t quickly identify which resource failed first.

**Action**

```bash
sam-doctor diagnose deployment.log --format json --output diagnosis.json
```

**Result**

SAM Doctor identifies the earliest actionable event and ranks the next check.

- It avoids chasing the rollback terminus.
- It points to the original create/update failure first.

**Why this converts**

- Incident threads move from speculation to a single reviewable finding.
- The report provides the exact command to verify before any cleanup or policy
  changes.

---

## Case study: team pilot with non-blocking gating

**Situation**

- A team wants diagnostics in CI without changing failure behavior immediately.

**Action**

1. Run SAM Doctor in non-blocking mode for a short pilot:

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

3. After 1–2 stable weeks, switch to strict mode:

```yaml
fail-on-findings: true
```

**Result**

The team builds trust in the tool’s signal quality before converting to an enforced
gate.

**Why this converts**

- Adoption becomes incremental, reversible, and safe.
- Product value is proven in the team’s own incident stream before full rollout.

---

Pair this with the rollout docs:

- [Adopter onboarding kit](adopter-onboarding-kit.md)
- [First-3 teams onboarding playbook](first-3-teams-onboarding-playbook.md)
- [Community sharing kit](community-sharing-kit.md)
