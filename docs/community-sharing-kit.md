# SAM Doctor community sharing kit

Use this page when you want people outside your team to adopt SAM Doctor quickly and
safely.

## 1) 5-minute onboarding checklist (for engineers)

1. Install:

   ```bash
   python -m pip install sam-doctor
   ```

2. Capture a failure log and run one diagnosis:

   ```bash
   sam-doctor diagnose deployment.log --format markdown
   ```

3. Confirm redaction-safe sharing:

   - no account IDs
   - no ARNs
   - no raw secret values
   - no full raw logs

4. Add to CI using the matching starter in
   [examples](../examples/README.md) and your command family.

5. Decide policy:

   - start non-blocking (audit-only)
   - switch to `fail-on-findings: true` only after 2-3 stable runs

## 2) One-page evidence packet (for collaborators and researchers)

For repeatable discussion with teammates, reviewers, or researchers:

```bash
sam-doctor packet deployment.log
```

Share exactly:

- `artifacts/diagnosis.md`
- `artifacts/diagnosis.json`
- `artifacts/researcher-notes.md`
- the sanitized excerpt used as input

Keep the full raw log out of Slack, ticket threads, and external discussions unless
the recipient is explicitly authorized and can handle redaction review.

## 3) Quick outreach message drafts

### Short tweet/X-style

```
Built a small open-source tool for AWS deployment triage:
@sam-doctor spotlights the first actionable failure in SAM/CloudFormation/GitHub Actions logs,
adds safe verification steps, and keeps sensitive IDs redacted.

Try it: https://jakegold1647.github.io/sam-doctor/
```

### Short LinkedIn/Discord post

```
If your team uses SAM/CloudFormation, SAM Doctor can save deployment triage time:
- runs locally on your logs
- gives one "first useful failure" with confidence + next check
- exports a repeatable evidence packet for incident notes

Starter docs and issue templates are in:
https://github.com/jakegold1647/sam-doctor
```

### Minimal Hacker News / Reddit intro

```
I open-sourced SAM Doctor after seeing the same problem repeatedly:
CloudFormation/AWS deployment failures with noisy rollbacks.

It finds the first actionable signal, suggests a safe verification, and keeps output
redacted for sharing.
Repo: https://github.com/jakegold1647/sam-doctor
```

## 4) Suggested sharing channels

- Engineering mailing list / team channel
- DevOps Slack / Discord
- AWS-focused discussion forums (Reddit / Hacker News / Stack Overflow)
- Internal incident retrospectives

For each channel, include only:

1. one-liner of what SAM Doctor solves,
2. the onboarding checklist above,
3. one link to this kit,
4. ask for one concrete use case for follow-up.
