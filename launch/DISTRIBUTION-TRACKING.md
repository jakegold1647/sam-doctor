# SAM Doctor distribution tracking

This repo uses ethical, conversation-first growth: no incentives, no star-buying,
no exchanges, and no pressure tactics. Use this sheet to keep the next 30 days
focused and reviewable.

## Weekly snapshot checklist

Run:

```bash
python scripts/check-launch.py --append-csv distribution.csv --summary distribution-summary.md --print-trend
```

Recommended cadence: after notable outreach batches and at least once per week
in addition to the automated 12-hour workflow snapshots.

Automated monitoring:

- This workflow runs every 12 hours on GitHub Actions:
  `.github/workflows/distribution-check.yml`
- A stable `release` publish event also runs this workflow automatically for a
  baseline snapshot.
- The workflow now runs the full launch check stack (`scripts/check-launch.py`), so
  each run verifies release-readiness, distribution channels, and a fresh
  outreach summary snapshot together.
- After stable publish and PyPI upload, the `pypi-publish` workflow also triggers
  a strict `workflow_dispatch` rerun of `distribution-check.yml` with
  `strict-distribution-during-release=true`, so hard readiness checks happen only
  after release channels are expected to be live.
- When run manually, include the `strict-distribution-during-release` workflow
  input after release is fully live so the check fails if PyPI/Marketplace/homepage
  readiness is still not green.
- Run it manually via workflow dispatch any time you publish a new release
  or run a new outreach batch. Manual execution is still useful for
  pre-release validation and ad-hoc checks outside the default cadence.
- Each run uploads an artifact named `distribution-snapshot` containing
  `distribution.json`, `distribution.csv`, `distribution-summary.md`, and
  `outreach-summary.md` so you can compare launch health over time.
- The run also appends a trend-friendly history row to `distribution.csv` for quick
  local and spreadsheet analysis.
- A summary note is emitted as `distribution-summary.md` for quick paste into
  launch notes.
- Run the scheduled check manually when you want stricter launch-gating:
  - Add `strict-distribution-during-release: true` for non-schedule/manual runs
    where you want hard launch-channel readiness enforcement.
  - Add `strict-ethical: true` to fail when voluntary outreach feedback is not
    strong enough (default minimum ratio is 100).
  - Customize the ethical minimum with `min-feedback-ratio` (for example, `85`).
- Run:
  `python scripts/check-launch.py --skip-distribution --strict-ethical --min-feedback-ratio 100 --outreach-log launch/outreach-log-template.csv --outreach-summary artifacts/outreach-summary.md`
  weekly (or before publishing a release) and review `ethical_signal` and
  `ethical_signal_strength`; treat `"mixed"` as "helpful star happened without
  follow-up context" and follow up for context before considering that signal.
- After a stable tag is live on release channels, add
  `--strict-distribution-during-release` to also fail when PyPI, Marketplace,
  and homepage/topics readiness are not fully green.

## What to watch

- `repo_stars` should reflect voluntary follow-ups only.
- `discussions` and issues should trend with practical failures, not broad requests.
- `ethical_signal` from outreach should trend with problem-first follow-up, not
  gratitude-only stars.
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

To reduce drift, copy this into a weekly `outreach-log-template.csv` row in
`launch/outreach-log-template.csv` and keep it in your notes folder:

`launch/outreach-log-template.csv` is intentionally header-only so the launch checks
measure only real outreach outcomes.

- week
- date
- contact_channel
- problem_area
- conversation_stage
- next_action
- voluntary_star
- outcome
- feedback_signal
- repeat_contact

Keep this honest and lightweight. The signal you want is repeated, practical use.
