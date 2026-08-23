"""Public CI recipes must preserve the reviewed onboarding contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = ROOT / "site"
PAGE = SITE_ROOT / "ci-recipes.html"


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_ci_recipe_page_covers_known_credential_free_results() -> None:
    page = _page()

    assert "examples/oidc-assume-role-failure.txt" in page
    assert "github.oidc.assume-role-rejected" in page
    assert "deployment finished with status 0" in page
    assert "no supported pattern was found" in page
    assert "needs no AWS credentials of its own" in page


def test_ci_recipe_page_links_every_checked_in_runner_starter() -> None:
    page = _page()
    starters = (
        "github-actions-workflow.yml",
        "github-actions-workflow-two-phase-gating.yml",
        "github-actions-workflow-sam-sync.yml",
        "github-actions-workflow-cdk.yml",
        "github-actions-workflow-cf-pipeline.yml",
        "github-actions-workflow-batch-logs.yml",
        "gitlab-ci-sam-doctor.yml",
        "circleci-sam-doctor.yml",
        "azure-pipelines-sam-doctor.yml",
        "bitbucket-pipelines-sam-doctor.yml",
    )

    for starter in starters:
        assert (ROOT / "examples" / starter).is_file()
        assert f"/examples/{starter}" in page


def test_ci_recipe_page_keeps_diagnosis_advisory_and_reviewable() -> None:
    page = _page()

    assert "Start advisory. Enforce only after review." in page
    assert "Preserve the deployment command's exit status" in page
    assert "does not inspect or change an AWS stack" in page
    assert "usage_feedback.yml" in page
    assert "report-missed-error.html" in page
    for sensitive_kind in (
        "account IDs",
        "ARNs",
        "request IDs",
        "credentials",
        "tokens",
        "private paths",
        "customer names",
        "private repository names",
    ):
        assert sensitive_kind in page


def test_ci_recipe_page_is_exposed_from_primary_public_indexes() -> None:
    expected_links = {
        SITE_ROOT / "index.html": './ci-recipes.html',
        SITE_ROOT / "quickstart.html": './ci-recipes.html',
        SITE_ROOT / "report-missed-error.html": './ci-recipes.html',
        SITE_ROOT / "errors" / "index.html": '../ci-recipes.html',
        SITE_ROOT / "contributors" / "index.html": '../ci-recipes.html',
    }

    for path, href in expected_links.items():
        assert f'href="{href}"' in path.read_text(encoding="utf-8")

    assert "https://sam-doctor.jacobgoldstein.dev/ci-recipes.html" in (
        SITE_ROOT / "sitemap.xml"
    ).read_text(encoding="utf-8")
    assert "CI recipe chooser" in (SITE_ROOT / "llms.txt").read_text(
        encoding="utf-8"
    )
