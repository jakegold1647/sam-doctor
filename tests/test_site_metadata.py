import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_site_has_canonical_social_metadata_and_application_schema() -> None:
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    assert '<link rel="canonical" href="https://jakegold1647.github.io/sam-doctor/"' in page
    assert 'property="og:image"' in page
    assert 'meta name="keywords"' in page
    assert 'name="twitter:image"' in page
    assert 'property="og:locale"' in page
    assert 'https://pypi.org/project/sam-doctor/' in page

    match = re.search(
        r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
        page,
        flags=re.DOTALL,
    )
    assert match is not None
    schema = json.loads(match.group(1))
    assert schema["@type"] == "SoftwareApplication"
    assert schema["name"] == "SAM Doctor"
    assert schema["softwareVersion"] == "0.7.7"
    assert schema["offers"]["price"] == "0"


def test_action_examples_show_opt_in_failure_gate() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    matrix_doc = (ROOT / "docs" / "ci-command-matrix.md").read_text(encoding="utf-8")
    starter = ROOT / "examples" / "github-actions-workflow.yml"
    starter_sync = ROOT / "examples" / "github-actions-workflow-sam-sync.yml"
    starter_cf = ROOT / "examples" / "github-actions-workflow-cf-pipeline.yml"
    starter_gitlab = ROOT / "examples" / "gitlab-ci-sam-doctor.yml"
    starter_circle = ROOT / "examples" / "circleci-sam-doctor.yml"
    starter_azure = ROOT / "examples" / "azure-pipelines-sam-doctor.yml"
    starter_bitbucket = ROOT / "examples" / "bitbucket-pipelines-sam-doctor.yml"

    assert "fail-on-findings: true" in readme
    assert "fail-on-findings: true" in site
    assert "--fail-on-findings" in readme
    assert "--fail-on-findings" in site
    assert "examples/github-actions-workflow.yml" in readme
    assert "sam-doctor GitHub Actions starter" in site
    assert "github-actions-workflow-sam-sync.yml" in readme
    assert "github-actions-workflow-cf-pipeline.yml" in readme
    assert "gitlab-ci-sam-doctor.yml" in readme
    assert "circleci-sam-doctor.yml" in readme
    assert "azure-pipelines-sam-doctor.yml" in readme
    assert "bitbucket-pipelines-sam-doctor.yml" in readme
    assert "ci-command-matrix.md" in readme
    assert "ci-command-matrix.md" in site
    assert "sam sync" in matrix_doc
    assert "examples/README.md" in readme
    assert "github-actions-workflow-sam-sync.yml" in site
    assert "github-actions-workflow-cf-pipeline.yml" in site
    assert "gitlab-ci-sam-doctor.yml" in site
    assert "circleci-sam-doctor.yml" in site
    assert "azure-pipelines-sam-doctor.yml" in site
    assert "bitbucket-pipelines-sam-doctor.yml" in site
    assert "examples/README.md" in site
    assert starter.exists()
    assert starter_sync.exists()
    assert starter_cf.exists()
    assert starter_gitlab.exists()
    assert starter_circle.exists()
    assert starter_azure.exists()
    assert starter_bitbucket.exists()


def test_examples_index_and_starters_are_documented() -> None:
    examples_readme = ROOT / "examples" / "README.md"
    starter_sync = ROOT / "examples" / "github-actions-workflow-sam-sync.yml"
    starter_cf = ROOT / "examples" / "github-actions-workflow-cf-pipeline.yml"
    starter_default = ROOT / "examples" / "github-actions-workflow.yml"

    assert examples_readme.exists()
    contents = examples_readme.read_text(encoding="utf-8")
    for name in [
        "github-actions-workflow.yml",
        "github-actions-workflow-sam-sync.yml",
        "github-actions-workflow-cf-pipeline.yml",
        "gitlab-ci-sam-doctor.yml",
        "circleci-sam-doctor.yml",
        "azure-pipelines-sam-doctor.yml",
        "bitbucket-pipelines-sam-doctor.yml",
    ]:
        assert name in contents
    assert "ci-command-matrix.md" in contents

    assert starter_default.exists()
    assert starter_sync.exists()
    assert starter_cf.exists()
    assert (ROOT / "examples" / "gitlab-ci-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "circleci-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "azure-pipelines-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "bitbucket-pipelines-sam-doctor.yml").exists()
