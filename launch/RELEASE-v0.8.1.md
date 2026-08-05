# SAM Doctor v0.8.1

A packaging and documentation fix on top of v0.8.0. The GitHub Action's
description is now under the Marketplace's 125-character limit, which is what
blocked the v0.8.0 Marketplace listing, and every README sample output has been
corrected to match what the CLI actually prints. No rule, flag, or report-shape
changes.

- Install the CLI with `python -m pip install sam-doctor`.
- Use the Marketplace Action with `jakegold1647/sam-doctor@v0.8.1`.
- Use `--fail-on-findings` only when a supported diagnosis should fail a CI job.
- Reports remain local, redacted, and evidence-first.
