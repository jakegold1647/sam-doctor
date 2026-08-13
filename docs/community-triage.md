# Community triage

This is the short path from a usage report to a useful next contribution. Keep
it lightweight, privacy-first, and specific enough that a newcomer can pick up
the next step without guessing.

## Public routes used in this playbook

- [Support boundaries](../SUPPORT.md) explain what maintainers can investigate
  in public and what must stay with the user's own incident process.
- [Share usage feedback](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml)
  accepts a helped, missed, unclear, or difficult setup report.
- [Contributing a diagnostic rule](contributing-a-diagnostic-rule.md) is the
  implementation path once a missed signal has a positive and nearby negative
  fixture.
- [Show and tell](https://github.com/jakegold1647/sam-doctor/discussions/categories/show-and-tell)
  is for a sanitized workflow or result that other users can reuse.

## First reply

1. Thank the reporter for trying SAM Doctor and sharing the result.
2. Confirm that no raw logs, credentials, account IDs, ARNs, customer data, or
   private repository names are needed.
3. Ask only for missing context: the version, command or workflow family, rule
   ID or finding title, and the smallest sanitized excerpt or packet detail.
4. Apply the narrowest useful label and link the next action before asking for
   more information.

Use the outcome-specific first responses below instead of asking every reporter
for the same context.

## Route the report

| Report outcome | Label or route | Next maintainer action |
| --- | --- | --- |
| The diagnosis helped | `enhancement`, `area: docs` when useful | Ask whether the reporter is comfortable sharing a sanitized example for the gallery. |
| A failure was missed | `diagnostic`, `status: needs-repro` | Extract one positive fixture and one nearby negative case; link a rule issue if the scope is clear. |
| An unrelated line was diagnosed | `diagnostic`, `status: needs-repro` | Capture the non-match, check rule precedence, and ask for the smallest safe reproducer. |
| The report was unclear or unsafe | `diagnostic` or `documentation` | Identify the evidence gap and propose the smallest wording or verification improvement. |
| Setup or workflow friction | `area: contributor-experience` or `area: github-action` | Reproduce with the documented command, then turn the fix into a copy-ready example. |
| The reporter wants to code | `help wanted`, `good first issue`, `mentor available`, `status: ready` | Link one scoped issue, explain the first file to edit, and invite a claim comment. |

Do not add `good first issue` until the acceptance criteria and test or
documentation path are clear. Add `status: ready` only when the issue has a
concrete first file or command, acceptance criteria, and a maintainer path for
questions. Add one `effort: small`, `effort: medium`, or `effort: large` label
so a newcomer can choose work with an honest size signal. Pair it with
`mentor available` when a newcomer can ask for help;
remove `status: ready` when the issue is claimed, blocked, or needs more
reproduction. When a newcomer explicitly claims an issue in a comment, assign
it or remove `status: ready` promptly so nobody else starts duplicate work.
Keep these labels meaningful so a newcomer can trust the queue.

## Copy-ready first responses

### The diagnosis helped

> Thanks for trying SAM Doctor - glad this finding helped. Please share only the
> stable rule ID, command family, and smallest sanitized evidence line through
> [Share usage feedback](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml).
> If the workflow itself would help another team, post the sanitized setup in
> [Show and tell](https://github.com/jakegold1647/sam-doctor/discussions/categories/show-and-tell).
> Do not attach the full deployment log.

**Escalation:** If the report reveals a useful workflow or a confusing sentence
in the finding, open one scoped example or documentation issue. Name the first
file to edit and the acceptance criterion, then invite the reporter to claim it.

### The failure was missed

> Thanks for reporting the miss. Run `sam-doctor request-packet deployment.log`,
> review the generated excerpt yourself, and open a
> [rule request](https://github.com/jakegold1647/sam-doctor/issues/new?template=rule_request.yml)
> with the SAM Doctor version and command family. Keep only the 5-15 sanitized
> lines around the first useful error; do not paste the full log.

**Escalation:** Keep the issue at `status: needs-repro` until one positive signal
and one nearby non-match define a deterministic boundary. Once they do, scope
the rule, link [Contributing a diagnostic rule](contributing-a-diagnostic-rule.md),
and invite a contributor to claim the implementation.

### The report is unclear or unsafe

> Thanks for flagging this. Please stop before adding more log text. Edit or
> remove any credential, token, account ID, ARN, customer data, or private path;
> if a credential was exposed, follow your own incident process before
> continuing. Start again with only the SAM Doctor version, rule ID or title,
> command family, and a reviewed placeholder-based summary. The
> [Support boundaries](../SUPPORT.md) explain what is safe to investigate here.

**Escalation:** Ask one missing-context question at a time. If useful triage would
require private data, stop the public investigation. If SAM Doctor or its docs
asked for unsafe material, open a focused bug or documentation issue that names
the unsafe prompt without reproducing the sensitive value.

### Setup or workflow friction

> Thanks for reporting the setup problem. Use
> [Share usage feedback](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml)
> to send the SAM Doctor version, OS or runner, exact command or minimal workflow
> step, and exit code. Replace repository names and private paths with
> placeholders; no AWS credentials or raw deployment log are needed.

**Escalation:** If the command contradicts the documented exit-code contract,
open a bug with a credential-free reproducer. If the behavior is correct but the
path was unclear, open one documentation or example issue, name the first file,
and invite the reporter to take the PR.

None of these documentation, fixture, or test follow-ups requires repository
admin access: a contributor can submit the normal pull request, while a
maintainer handles labels, assignment, and closure.

The scheduled [community queue check](../.github/workflows/community-queue.yml)
checks this contract against GitHub's public issue data. It is intentionally
outside the pull-request gate because it needs the network; a failure is a
maintainer signal to repair labels, acceptance criteria, or the welcome prompt
before pointing a newcomer at the issue.

## Turn a miss into a contribution

1. Open or link one focused issue for one signal or one documentation gap.
2. State the smallest positive fixture, the nearby non-match, and the safe
   verification step.
3. Link the relevant [rule roadmap](rule-roadmap.md),
   [diagnostic-rule guide](contributing-a-diagnostic-rule.md), or example.
4. Invite the reporter to comment **I'd like to take this**. Keep the issue
   available to first-time contributors unless someone has actively claimed it.
5. Review the resulting PR with the same privacy, evidence, and deterministic
   checks as any maintainer change.

For a first PR, point contributors to
[`python scripts/check-pr.py`](../CONTRIBUTING.md#verify-the-baseline-before-editing)
and the [pull-request template](../.github/pull_request_template.md). A
documentation-only or fixture-only change is a complete contribution when it
makes the next diagnosis easier to reproduce.

## Close the loop

- Link the follow-up issue or PR in the feedback report.
- Thank the reporter even when the result is already fixed by an existing rule.
- Keep the feedback report open while a promised follow-up is unlinked; close it
  after the fix, example, or documentation path is clear.
- Preserve the redaction boundary in every comment and fixture.

The [usage feedback form](https://github.com/jakegold1647/sam-doctor/issues/new?template=usage_feedback.yml)
is for wins, misses, unclear reports, and setup friction. The
[support guide](../SUPPORT.md) explains what SAM Doctor cannot investigate.
