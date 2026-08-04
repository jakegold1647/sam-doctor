# Researcher evidence packet (sanitized)

Use this when you need a repeatable artifact for collaboration, reviews, or
research discussion.

## 1) Capture a minimal input

```bash
# Prefer the smallest relevant excerpt around the first supported failure signal
sam-doctor diagnose deployment.log --format markdown > diagnosis.md
sam-doctor diagnose deployment.log --format json --output diagnosis.json
```

## 2) Build a reusable packet

```bash
mkdir -p artifacts
cp diagnosis.md artifacts/
cp diagnosis.json artifacts/
cat > artifacts/researcher-notes.md <<'EOF'
Scenario:
Toolchain:
Failure family:
Sanitized excerpt command:
SAM Doctor output summary:
Validation command run:
Outcome:
EOF
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
