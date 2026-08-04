# AWS Open Source Newsletter submission (draft — send manually)

Submission channels: the newsletter takes suggestions via the #aws-open-source
channel on the AWS Developers Slack, via @ mentions of the curator on
social, or the contact form linked from each issue on blog.beachgeek.co.uk.
Adapt the subject line to whichever channel you use.

---

**Subject:** Project suggestion: sam-doctor — offline diagnosis of SAM/CloudFormation deploy failures

Hi,

I'd like to suggest my open source project for a future issue of the AWS
Open Source Newsletter.

**sam-doctor** is a Python CLI and GitHub Action that diagnoses failed AWS
SAM, CloudFormation, and GitHub Actions deployments from the log text alone.
It ships 31+ deterministic diagnostic rules for the failures serverless teams
actually hit — `sts:AssumeRoleWithWebIdentity` OIDC trust rejections,
`ROLLBACK_COMPLETE` dead ends, `InsufficientCapabilitiesException`, expired
tokens and clock skew, ECR auth failures during image pushes, CloudFormation
throttling, `DELETE_FAILED` blockers, and SAM build problems (Docker
unavailable, esbuild missing, Python dependency resolution).

What makes it different from pasting a log into a chatbot:

- Runs entirely locally. No AWS credentials, no API calls, no log upload.
- Deterministic and evidence-first: every finding cites the matched log line,
  a confidence level, safe verification steps, and the official AWS/GitHub doc.
- Redacts account IDs, ARNs, and tokens from the output so reports are safe
  to paste into a team channel.
- Drops into CI as a composite action with `if: always()` after the deploy
  step, with opt-in job summaries, annotations, and failure gating.

Links:

- Repo: https://github.com/jakegold1647/sam-doctor (MIT)
- PyPI: https://pypi.org/project/sam-doctor/
- Docs/site: https://jakegold1647.github.io/sam-doctor/
- Marketplace action: https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics

Install and try in under a minute:

```
pip install sam-doctor
sam-doctor demo
```

I'm the author and sole maintainer; happy to provide anything else useful
for the write-up.

Thanks for considering it,

Jacob Goldstein
jacobgoldstein.cs@gmail.com
https://jacobgoldstein.dev
