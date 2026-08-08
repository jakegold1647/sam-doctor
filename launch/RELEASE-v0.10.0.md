# SAM Doctor v0.10.0

Two new diagnostic rules and a redaction hardening pass. The catalog is now
46 rules, every one of them backed by a positive/negative fixture pair and a
dedicated error-reference page, both enforced in CI.

The redaction fix is the one to read: `aws sts assume-role` prints its
credentials as CamelCase JSON keys (`"SecretAccessKey"`, `"SessionToken"`),
and the assignment pattern only recognized the underscore spellings - so a
pasted assume-role response could carry the real secret key into a report.
That shape is covered now, along with presigned-URL signatures, Slack tokens,
and PEM private-key blocks.

New rules:

- The deployment ran with invalid or wrong-account AWS credentials
  (`UnrecognizedClientException`), kept distinct from expired credentials.
- A stack stuck in `UPDATE_ROLLBACK_FAILED`, where the rollback itself failed
  and needs `continue-update-rollback`.

Also in this release: every rule now has an error-reference page on the
website (the drift gate requires one), the rollout guidance walks teams up
the confidence gate rather than jumping to strict mode, and the determinism
and CRLF-input promises have direct tests.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Marketplace Action with `jakegold1647/sam-doctor@v0.10.0`.
- Match on `rule_id` in JSON and SARIF output, not on titles - see
  `docs/stability.md`.
- Reports remain local, redacted, and evidence-first. Redaction is a
  guardrail, not a secret scanner: review a report before sharing it.
