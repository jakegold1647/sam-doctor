# Community triage

This is the short path from a usage report to a useful next contribution. Keep
it lightweight, privacy-first, and specific enough that a newcomer can pick up
the next step without guessing.

## First reply

1. Thank the reporter for trying SAM Doctor and sharing the result.
2. Confirm that no raw logs, credentials, account IDs, ARNs, customer data, or
   private repository names are needed.
3. Ask only for missing context: the version, command or workflow family, rule
   ID or finding title, and the smallest sanitized excerpt or packet detail.
4. Apply the narrowest useful label and link the next action before asking for
   more information.

Suggested reply:

> Thanks for trying SAM Doctor. This is enough to start triage. Please keep any
> follow-up sanitized. We will route this to a fixture, documentation update,
> or diagnostic rule, and you are welcome to take the first PR if you want to.

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
questions. Pair it with `mentor available` when a newcomer can ask for help;
remove `status: ready` when the issue is claimed, blocked, or needs more
reproduction. When a newcomer explicitly claims an issue in a comment, assign
it or remove `status: ready` promptly so nobody else starts duplicate work.
Keep these labels meaningful so a newcomer can trust the queue.

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
