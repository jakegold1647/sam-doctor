# Draft: Hacker News "Show HN"

> Publish manually from your own account. HN convention: title starts with
> "Show HN:", URL points at the repo, and the text below goes in the text
> field. Be around for the first two hours to answer comments.

---

**Title:** Show HN: Sam-doctor â€“ offline, deterministic diagnosis of AWS SAM/CloudFormation deploy failures

**URL:** https://github.com/jakegold1647/sam-doctor

**Text:**

I kept losing time to the same two AWS deployment failures: GitHub Actions
OIDC role assumption ("Not authorized to perform sts:AssumeRoleWithWebIdentity",
which has at least three distinct causes the error text doesn't distinguish),
and CloudFormation rollbacks where the first CREATE_FAILED event is buried
under rollback noise.

sam-doctor is a zero-dependency Python CLI that reads the deployment log
locally and matches it against a catalog of hand-written failure rules (29 and growing). For each match
it prints the evidence lines, a confidence level, the specific things to
verify before changing anything, and a link to the official doc page.

Design choices, since they're the whole point:

- Deterministic: same log in, same report out. Rules are pattern matches,
  not a model.
- Offline: no AWS calls, no network calls, nothing uploaded.
- Redacted by default: account IDs, ARNs, key IDs, and tokens are stripped
  from output so the report is safe to paste into a ticket or PR.
- Honest about coverage: if no rule matches, it says so and exits, rather
  than guessing. `sam-doctor rules --format json` lists exactly what it can
  and can't see.

An LLM can obviously handle failures I have no rule for, and I still use one
for those. But for the failures that recur, I wanted something that doesn't
require uploading a log full of account IDs and role ARNs, and that gives the
same answer every time.

Try it without an AWS account: `pip install sam-doctor && sam-doctor demo`
(or `uvx sam-doctor demo`). There's also a composite GitHub Action that runs
it on the log your deploy step already writes.

MIT licensed. The rule set is the obvious limitation - contributions of
sanitized failure excerpts are the most useful thing anyone can send.
