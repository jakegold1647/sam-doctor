# Community outreach plan

SAM Doctor should grow the way a good server community grows: people arrive
with a real problem, get a useful answer, and come back because the place is
worth being part of. This is an operating plan for that loop, not a campaign to
manufacture stars.

## The rule for every public conversation

Lead with the person's deployment problem. Give the useful troubleshooting
step even if they never click a link. Mention SAM Doctor only when it is a
relevant, free next step, and ask for feedback only after they have had a chance
to try it.

Do not mass-message people, drop links under unrelated posts, publish anyone's
logs, promise coverage the rule catalog does not have, or trade help for stars.
Keep the project local and privacy-first: no telemetry, no AWS credentials, and
no raw production logs in issues or discussions.

## The two loops

### Usage loop

1. Find a public, current SAM, CloudFormation, IAM, or GitHub Actions failure.
2. Answer the immediate question with the smallest safe verification step.
3. Offer the local demo or `uvx sam-doctor diagnose ...` command if it fits.
4. Invite a sanitized usage report when the diagnosis helps, misses, or is
   unclear.
5. Turn repeated misses into a scoped issue, fixture, rule, guide, or explicit
   “not planned” decision.
6. Mention the change in the changelog or a short follow-up so users can see
   that their report went somewhere.

### Contribution loop

1. A usage report or discussion becomes one narrow issue with acceptance
   criteria.
2. Label it honestly (`good first issue`, `status: ready`, `mentor available`,
   and an effort label when it is ready for a newcomer).
3. Reply to a claim, answer setup questions, and welcome a draft PR early.
4. Review the evidence and tests, then merge through the normal branch flow.
5. Add or correct the person's entry in `CONTRIBUTORS.md` when they want the
   credit. The contributor page is generated and checked from that record, so a
   future credit cannot silently leave the site stale.

## A simple 30-day cadence

### Week 1: help a small group

- Publish one personal launch or follow-up post about a specific OIDC or
  CloudFormation failure, not a feature list.
- Have five to ten genuine conversations with people who are already debugging
  a related failure.
- Ask three people to try the tool on a sanitized log and tell you one thing
  that was useful or confusing.
- Answer every reply and open only the issues that have enough evidence to be
  actionable.

### Week 2: teach one failure family

- Publish a short before/after example: the noisy error, the matched evidence,
  and the next safe check.
- Share it in one technical community at a time, following that community's
  self-promotion rules. Good fits are GitHub Discussions, AWS/serverless
  communities, Stack Overflow answers where the tool is directly relevant, and
  a carefully written Hacker News or Reddit post.
- Do not cross-post the same announcement everywhere on the same day.

### Week 3: make the feedback visible

- Pick the most common real miss and write a small public issue with the
  sanitized signature and proposed behavior.
- Post a short progress note that names what changed and what is still unknown.
- Invite one person who gave useful feedback to review the wording or fixture;
  this is a gentler first contribution than asking for a full rule.

### Week 4: keep the door open

- Publish a changelog-style update with the new rule, fixture, docs, or reason
  for declining a request.
- Refresh the ready newcomer queue so it contains work that actually exists.
- Host an informal Q&A in GitHub Discussions if there are questions to answer;
  do not create a new chat server just to make the project look bigger.
- Review the aggregate outreach notes and choose one channel to continue, one
  to pause, and one experiment to try next month.

## Copy that sounds like a person

### Help-first reply

> The first thing I would check is **[specific safe check]**. I also maintain a
> small local CLI that recognizes this error family and shows the matched,
> redacted evidence. If it is useful, you can try it without AWS credentials:
> https://sam-doctor.jacobgoldstein.dev/ . Either way, the check above should
> tell you whether the failure is in **[likely boundary]**.

### Feedback invitation

> If you try it, would you tell me whether the report pointed at the right next
> check? A sanitized excerpt is enough; please do not include account IDs, ARNs,
> tokens, customer data, or private repository names.

### Contributor welcome

> Thanks for taking this on. Start with the smallest test or documentation
> change that proves the behavior. A draft PR is welcome before it is finished;
> I can help with the fixture, wording, or gate once there is something concrete
> to review.

## What to measure

Keep only aggregate, consented notes in the local outreach tracker. Do not store
names, private messages, deployment logs, or customer details in the repository.
The useful signals are:

- people who actually ran the tool on a real, sanitized failure;
- useful reports (a win, a miss, a false positive, or an unclear result);
- repeat users who came back with another failure or follow-up;
- scoped issues that came from those conversations;
- first-time contributors who opened a draft or merged PR.

Use `python scripts/bootstrap-outreach-log.py` to create the ignored local
tracker and `python scripts/check-outreach.py` to summarize it. Treat stars and
raw reach as secondary signals. If conversations do not lead to real trials
after a reasonable batch, narrow the problem and improve the example instead of
posting more often.

## Maintainer promise

Keep the queue honest, answer claims and questions promptly, preserve credit,
and explain decisions when a request is not a fit. The goal is a small group of
people who trust the project enough to use it on the next failed deployment and
to help make the next report better.
