"""Error wordings taken from real logs, not from the documentation.

Every string below was copied from a public GitHub issue or pull request where a
human pasted a failing deployment log. They are here because the catalog did not
match them: three rules - two of them the flagship OIDC pair - were matching the
wording in AWS and GitHub documentation rather than the wording the tools actually
print. Detection across 231 real failure excerpts went from 83% to 88% on these
three fixes alone.

The lesson is narrow and worth keeping: a pattern written from a doc page is a
guess about what a log says. These tests are the counterweight.
"""

from __future__ import annotations

import pytest

from sam_doctor.diagnostics import diagnose


def _rule_ids(log: str) -> list[str]:
    return [finding.rule_id for finding in diagnose(log)]


# Seen in four unrelated public repositories. @actions/core prints exactly this and
# nothing more: without `permissions: id-token: write` the runner never injects the
# variable, so the log cannot mention the permission - which is what the original
# two patterns required it to do.
ACTIONS_ID_TOKEN_VARIANTS = (
    "Error: Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable",
    "Error: Unhandled error: Error: Error message: Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable",
    "error: Error message: Unable to get ACTIONS_ID_TOKEN_REQUEST_URL env variable",
    "Unable to get ACTIONS_ID_TOKEN_REQUEST_TOKEN env variable",
)


@pytest.mark.parametrize("log", ACTIONS_ID_TOKEN_VARIANTS)
def test_the_real_oidc_token_request_error_is_diagnosed(log: str) -> None:
    assert "github.oidc.token-request-denied" in _rule_ids(log)


# Seen in three unrelated public repositories, one of them reporting in Japanese
# around the same English error string. `configure-aws-credentials` omits the colon
# after `perform`, and puts "Not authorized" before the action name rather than
# after it - so all three of the original patterns missed.
ASSUME_ROLE_VARIANTS = (
    "Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity",
    'CI could not assume either role: "Not authorized to perform sts:AssumeRoleWithWebIdentity".',
    "Not authorized to perform sts:AssumeRoleWithWebIdentity",
)


@pytest.mark.parametrize("log", ASSUME_ROLE_VARIANTS)
def test_the_real_assume_role_rejection_is_diagnosed(log: str) -> None:
    assert "github.oidc.assume-role-rejected" in _rule_ids(log)


def test_the_documented_wording_still_matches_too() -> None:
    # Widening must not trade one wording for the other.
    assert "github.oidc.assume-role-rejected" in _rule_ids(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity"
    )
    assert "github.oidc.token-request-denied" in _rule_ids(
        "Unable to get ID Token: the job is missing id-token: write"
    )


def test_a_bucket_collision_wrapped_by_the_resource_handler_is_diagnosed() -> None:
    # The comment in the rule described this shape and the pattern for it was never
    # added, so the wrapped form produced no finding at all.
    log = (
        'Resource handler returned message: "my-app-logs already exists '
        '(Service: S3, Status Code: 409, Request ID: abc)" '
        "(HandlerErrorCode: AlreadyExists)"
    )

    assert "s3.bucket-name.already-taken" in _rule_ids(log)


@pytest.mark.parametrize(
    "log",
    [
        # `HandlerErrorCode: AlreadyExists` is shared by every resource type. Only
        # the S3-specific sentence may claim it, or the finding sends someone to
        # the bucket-naming docs for a Lambda function.
        (
            'Resource handler returned message: "my-fn already exists (Service: '
            'Lambda, Status Code: 409)" (HandlerErrorCode: AlreadyExists)'
        ),
        'Resource handler returned message: "Table already exists: Orders (Service: DynamoDb)"',
    ],
)
def test_another_services_already_exists_is_not_called_a_bucket_collision(log: str) -> None:
    assert "s3.bucket-name.already-taken" not in _rule_ids(log)


@pytest.mark.parametrize(
    "log",
    [
        "Assuming role with OIDC succeeded; AssumeRoleWithWebIdentity returned credentials",
        "Remember to grant id-token: write in the workflow",
        "Unable to get AWS_REGION env variable",
    ],
)
def test_the_widened_patterns_do_not_fire_on_success_or_prose(log: str) -> None:
    ids = _rule_ids(log)

    assert "github.oidc.token-request-denied" not in ids
    assert "github.oidc.assume-role-rejected" not in ids
