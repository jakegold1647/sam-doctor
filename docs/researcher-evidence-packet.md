# Researcher evidence packet (sanitized)

Use this when you need a repeatable artifact for collaboration, reviews, or
research discussion.

## 1) Capture a reproducible packet

```bash
python scripts/export-evidence-packet.py deployment.log
```

## 2) Build a reusable packet

You can move artifacts for sharing as needed:

```bash
cp artifacts/diagnosis.md artifacts/researcher-notes.md ... /your/shared/location/
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
