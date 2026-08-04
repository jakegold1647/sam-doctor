# Awesome-list entries (drafts — submit manually)

Ready-to-paste one-liners and PR descriptions for awesome-serverless /
awesome-aws style lists. Check each list's CONTRIBUTING.md for ordering
(usually alphabetical) and formatting rules before opening the PR.

## One-line entries

Pick the variant that matches the target list's format.

**Standard (name — description):**

```markdown
- [sam-doctor](https://github.com/jakegold1647/sam-doctor) — CLI and GitHub Action that diagnoses failed AWS SAM/CloudFormation deployments from log text: 31+ rules for OIDC, rollback, capability, ECR, and build failures. Runs offline, redacts identifiers.
```

**Short (for lists with tight descriptions):**

```markdown
- [sam-doctor](https://github.com/jakegold1647/sam-doctor) — Diagnose failed SAM/CloudFormation deploys from the log, offline.
```

**awesome-aws style (with language tag):**

```markdown
- [sam-doctor](https://github.com/jakegold1647/sam-doctor) - Python CLI that pinpoints why a SAM/CloudFormation deploy failed (OIDC, rollback, capabilities, ECR auth, throttling) without AWS access.
```

Suggested sections: "Serverless / SAM", "Developer Tools", "CI/CD", or
"Debugging & Troubleshooting", depending on the list.

## PR title

```
Add sam-doctor (SAM/CloudFormation deployment failure diagnosis)
```

## PR description

```markdown
## What is being added

[sam-doctor](https://github.com/jakegold1647/sam-doctor) — an MIT-licensed
Python CLI and GitHub Action that diagnoses failed AWS SAM, CloudFormation,
and GitHub Actions deployments from the log text alone.

## Why it belongs on this list

- Solves a recurring pain: turning a wall of rollback noise into the first
  actionable failure (OIDC trust rejections, ROLLBACK_COMPLETE,
  InsufficientCapabilities, ECR auth, throttling, Docker/esbuild build
  failures — 31+ deterministic rules).
- Runs entirely locally: no AWS credentials, no API calls, no log upload;
  output is redacted so it is safe to share in team channels.
- Actively maintained, tested, published on PyPI and the GitHub Actions
  Marketplace with docs and CI templates for GitHub Actions, GitLab,
  CircleCI, Azure Pipelines, and Bitbucket.

## Checklist

- [x] Entry follows the list's format and alphabetical ordering
- [x] Project is open source (MIT) and actively maintained
- [x] Link is to the canonical repository
- [x] I am the project author (disclosed)
```

Note: keep the author disclosure in the PR — most awesome lists require
self-submissions to be identified.
