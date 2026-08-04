# SAM Doctor deep-research sprint plan

Use this when you want measurable, practical feedback before shipping positioning changes.

## 1) User adoption research (highest priority)

**Goal:** prove what keeps people from trying the tool after install.

1. Run 10–20 short interviews with developers who currently deploy to AWS SAM or CloudFormation.
2. Ask only concrete questions:
   - What is your most recent deployment failure and where did it happen?
   - What changed the fastest for triage today?
   - What do you do first when a deploy fails?
   - What prevented you from using SAM Doctor last time?
   - What output format makes you trust an external diagnostic most?
3. Capture one sentence per interview in `artifacts/research-notes.md` (or your notes app):
   - `pain`, `workaround`, `decision blocker`, `feature requested`.
4. Next action only if same blocker appears >=3 times.

## 2) Keyword + discoverability audit

**Goal:** rank high-intent search terms and positioning gaps.

1. Search these terms in recent posts, repos, and marketplaces:
   - "AWS SAM deployment failed" / "GitHub Actions OIDC error"
   - "sam deploy failed" / "CloudFormation rollback error"
   - "sam doctor", "aws cloudformation action", "github actions deployment diagnostics"
2. For each top competitor, record:
   - setup friction (install + sample in 60s),
   - supported failure classes,
   - whether it uploads logs or requires credentials,
   - clarity of output and safe-check guidance.
3. Keep a one-line gap statement (e.g. `competitor X is too slow to setup, no local redaction`).

## 3) Channel experiments (execution loop)

**Goal:** identify where a real developer first sees and trusts the project.

- Run one batch of 5 personalized interactions per week.
- Use only people with a visible, recent AWS failure.
- For each channel record: `attempts`, `diagnoses sent`, `follow-through`, `feedback outcome`.
- Retire channels that produce no practical trials after 2 batches.

## 4) Product proof loop

**Goal:** turn curiosity into trust.

- Publish one short de-identified case note every 2 weeks in `RESEARCH` / changelog.
- Pair each note with:
  - one sanitized log excerpt,
  - matched finding,
  - one safe verification command,
  - what changed next.
- Track whether repeat trials increase after publication.

## 5) Success signals this sprint

Use these as gates for the next rollout:

- >50% of new first-contact asks include a real failure and a try of the CLI.
- repeat-users / one-off users ratio should move up.
- Outreach conversations with feedback should outnumber pure thanks/star messages.
- Organic stars should trend with practical trials, not just profile visits.

### Evidence snapshot command

After each sprint, run:

```bash
python scripts/check-launch.py --append-csv artifacts/distribution.csv --summary artifacts/distribution-summary.md --print-trend
python scripts/check-launch.py --skip-distribution --strict-ethical --min-feedback-ratio 100 --outreach-log launch/outreach-log-template.csv
```

If strict ethical checks fail, pause outbound posting and close the blocker before the next release.
