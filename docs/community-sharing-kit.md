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

## 3b) High-intent templates by error family

Use one of these when your audience already has a failure class.

### OIDC (`AssumeRoleWithWebIdentity`) message

```
Team hit: "Not authorized to perform: sts:AssumeRoleWithWebIdentity" during deploy.

Use SAM Doctor first on the excerpt before changing IAM trust:
- captures the pattern
- suggests the first safe check
- keeps sensitive identifiers redacted

Run:
sam-doctor diagnose deployment.log --format markdown

Install if needed:
python -m pip install sam-doctor

Homepage:
https://jakegold1647.github.io/sam-doctor/
```

### Rollback noise (`ROLLBACK_COMPLETE`) message

```
Deployment log is full of rollback noise but failure root is unclear.

Use SAM Doctor for the first actionable event, then re-run with only the needed fix:
sam-doctor diagnose deployment.log --format markdown

See:
https://github.com/jakegold1647/sam-doctor/blob/main/docs/cloudformation-first-failure.md
```

### Capability/permissions message

```
If deploys start failing on IAM capability checks, use one local diagnosis pass:
sam-doctor diagnose deployment.log --format markdown

Then apply only the required capability update and re-run.

Reference:
https://github.com/jakegold1647/sam-doctor/blob/main/docs/capability-acknowledgement.md
```

### ECR / container image message

```
Lambda container image CI deployment failing on access can be hard to triage from one error.

Run a local SAM Doctor pass first:
sam-doctor diagnose deployment.log --format markdown

Share only:
- top finding
- the first verification command
- redacted excerpt
```

### SAM/CDK packaging message

```
If this is a SAM/CDK package/build failure, don’t guess from entire output.

Use this flow:
1) capture the smallest excerpt
2) sam-doctor diagnose deployment.log --format markdown
3) execute the suggested verification

More examples:
https://github.com/jakegold1647/sam-doctor/blob/main/docs/ci-command-matrix.md
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
