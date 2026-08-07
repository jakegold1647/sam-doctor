# Researcher evidence packet (sanitized)

Use this when you need a repeatable artifact for collaboration, reviews, or
research discussion.

## 1) Capture a reproducible packet

```bash
sam-doctor packet deployment.log

# If working in a repo checkout:
python scripts/export-evidence-packet.py deployment.log
```

## 2) Build a reusable packet

You can move artifacts for sharing as needed:

```bash
cp artifacts/diagnosis.md artifacts/diagnosis.json artifacts/researcher-notes.md /your/shared/location/
```

## 3) Share safely

- Never share raw logs.
- Strip account IDs, ARNs, access keys, session tokens, emails, and private URLs.
- Share only `artifacts/researcher-notes.md`, `diagnosis.json`, and the top
  matching excerpt in `diagnosis.md`.

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
