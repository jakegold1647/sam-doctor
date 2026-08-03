# Minimum validation that moves toward revenue

The goal is not to collect generic feedback. The goal is to learn whether an active AWS developer will pay for a local diagnostic workflow.

## Week 1

1. Publish the free tool on GitHub with a five-line install/run section and bundled demo log.
2. Contact 30 people who publicly reported a relevant AWS deployment error within the last 90 days.
3. Hold five short problem conversations. Ask about the last failure, the first error they saw, time lost, and what they used to resolve it.
4. Invite qualified contacts to run the free tool on one sanitized log.

## Week 2 decision

Move forward when at least three people run the tool on a real sanitized failure and at least one asks for a capability in the planned paid edition.

Ask for a $39 founder preorder only after a tester has seen a useful report. The first serious payment signal is three paid founder orders from people who are not friends or family.

If people like the report but will not install a CLI, package the findings as a paid troubleshooting guide instead. If people do not use the free core on real failures, narrow the tool to the most repeated error family rather than adding more rules.

## Outreach metrics helper

If you are tracking outreach in `launch/outreach-log-template.csv`, run:

```bash
python scripts/check-outreach.py launch/outreach-log-template.csv \
  --summary artifacts/outreach-summary.md \
  --strict --min-feedback-ratio 100
```

This prints a lightweight, non-sensitive summary to guide your next 7-day
focused outreach batch.

