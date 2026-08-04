# Draft: dev.to article / LinkedIn post

> Two versions below: the dev.to article (longer) and a LinkedIn cut of the
> same story. Publish manually. On dev.to, suggested tags: #aws #serverless
> #devops #opensource.

---

## dev.to version

**Title:** The deployment error that lies to you (and the small CLI I built because of it)

`Not authorized to perform: sts:AssumeRoleWithWebIdentity`

If you've wired GitHub Actions to AWS with OIDC, you've probably met this
line. It looks specific. It isn't. In practice it means one of at least three
different things:

1. The workflow is missing `permissions: id-token: write`, so no OIDC token
   was issued at all.
2. The role trust policy expects a different audience than
   `sts.amazonaws.com`.
3. The trust policy's `sub` condition doesn't match the repo, branch, or
   GitHub Environment that actually ran the job.

The error text is identical in all three cases. I fixed it once, forgot which
cause it was, and hit it again months later on a different repo. The second
time, I wrote down the checklist. The third time, I turned the checklist into
code.

That became sam-doctor: a Python CLI that reads a SAM / CloudFormation /
GitHub Actions deployment log locally and matches it against hand-written
rules for failures like this one - plus IAM AccessDenied, CloudFormation
rollbacks (it finds the first CREATE_FAILED event instead of the rollback
noise), capability acknowledgement errors, SAM config conflicts, and a
handful of others. 22 rules right now.

Constraints I held myself to, because they're what I wanted as a user:

- **Local and offline.** It never calls AWS and never uploads the log.
  Deployment logs are full of account IDs and role ARNs; they shouldn't
  leave your machine just to get triaged.
- **Deterministic.** Same log, same report. No model, no temperature.
- **Redacted output.** Account IDs, ARNs, and token-shaped strings are
  stripped before anything is displayed, so the report is safe to paste
  into a ticket.
- **No guessing.** If no rule matches, it says "no supported pattern found."
  I'd rather it be silent than confidently wrong.

You can try it in under a minute with no AWS account:

```bash
pip install sam-doctor
sam-doctor demo
```

For real use: `sam-doctor diagnose deployment.log`, or the GitHub Action,
which runs on the log your deploy step already writes and can post a
redacted job summary.

It's MIT licensed: https://github.com/jakegold1647/sam-doctor

The honest limitation: it only knows the failures it has rules for. If you
hit a deployment error it can't classify, a sanitized excerpt in an issue is
the most valuable contribution there is.

---

## LinkedIn version

I kept hitting the same AWS deployment failure - "Not authorized to perform
sts:AssumeRoleWithWebIdentity" - and kept forgetting that it has three
different causes hiding behind one error message.

So I built sam-doctor, a small open-source CLI that reads SAM/CloudFormation/
GitHub Actions deployment logs locally and matches them against 22 known
failure patterns. It prints the evidence, what to verify, and the official
doc link.

What makes it different from pasting the log into a chatbot: it runs
entirely offline, never touches your AWS account, redacts account IDs and
ARNs from its output, and says "no match" instead of guessing.

Try it without credentials: pip install sam-doctor, then sam-doctor demo.

Repo (MIT): https://github.com/jakegold1647/sam-doctor

If it misses a failure you've hit, a sanitized log excerpt in an issue is
the best way to make it better.
