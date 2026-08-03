# SAM Doctor v0.3.0

SAM Doctor v0.3.0 adds more transparent coverage for the failure patterns that
most often hide useful evidence in long deployment logs.

## Highlights

- Inspect current coverage before sharing a log with `sam-doctor rules`.
- Try a bundled failed-resource example with `sam-doctor demo --scenario cloudformation`.
- Get a direct high-confidence finding for CloudFormation `CREATE_FAILED` and
  `UPDATE_FAILED` events, before a later rollback entry obscures the first failure.
- Keep evidence safer with masking for common key, token, password, and
  session-token assignments.
- Avoid treating a generic `InvalidIdentityToken` as proof of an OIDC audience mismatch.

## Try it

```bash
python -m pip install "sam-doctor @ git+https://github.com/jakegold1647/sam-doctor.git@v0.3.0"
sam-doctor demo --scenario cloudformation
```

The free alpha remains local-only: it does not access AWS, upload logs, or make
changes to infrastructure. Feedback is most useful as a short, sanitized first
error and the next check that would have saved time.
