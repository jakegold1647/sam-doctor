# Draft: r/aws (or r/devops) post

> Publish manually. Suggested flair: "tooling" or "discussion" depending on
> subreddit rules. Check each subreddit's self-promo policy first; r/aws
> generally tolerates OSS posts that lead with the problem, not the tool.

---

**Title:** I got tired of re-debugging the same "Not authorized to perform sts:AssumeRoleWithWebIdentity" failure, so I wrote a local log analyzer for SAM/CloudFormation deploys

**Body:**

A few months ago I set up GitHub Actions OIDC for a SAM app, and the deploy
died with `Not authorized to perform: sts:AssumeRoleWithWebIdentity`. That
error message tells you almost nothing: the actual cause can be a missing
`id-token: write` permission, a wrong audience in the trust policy, or a `sub`
condition that doesn't match the branch that ran the job. I fixed it, forgot
which of the three it was, and then hit it again on the next repo.

The other one that kept eating time: a CloudFormation rollback where the line
you actually need (the first `CREATE_FAILED` event) is buried above a wall of
`ROLLBACK_IN_PROGRESS` noise.

So I wrote sam-doctor. It's a small Python CLI that reads a deployment log
locally, matches it against 22 known failure patterns (OIDC/STS, IAM
AccessDenied, CloudFormation rollbacks and capability errors, SAM config
problems, API Gateway ordering issues, etc.), and prints the matched evidence
plus the specific things to check, with a link to the relevant official doc
page.

Things it deliberately does NOT do:

- No AWS API calls. It never touches your account.
- No network calls at all. It's regex/pattern matching, not an LLM.
- No uploading logs anywhere. Output is redacted (account IDs, ARNs, tokens)
  before it's shown, in case you paste the report into a ticket.
- No guessing. If nothing matches, it says "no supported pattern found"
  instead of inventing a root cause.

Try it without credentials:

```
pip install sam-doctor
sam-doctor demo
```

or point it at a real log: `sam-doctor diagnose deployment.log`. There's also
a GitHub Action that runs it on the log your deploy step already writes.

Repo: https://github.com/jakegold1647/sam-doctor (MIT)

It only knows the failures I've encoded rules for, so if you have a deployment
error it whiffs on, I'd genuinely like a sanitized excerpt - that's how the
rule set grows.
