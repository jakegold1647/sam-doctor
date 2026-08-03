# SAM Doctor v0.4.0 launch copy

Use this only in places where AWS SAM, CloudFormation, IAM, or GitHub Actions
deployment failures are already relevant. Adapt the first sentence to the
audience; do not repeat the post unchanged across communities.

## Short release post

> I released SAM Doctor v0.4.0, a small local CLI for getting the next useful
> check from a failed AWS deployment log. It handles a focused set of SAM,
> CloudFormation, IAM, API Gateway CORS, and GitHub Actions OIDC failures. The
> report keeps only redacted matching evidence, links to the relevant docs, and
> does not access AWS or upload logs.
>
> This release separates three OIDC setup failures that are easy to blur
> together: a job missing `id-token: write`, an AWS account missing GitHub's OIDC
> provider, and a role trust-policy mismatch.
>
> https://github.com/jakegold1647/sam-doctor/releases/tag/v0.4.0

## OIDC-specific post

> If GitHub Actions cannot assume an AWS role with OIDC, check the failure in
> this order: can the job request an ID token (`id-token: write`)? Does the AWS
> account have GitHub's OIDC provider? Does the role trust policy match the
> actual `aud` and `sub` claims? Those are different fixes, and loosening a
> policy is not a good shortcut.
>
> I packaged those checks into a local, free diagnostic CLI and wrote the
> underlying guide here:
> https://github.com/jakegold1647/sam-doctor/blob/main/docs/oidc-deployment-debugging.md

## End note after a useful conversation

> I am keeping this free alpha narrow and adding rules only when they can point
> to concrete evidence and a safe next check. If it was useful, a star is a
> voluntary way to follow updates; if it missed, a short sanitized example is
> even more valuable feedback.

## Release link

https://github.com/jakegold1647/sam-doctor/releases/tag/v0.4.0
