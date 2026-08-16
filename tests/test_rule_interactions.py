"""One rule must not silently hide another's finding.

Rules overlap deliberately: a specific reason should speak instead of a
generic one for the same event. But the same mechanism, applied to the whole
log instead of the offending line, hides *unrelated* failures - and a stack
rarely fails exactly one resource. That bug shipped across nine rules before
anyone noticed, because every individual rule's tests passed.

This pairs every rule's positive fixture with every other rule's and checks
which findings disappear. The expected set below is the intended suppression;
anything new is a regression, and anything removed means an intended
suppression stopped working.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from sam_doctor.diagnostics import diagnose

REPO_ROOT = Path(__file__).resolve().parents[1]


def _fixtures() -> dict[str, object]:
    path = REPO_ROOT / "scripts" / "check-rule-fixtures.py"
    spec = importlib.util.spec_from_file_location("check_rule_fixtures", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.RULE_FIXTURES


# (hidden_rule, hiding_rule) pairs that are intended. Each group is one design
# decision, not an accident:
#
# - A generic rule yields to a specific one describing the same event. The
#   change-set, resource-failure, rollback, and access-denied rules are the
#   catch-alls that exist precisely to be outranked.
# - Two rules describe the same underlying failure and only one should speak:
#   expired credentials outrank merely-invalid ones, an in-use export explains
#   a blocked delete, and the Python build failures are one failing build.
#
# Adding a pair here should mean writing down why. If a rule you did not touch
# starts disappearing, that is the bug this test exists to catch.
EXPECTED_HIDING = {
    ("aws.credentials.invalid", "aws.credentials.expired"),
    ("cloudformation.resource.create-update-failed", "cloudformation.lambda-layer.artifact-unreadable"),
    ("cloudformation.resource.create-update-failed", "lambda.code-signing.image-incompatible"),
    ("cloudformation.resource.create-update-failed", "lambda.ecr-image.access-denied"),
    # The inline-policy size reason is carried on the failed resource event itself,
    # so the specific IAM finding owns that line without hiding other resources.
    ("cloudformation.resource.create-update-failed", "iam.role.inline-policy-size-limit"),
    ("cloudformation.stack.delete-failed", "cloudformation.export.in-use"),
    ("cloudformation.stack.rollback-complete", "cloudformation.rollback.iam-role-delete-failed"),
    ("cloudformation.stack.rollback-complete", "cloudformation.stack.failed-recreate-required"),
    ("cloudformation.stack.rollback-complete", "cloudformation.stack.update-rollback-failed"),
    ("cloudformation.stack.rollback-complete", "cloudformation.export.not-found"),
    ("cloudformation.stack.rollback-complete", "cloudformation.template.circular-dependency"),
    ("iam.access-denied.generic", "cloudformation.lambda-layer.artifact-unreadable"),
    ("iam.access-denied.generic", "lambda.ecr-image.access-denied"),
    ("s3.artifact-bucket.access-denied", "cloudformation.lambda-layer.artifact-unreadable"),
    ("sam.build.python-dependency-resolution-failed", "sam.build.python-dependency-validation-failed"),
    ("sam.build.python-dependency-resolution-failed", "sam.build.python-runtime-mismatch"),
    ("sam.build.python-dependency-validation-failed", "sam.build.python-dependency-resolution-failed"),
    ("sam.build.python-dependency-validation-failed", "sam.build.python-runtime-mismatch"),
    ("sam.deploy.configuration-resolution-failed", "aws.credentials.expired"),
    # The CLI reports the API Gateway exception as the concrete reason for the
    # failed change set, so the API-specific checks replace the generic wrapper.
    ("sam.deploy.configuration-resolution-failed", "apigateway.control-plane.throttled"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.api.throttled"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.capabilities.required"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.deploy.no-changes"),
    # A CREATE-type change set against an existing stack names the concrete
    # mistake on the same line as SAM's generic changeset wrapper, so only the
    # stack-name conflict should speak for that event.
    ("sam.deploy.configuration-resolution-failed", "cloudformation.stack.create-name-conflict"),
    # A stack in ROLLBACK_COMPLETE reports "can not be updated" inside the same
    # CreateChangeSet ValidationError this rule matches generically, on one line -
    # so they are one failure, and the recreate-required rule is the one that says
    # to delete and redeploy. Matches the treatment of the *_IN_PROGRESS sibling
    # immediately below.
    ("sam.deploy.configuration-resolution-failed", "cloudformation.stack.failed-recreate-required"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.stack.operation-in-progress"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.template.quota-exceeded"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.export.not-found"),
    ("sam.deploy.configuration-resolution-failed", "cloudformation.template.circular-dependency"),
    ("sam.deploy.configuration-resolution-failed", "s3.artifact-bucket.access-denied"),
    ("sam.deploy.configuration-resolution-failed", "s3.bucket-name.already-taken"),
    ("sam.deploy.configuration-resolution-failed", "s3.bucket-name.invalid"),
    ("sam.deploy.configuration-resolution-failed", "sam.build.esbuild-missing"),
    ("sam.deploy.configuration-resolution-failed", "sam.build.python-dependency-resolution-failed"),
    ("sam.deploy.configuration-resolution-failed", "sam.build.python-dependency-validation-failed"),
    ("sam.deploy.configuration-resolution-failed", "sam.deploy.artifact-upload-failed"),
    ("sam.deploy.configuration-resolution-failed", "sam.deploy.bucket-config-conflict"),
    ("sam.deploy.configuration-resolution-failed", "sam.template.invalid-property"),
    # An unresolvable SSM reference and the generic change-set failure are one
    # event: CloudFormation prints `Error: Failed to create changeset` as the
    # wrapper and the `Parameters: [ssm:...] cannot be found` reason on its own
    # line. Excluding only the reason line would leave the generic rule matching
    # the wrapper, reporting the same failure twice, so this one suppresses for
    # the whole log - the same trade-off already made for the other change-set
    # reasons above.
    ("sam.deploy.configuration-resolution-failed", "ssm.parameter.resolution-failed"),
    ("sam.template.schema-validation-failed", "sam.template.invalid-property"),
    # The VPC CNI wrapper is only a fallback. When the same log includes the
    # nested CreateNetworkInterface response, the EC2 rule has the actionable
    # status and error code, so the wrapper must yield for the whole event.
    ("eks.vpc-cni.pod-sandbox-network-failed", "ec2.network-interface.create-failed"),
    # Network-policy setup is a more specific EKS VPC CNI stage than the generic
    # pod-sandbox wrapper, so the generic handoff yields when it is present.
    ("eks.vpc-cni.pod-sandbox-network-failed", "eks.network-policy.agent-failed"),
    # A bare Kubernetes sandbox wrapper is the last-resort fallback; the EKS
    # rules remain more specific when their plugin or policy stage is named.
    ("kubernetes.pod-sandbox.network-setup-failed", "eks.vpc-cni.pod-sandbox-network-failed"),
    ("kubernetes.pod-sandbox.network-setup-failed", "eks.network-policy.agent-failed"),
    # The asset wrapper names the concrete CDK build stage. When it appears with
    # the broad AssemblyError wrapper, the asset finding is the more useful
    # handoff and the generic synthesis finding yields.
    ("cdk.synth.assembly-failed", "cdk.asset.bundling-failed"),
}


def _observed_hiding() -> set[tuple[str, str]]:
    fixtures = _fixtures()
    rule_ids = sorted(fixtures)
    hiding: set[tuple[str, str]] = set()
    for hidden in rule_ids:
        for hider in rule_ids:
            if hidden == hider:
                continue
            log = f"{fixtures[hidden].positive}\n{fixtures[hider].positive}"
            if hidden not in {finding.rule_id for finding in diagnose(log)}:
                hiding.add((hidden, hider))
    return hiding


def test_no_rule_hides_another_unexpectedly() -> None:
    observed = _observed_hiding()

    unexpected = sorted(observed - EXPECTED_HIDING)
    assert not unexpected, (
        "These rules now disappear when another rule's failure is in the same "
        "log, which means a real failure would go unreported:\n  "
        + "\n  ".join(f"{hidden} hidden by {hider}" for hidden, hider in unexpected)
        + "\n\nIf the two describe the same event, whole-log `suppressed_by` is "
        "right and the pair belongs in EXPECTED_HIDING with a reason. If they "
        "are different events that can co-occur, use `excluded_line_patterns` "
        "so only the overlapping line is skipped."
    )

    stale = sorted(EXPECTED_HIDING - observed)
    assert not stale, (
        "These suppressions are listed as intended but no longer happen; drop "
        f"them from EXPECTED_HIDING if that is deliberate: {stale}"
    )


@pytest.mark.parametrize(
    "generic_rule",
    (
        "cloudformation.resource.create-update-failed",
        "iam.access-denied.generic",
        "sam.deploy.configuration-resolution-failed",
    ),
)
def test_catch_all_rules_are_the_ones_that_yield(generic_rule: str) -> None:
    """The catch-alls should be outranked, never the other way round."""

    observed = _observed_hiding()
    assert any(hidden == generic_rule for hidden, _ in observed), (
        f"{generic_rule} is a catch-all and should yield to specific rules"
    )
