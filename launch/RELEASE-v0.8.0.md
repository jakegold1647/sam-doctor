# SAM Doctor v0.8.0

SAM Doctor v0.8.0 grows the rule catalog from 31 to 37 diagnoses and adds
context-aware IAM denial reporting. New rules cover empty change sets, split
explicit/implicit IAM denials (including service control policies), resource
stabilization timeouts, in-use stack exports, and Lambda package size limits -
that last one contributed by a first-time contributor in #34. `python -m
sam_doctor` now works, and contributors get a one-command local gate
(`scripts/check-pr.py`) that mirrors CI.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Marketplace Action with `jakegold1647/sam-doctor@v0.8.0`.
- Use `--fail-on-findings` only when a supported diagnosis should fail a CI job.
- Reports remain local, redacted, and evidence-first.
