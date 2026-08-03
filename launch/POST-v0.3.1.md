# SAM Doctor v0.3.1 launch copy

Use one version, adapt it to the audience, and only share where it is relevant.
The useful part of the post should stand on its own without a repository link.

## Short launch post

> AWS deployment logs often end with `ROLLBACK_COMPLETE`, but the useful error
> happened earlier on a failed resource. I built SAM Doctor to turn a local,
> sanitized SAM / CloudFormation / IAM / GitHub Actions log into a short report:
> matched evidence, a likely failure family, and safe checks.
>
> It is a free local CLI: no AWS credentials, no log upload, no automatic fixes.
> v0.3.1 adds a CloudFormation failed-resource demo and a guide to GitHub Actions
> OIDC failures. If you have a sanitized error, I would value a report that is
> wrong or missing as much as one that helps.
>
> https://github.com/jakegold1647/sam-doctor

## OIDC guide post

> A GitHub Actions `AssumeRoleWithWebIdentity` failure is often a mismatch
> between the OIDC token and the AWS role trust policy—not a reason to widen IAM
> permissions. The three checks are: `id-token: write`, the
> `sts.amazonaws.com` audience, and the exact `sub` condition.
>
> One current gotcha: newer GitHub repositories can use immutable OIDC subject
> claims that include owner and repository IDs. Copying an older `sub` example
> can leave a correctly scoped trust policy unable to match.
>
> I wrote the full safe-check guide here:
> https://github.com/jakegold1647/sam-doctor/blob/main/docs/oidc-deployment-debugging.md

## CloudFormation guide post

> `ROLLBACK_IN_PROGRESS` is downstream context. For a failed CloudFormation
> deploy, find the first `CREATE_FAILED` or `UPDATE_FAILED` resource event and
> preserve its status reason before retrying. That is where the next useful
> check usually starts.
>
> I wrote a short walkthrough, including the exact information to capture from
> stack events:
> https://github.com/jakegold1647/sam-doctor/blob/main/docs/cloudformation-first-failure.md

## Reply when someone reports a matching problem

> The first detail I would preserve is the `ResourceStatusReason` from the
> earliest failed resource event / the exact OIDC `sub` condition from the
> failing job. I made a local CLI for this error family that can produce a
> redacted report from a short sanitized excerpt. It is free; use it only if it
> saves you time: https://github.com/jakegold1647/sam-doctor

## After someone tries it

> Thanks for trying it. If the diagnosis missed the mark, the most useful
> feedback is the first sanitized error and the check you expected it to suggest.
> You can open a rule request or add it to the discussion:
> https://github.com/jakegold1647/sam-doctor/discussions/1

Do not ask for a star as a favor or in exchange for help. If the project proves
useful, it is reasonable to say that starring is a voluntary way to follow
updates.
