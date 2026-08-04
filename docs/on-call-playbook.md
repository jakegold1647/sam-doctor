# SAM Doctor on-call playbook

Use this once per incident and reuse the same sequence for predictable speed.

## 60-second triage

1. Capture the failing log chunk (full log or pasted error excerpt).
2. Run:

```bash
sam-doctor diagnose deployment.log --format markdown
```

3. Share one finding plus one verification command.
4. Re-run deploy only after verification passes.

## Copy/paste for Slack/Teams

```text
I ran SAM Doctor on the attached failure excerpt.
- Finding: [copy top finding]
- Confidence: [high|med|low]
- Evidence: [copy first evidence line]
- Suggested check: [copy first verification command]
- Next step: [one concrete action]
```

## Failure type checklist

### OIDC / AssumeRoleWithWebIdentity
- Verify `id-token: write` in workflow/job permissions.
- Confirm trust-policy subject and audience.
- Re-run with `sam deploy --no-confirm-changeset` after update.

### CloudFormation rollback
- Ignore `ROLLBACK_COMPLETE` itself.
- Fix the first non-rollback failed resource.
- Re-run deploy only after that dependency issue is addressed.

### Capability errors
- Confirm whether IAM changes are intentional.
- Re-run with the required `CAPABILITY_*` flag.

## Escalation rule

Only escalate to platform/team lead when:

- SAM Doctor returns `no supported finding` and there is no obvious infra clue,
  or
- The same failure appears after applying the first verified command twice.

## Safe output guardrails

- Do not include raw account IDs, ARNs, keys, or tokens in team threads.
- Use the sanitized excerpt mode whenever possible.
