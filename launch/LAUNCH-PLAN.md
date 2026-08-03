# SAM Doctor launch plan: earn useful stars

The goal is not to manufacture stars. The goal is to get SAM Doctor in front of
developers with a current deployment failure, earn trust with a useful free
report, and make starring the repository an easy voluntary way to follow it.

## Launch bar

Before the first public post:

1. Confirm the current prerelease exists and the GitHub Actions matrix is green.
2. Set the repository homepage to the GitHub Pages site.
3. Add the repository topics listed in `PUBLISH.md`.
4. Upload `site/assets/sam-doctor-social-preview.jpg` in repository settings.
5. Use the current release note and verify the pinned install command in a clean shell.
6. Point visitors to the welcome discussion and the issue forms so feedback has a clear home.

## Who to help first

Prioritize people who have an active, public error in one of these categories:

- GitHub Actions OIDC role-assumption failures.
- CloudFormation rollbacks with an unclear first failing resource.
- IAM access-denied deployment errors.
- AWS SAM change-set, parameter, or credentials failures.
- API Gateway CORS preflight conflicts.

Do not pitch under unrelated posts, mass-message people, or ask for a star before
you have helped. The best opening is a short answer to their actual error plus a
link to the free alpha only when it is relevant.

## The 14-day sequence

| Day | Action | Success signal |
| --- | --- | --- |
| 0 | Publish the current prerelease and run the launch-bar checklist. | A stranger can install, demo, and file feedback without asking a question. |
| 1 | Post a concise launch note on your own GitHub, LinkedIn, X, or personal network. | 5 qualified clicks or replies. |
| 2-4 | Have 10 one-to-one problem conversations using the interview note in `OUTREACH.md`. | 3 people try it on a sanitized real failure. |
| 5 | Publish a short problem-first write-up: "Why an OIDC deploy failed even though the workflow looked right." Include one synthetic before/after report. | 1 saved/shared post or substantive reply. |
| 6-10 | Offer helpful answers in AWS SAM, serverless, GitHub Actions, and CloudFormation communities where sharing a relevant tool is allowed. | 5 qualified visitors from help-first replies. |
| 11 | Turn the most common missing pattern into a public issue and label it as planned or declined with a reason. | A visible feedback loop. |
| 12-14 | Publish a small follow-up showing what changed from feedback. | 3-10 organic stars or 5 repeat users is a healthy first signal. |

## Copy that earns attention without hype

### Launch post

> I kept seeing the same AWS deployment failures burn time because the useful
> error was buried in a long SAM or GitHub Actions log. I made SAM Doctor, a
> local CLI that matches a small set of failures, shows the evidence, and gives
> safe checks. It does not need AWS credentials or upload the log. The free alpha
> is here: https://github.com/jakegold1647/sam-doctor
>
> If you try it on a sanitized failure, I would genuinely value a false-positive
> report or a missing-rule request. Star it only if it is worth following.

### Help-first reply

> The first thing I would verify is [specific safe check]. I also built a small
> local CLI that recognizes this error family and keeps only redacted matching
> evidence in its report. If useful, it is free here: https://github.com/jakegold1647/sam-doctor

### Follow-up post

> A few developers tried SAM Doctor on real sanitized deployment failures. The
> clearest lesson was [specific lesson]. I tightened [rule] so it no longer flags
> [non-failure], and added [new behavior]. I am still looking for the next real
> failure family to support: https://github.com/jakegold1647/sam-doctor

## Channels and rules

- Share in the AWS SAM developer community only after reading its current rules;
  the official SAM CLI repository points contributors to the `#samdev` Slack
  channel.
- Answer existing GitHub Issues, Stack Overflow questions, or forum posts only
  when the answer itself is useful without the link.
- Use a technical post or short video to explain one concrete failure, not a
  generic "new tool" announcement.
- Ask collaborators and testers for blunt feedback, not reciprocal stars.

## Metrics to track

Record only aggregate numbers and voluntary feedback. Do not retain customer logs.

| Metric | Week-one target | Why it matters |
| --- | --- | --- |
| Qualified conversations | 10 | Measures whether the problem is real and reachable. |
| Sanitized real-log trials | 3 | Validates the diagnostic workflow. |
| Actionable issues or rule requests | 2 | Produces an evidence-based roadmap. |
| Organic stars | 3-10 | Indicates that a visitor wants to follow the project. |
| Repeat users | 2 | Stronger than a vanity metric. |

If visitors install but do not star, ask what was missing from the README or demo.
If people star but do not try it, improve the quick-start and publish a clearer
realistic example. If no one with a current failure engages after 20 helpful,
personalized conversations, narrow the tool to the error family that produced the
strongest response instead of broadening the marketing.

## Keep the project credible

- Never buy stars, use star-exchange groups, or ask for a star in exchange for help.
- Never post a user's log, even after redaction, without explicit permission.
- Prefer transparent changelog updates over promises about unsupported features.
- Reply to feedback with the decision and rationale, including when a rule will not be added.
