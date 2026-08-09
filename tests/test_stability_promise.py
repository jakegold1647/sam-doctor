"""Enforce the commitments in docs/stability.md.

The promise is only worth what it is checked against. Two of its clauses can be
verified mechanically, and both had already drifted or could drift silently:

- the list of subcommands it names was missing `request-packet`, which has
  shipped for a while, so a reader could not tell whether it was covered;
- rule ids are promised never to change, but nothing compared the current
  catalog against the ids that have actually been released.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from conftest import child_env

from sam_doctor.cli import _build_parser
from sam_doctor.diagnostics import supported_rules

REPO_ROOT = Path(__file__).resolve().parents[1]
STABILITY_DOC = REPO_ROOT / "docs" / "stability.md"

# Rule ids that have shipped in a published release. The promise is that these
# keep working forever: an id may be added, never removed or renamed, because
# integrations are told to match on the id rather than the title.
#
# Seeded from v0.11.0 (48 rules). When a release goes out, append the ids it
# introduced. Nothing needs adding for an unreleased rule - the check is that
# every id here still exists, not that every current id is listed.
SHIPPED_RULE_IDS = frozenset(
    {
        "apigateway.cors.preflight-conflict",
        "apigateway.deployment.no-methods",
        "aws.credentials.expired",
        "aws.credentials.invalid",
        "cloudformation.api.throttled",
        "cloudformation.capabilities.required",
        "cloudformation.deploy.no-changes",
        "cloudformation.export.in-use",
        "cloudformation.lambda-layer.artifact-unreadable",
        "cloudformation.nested-stack.propagation-failed",
        "cloudformation.resource.create-update-failed",
        "cloudformation.resource.stabilization-timeout",
        "cloudformation.rollback.iam-role-delete-failed",
        "cloudformation.stack.delete-failed",
        "cloudformation.stack.failed-recreate-required",
        "cloudformation.stack.operation-in-progress",
        "cloudformation.stack.rollback-complete",
        "cloudformation.stack.termination-protection",
        "cloudformation.stack.update-rollback-failed",
        "cloudformation.template.quota-exceeded",
        "ecr.auth.login-failed",
        "github.oidc.assume-role-rejected",
        "github.oidc.audience-mismatch",
        "github.oidc.provider-missing",
        "github.oidc.token-request-denied",
        "iam.access-denied.generic",
        "iam.deny.explicit",
        "iam.deny.implicit",
        "iam.trust-policy.resource-field-invalid",
        "lambda.code-signing.image-incompatible",
        "lambda.code-storage.limit-exceeded",
        "lambda.concurrency.reserved-below-minimum",
        "lambda.ecr-image.access-denied",
        "lambda.package.size-limit-exceeded",
        "s3.artifact-bucket.access-denied",
        "s3.bucket-name.already-taken",
        "s3.bucket-name.invalid",
        "sam.build.docker-required",
        "sam.build.esbuild-missing",
        "sam.build.python-dependency-resolution-failed",
        "sam.build.python-dependency-validation-failed",
        "sam.build.python-runtime-mismatch",
        "sam.deploy.artifact-upload-failed",
        "sam.deploy.bucket-config-conflict",
        "sam.deploy.configuration-resolution-failed",
        "sam.deploy.interactive-confirmation-required",
        "sam.template.invalid-property",
        "sam.template.schema-validation-failed",
    }
)


def _documented_subcommands() -> set[str]:
    text = STABILITY_DOC.read_text(encoding="utf-8")
    clause = re.search(r"\*\*CLI surface\.\*\*(.+?)\n-\s\*\*", text, re.DOTALL)
    assert clause, "could not find the CLI surface clause in docs/stability.md"
    return set(re.findall(r"`([a-z][a-z-]*)`", clause.group(1)))


def _registered_subcommands() -> set[str]:
    parser = _build_parser()
    for action in parser._actions:
        if getattr(action, "choices", None) and action.dest == "command":
            return set(action.choices)
    raise AssertionError("could not find the subparser action on the CLI parser")


def test_stability_doc_lists_every_shipped_subcommand() -> None:
    documented = _documented_subcommands()
    registered = _registered_subcommands()

    missing = sorted(registered - documented)
    assert not missing, (
        "these subcommands ship but are not named in the CLI surface clause of "
        f"docs/stability.md, so a reader cannot tell whether they are covered: {missing}"
    )

    stale = sorted(documented - registered)
    assert not stale, (
        f"docs/stability.md promises subcommands that no longer exist: {stale}"
    )


def test_no_released_rule_id_has_disappeared() -> None:
    current = {rule.id for rule in supported_rules()}

    missing = sorted(SHIPPED_RULE_IDS - current)
    assert not missing, (
        "these rule ids have shipped in a release, and docs/stability.md promises "
        "they do not change - integrations match on the id, not the title. "
        f"Removed or renamed: {missing}"
    )


def test_the_shipped_id_baseline_is_not_stale_nonsense() -> None:
    # Guard the guard: if every baseline id vanished from the catalog the test
    # above would still pass on an empty baseline, so assert the baseline is
    # actually describing this project.
    current = {rule.id for rule in supported_rules()}

    assert len(SHIPPED_RULE_IDS) >= 48
    assert SHIPPED_RULE_IDS <= current


def test_documented_subcommands_all_run() -> None:
    # A promised subcommand that errors on --help is not a stable surface.
    for command in sorted(_documented_subcommands()):
        result = subprocess.run(
            [sys.executable, "-m", "sam_doctor.cli", command, "--help"],
            capture_output=True,
            text=True,
            env=child_env(),
            check=False,
        )
        assert result.returncode == 0, f"{command} --help exited {result.returncode}"
