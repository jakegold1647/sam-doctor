# Diagnose a GitHub Actions to AWS OIDC deployment failure

An `AssumeRoleWithWebIdentity` failure usually means the workflow reached AWS
STS, but the token did not satisfy the role's trust policy. Start with the
first STS error rather than a later CloudFormation rollback.

```bash
sam-doctor diagnose failed-deploy.log --format markdown
```

The report gives you a short redacted excerpt and the checks below. It does not
replace review of the workflow and trust policy.

## 1. Confirm the job can request an OIDC token

The deployment job needs the `id-token: write` permission. Keep other workflow
permissions as narrow as the job allows.

```yaml
permissions:
  id-token: write
  contents: read
```

The permission belongs at workflow or job scope. A job that never receives an
OIDC token cannot assume the AWS role, regardless of the trust policy.

## 2. Check the audience on both sides

For the normal AWS STS flow, the GitHub-issued token and AWS trust policy should
agree on `sts.amazonaws.com` as the audience. The useful comparison is:

```text
token.actions.githubusercontent.com:aud = sts.amazonaws.com
```

If a credentials action is given a custom `audience` option, verify that it is
intentional and that the AWS role expects the same value.

## 3. Compare the exact subject claim

The role trust policy must limit `token.actions.githubusercontent.com:sub` to
the workflow context that is allowed to deploy. A narrow condition looks like:

```json
{
  "StringEquals": {
    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
    "token.actions.githubusercontent.com:sub": "<exact subject for this deployment job>"
  }
}
```

Do not loosen the subject to a global wildcard just to make a deployment pass.
Verify whether the job runs from a branch ref, a GitHub Environment, or another
configured subject context.

There is a current compatibility detail worth checking: repositories created,
renamed, or transferred after GitHub's immutable-subject rollout may include
owner and repository IDs in `sub`, for example:

```text
repo:octo-org@123456/octo-repo@456789:ref:refs/heads/main
```

Older repositories can retain the earlier format without IDs. Use the exact
claim format your repository emits instead of copying an example from an older
guide.

## 4. Treat the AWS error as evidence, not a command to widen access

| Error fragment | First safe check |
| --- | --- |
| `Not authorized to perform: sts:AssumeRoleWithWebIdentity` | Compare `aud` and the exact `sub` condition. |
| `Incorrect token audience` | Inspect the credentials action's audience and the trust-policy audience condition. |
| `InvalidIdentityToken` without an audience message | Preserve the full first error; it is not enough evidence to call this an audience mismatch. |

Use the smallest trust-policy adjustment that admits the intended repository,
branch, or environment. Review the change with the owner of the AWS account
before applying it.

## Official references

- [Configuring OpenID Connect in Amazon Web Services](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [GitHub OIDC claim reference](https://docs.github.com/en/actions/reference/security/oidc)
- [AWS IAM OIDC role guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html)
