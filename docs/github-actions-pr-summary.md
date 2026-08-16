# Add an opt-in first-finding PR comment

Use this pattern when reviewers need the first supported deployment finding on a
same-repository pull request without opening a raw log. It is intentionally a
workflow-level choice: SAM Doctor writes a short, redacted Markdown file; your
workflow decides whether to comment with its normal `GITHUB_TOKEN`.

Start from the canonical
[`github-actions-pr-comment.yml` example](../examples/github-actions-pr-comment.yml).

## What the Action writes

Set `first-finding-report` to a workspace path:

```yaml
- name: Diagnose deployment log
  if: always()
  id: sam-doctor
  uses: jakegold1647/sam-doctor@v0
  with:
    log-file: deployment.log
    summary: true
    first-finding-report: sam-doctor-first-finding.md
```

The file contains the first deterministic finding with already-redacted
evidence. For a non-empty input with no matching rule, it contains SAM Doctor's
normal no-supported-pattern message; an empty log reports that there is nothing to
diagnose. It never contains or uploads the raw deployment log.

## Keep the comment opt-in and safe

The example uses the `pull_request` event and explicit `contents: read` plus
`pull-requests: write` permissions. Its comment step is guarded so it only runs
for a PR whose head repository matches the current repository. Fork PRs still get
the diagnostic job and its summary, but no comment attempt.

The step reads the generated Markdown file at runtime, adds a stable hidden
marker, and updates that marked comment on later runs. A missing comment permission
is non-blocking, so the summary remains the fallback and the deployment's original
status remains visible.

Do not switch this pattern to `pull_request_target`, put report text directly in
workflow JavaScript, upload `deployment.log`, or replace the same-repository
guard with a branch-name check.
