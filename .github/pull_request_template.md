## Summary

<!-- What user-visible problem does this change solve? -->

## Diagnostic or documentation gap

<!-- Link an issue or describe the gap. Use "Fixes #123" when this PR closes
     the issue, or "Related to #123" for draft or partial work. -->

## Help wanted (optional)

<!-- If this is your first PR here or you want an early maintainer check, say
     what you are unsure about. Draft PRs and partial work are welcome. -->

## Validation

Tip: `python scripts/check-pr.py` runs every required check in one command.

- [ ] I added or updated tests when behavior changed.
- [ ] I ran `python -m ruff check src tests scripts`.
- [ ] I ran `python -m pytest -q`.
- [ ] I ran `python scripts/run-smoke.py`.
- [ ] I ran `python -m build` when packaging or release files changed.
- [ ] A new or changed rule passes `python scripts/check-rule-catalog.py` and includes a positive and a nearby-negative test.
- [ ] I checked that fixtures contain no credentials, account IDs, ARNs, customer data, or unredacted logs.

## Safety review

- [ ] The report does not claim more certainty than the evidence supports.
- [ ] Suggested verification steps are read-only or clearly warn before changes.
- [ ] Official documentation links are included for new diagnostic behavior.
