# Researcher evidence packet (sanitized)

Use this when you need a repeatable artifact for collaboration, reviews, or
research discussion.

## 1) Capture a reproducible packet

```bash
sam-doctor packet deployment.log

# If working in a repo checkout:
python scripts/export-evidence-packet.py deployment.log
```

Set `SOURCE_DATE_EPOCH` to a non-negative Unix timestamp when packet files must
be byte-identical across reruns. The generated UTC timestamp in both evidence
packets and rule-request excerpts will use that pinned value.

## 2) Build a reusable packet

You can move artifacts for sharing as needed:

```bash
cp artifacts/diagnosis.md artifacts/diagnosis.json artifacts/researcher-notes.md /your/shared/location/
```

## 3) Share safely

- Never share raw logs.
- The packet is visibly marked as redacted and removes common account IDs, ARNs,
  access keys, session tokens, emails, private URLs, and user-home paths.
- Share only `artifacts/researcher-notes.md`, `diagnosis.json`, and the top
  matching excerpt in `diagnosis.md`; review each file before posting it.
- Read the [support boundaries](../SUPPORT.md) before asking for help, or use the
  [usage feedback form](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml)
  to share a safe result, miss, or unclear report.

This packet is intentionally small, reproducible, and safe to discuss in:

- researcher notes and reading groups,
- OSS issue threads,
- internal postmortems,
- reproducibility discussions.

For role-specific commands when setting this up on a team, see
[team-rollout.md](team-rollout.md).

## No matching rule?

If `sam-doctor diagnose` reports no supported pattern, don't paste the whole
log into a rule request. `sam-doctor request-packet deployment.log` writes a
single redacted file with a short context window around the first likely
error, the command you ran, and a link to the rule request template:

```bash
sam-doctor request-packet deployment.log
```

Same rule as everywhere else: review the excerpt yourself before sharing it.

## Short before-and-after example

Input evidence can contain a local checkout path:

```text
Error: Not authorized to perform: sts:AssumeRoleWithWebIdentity at C:\Users\alice\acme-private\template.yaml
```

The shared report preserves the failure wording but replaces the local path with
`[REDACTED_PRIVATE_PATH]`. Relative paths such as
`scripts/build-site-rule-catalog.py` stay visible because they are often useful
for reproducing the command without naming a user or private checkout.
