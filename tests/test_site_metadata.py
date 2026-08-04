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
    starter = ROOT / "examples" / "github-actions-workflow.yml"
    starter_sync = ROOT / "examples" / "github-actions-workflow-sam-sync.yml"
    starter_cf = ROOT / "examples" / "github-actions-workflow-cf-pipeline.yml"

    assert "fail-on-findings: true" in readme
    assert "fail-on-findings: true" in site
    assert "--fail-on-findings" in readme
    assert "--fail-on-findings" in site
    assert "examples/github-actions-workflow.yml" in readme
    assert "sam-doctor GitHub Actions starter" in site
    assert "github-actions-workflow-sam-sync.yml" in readme
    assert "github-actions-workflow-cf-pipeline.yml" in readme
    assert "github-actions-workflow-sam-sync.yml" in site
    assert "github-actions-workflow-cf-pipeline.yml" in site
    assert starter.exists()
    assert starter_sync.exists()
    assert starter_cf.exists()
