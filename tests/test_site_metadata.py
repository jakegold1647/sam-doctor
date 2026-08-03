import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_site_has_canonical_social_metadata_and_application_schema() -> None:
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    assert '<link rel="canonical" href="https://jakegold1647.github.io/sam-doctor/"' in page
    assert 'property="og:image"' in page
    assert 'name="twitter:image"' in page
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

    assert 'fail-on-findings: "true"' in readme
    assert 'fail-on-findings: "true"' in site
    assert "--fail-on-findings" in readme
    assert "--fail-on-findings" in site
