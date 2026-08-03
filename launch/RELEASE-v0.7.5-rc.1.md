# SAM Doctor v0.7.5-rc.1

This prerelease puts the polished first-use path on one tested version:

- The README and project site install the matching wheel directly from GitHub.
- The Marketplace Action examples run after failed deployments and use
  `if: always()` so the diagnostic report is not skipped.
- Human-readable no-match reports point users toward sanitized rule feedback.
- Scheduled launch monitoring no longer treats the intentional prerelease state
  as a failed stable-release check.
- Outreach summaries include an ethical growth score and concrete next actions.

The CLI and Action remain local and evidence-first: they do not access AWS,
upload logs, or change resources.
