# SAM Doctor distribution tracking

This repo uses ethical, conversation-first growth: no incentives, no star-buying,
no exchanges, and no pressure tactics. Use this sheet to keep the next 30 days
focused and reviewable.

## Weekly snapshot checklist

Run:

```bash
python scripts/check-distribution.py
```

Recommended cadence: Monday + Friday after any outreach batch.

Automated monitoring:

- This workflow runs every Monday and Friday on GitHub Actions:
  `.github/workflows/distribution-check.yml`
- Run it manually via workflow dispatch any time you publish a new release
  or run a new outreach batch.
- Each run uploads an artifact named `distribution-snapshot` containing
  `distribution.json` so you can compare snapshots over time.
- The run also appends a trend-friendly history row to `distribution.csv` for quick
  local and spreadsheet analysis.

## What to watch

- `repo_stars` should reflect voluntary follow-ups only.
- `discussions` and issues should trend with practical failures, not broad requests.
- `release` count and versioned artifact publishing should keep pace.
- Pages, Marketplace, and PyPI reachability should stay green.
- Avoid any request to buy stars; ask people to share only if they found useful output.

## Copy guardrails

- Lead each outreach with a real problem first.
- Ask one concrete follow-up question about the failure.
- Ask for a feedback artifact (issue title + one-liner) before asking about distribution help.
- If there is no follow-through after 20 personalized contacts, focus on one
  stronger case study and repeat fewer, deeper conversations.

## Record format (append in a shared notes doc)

- date
- conversations started
- sanitized logs reviewed
- issues opened
- false positives reported
- new useful rules planned
- voluntary stars
- repeat users / re-runs

Keep this honest and lightweight. The signal you want is repeated, practical use.
