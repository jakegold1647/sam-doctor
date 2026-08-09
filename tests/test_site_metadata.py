import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[1]


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


class _VisibleFaqParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[tuple[str, str]] = []
        self._stack: list[tuple[str, bool, bool, bool, bool]] = []
        self._faq_depth = 0
        self._hidden_depth = 0
        self._summary_depth = 0
        self._current: tuple[list[str], list[str]] | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        opens_hidden = "hidden" in attributes or (
            (attributes.get("aria-hidden") or "").lower() == "true"
        )
        visible = self._hidden_depth == 0 and not opens_hidden
        classes = (attributes.get("class") or "").split()
        opens_faq = visible and "faq" in classes
        if opens_faq:
            self._faq_depth += 1

        opens_details = (
            visible
            and self._faq_depth > 0
            and tag == "details"
            and self._current is None
        )
        if opens_details:
            self._current = ([], [])

        opens_summary = visible and self._current is not None and tag == "summary"
        if opens_summary:
            self._summary_depth += 1

        if opens_hidden:
            self._hidden_depth += 1
        self._stack.append(
            (tag, opens_faq, opens_details, opens_summary, opens_hidden)
        )

    def handle_endtag(self, tag: str) -> None:
        start_tag, opens_faq, opens_details, opens_summary, opens_hidden = (
            self._stack.pop()
        )
        assert start_tag == tag
        if opens_summary:
            self._summary_depth -= 1
        if opens_details:
            assert self._current is not None
            question, answer = self._current
            self.entries.append(
                (
                    _normalize_whitespace("".join(question)),
                    _normalize_whitespace("".join(answer)),
                )
            )
            self._current = None
        if opens_faq:
            self._faq_depth -= 1
        if opens_hidden:
            self._hidden_depth -= 1

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        # Void elements cannot open a FAQ, details, or summary region.
        return

    def handle_data(self, data: str) -> None:
        if self._current is None or self._hidden_depth > 0:
            return
        question, answer = self._current
        if self._summary_depth:
            question.append(data)
        else:
            answer.append(data)


def _current_version() -> str:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project: dict[str, Any] = payload["project"]
    return str(project["version"])


def test_site_has_canonical_social_metadata_and_application_schema() -> None:
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    assert '<link rel="canonical" href="https://sam-doctor.jacobgoldstein.dev/"' in page
    assert 'name="author" content="Jake Goldstein"' in page
    assert 'name="geo.region" content="US"' in page
    assert 'name="geo.placename" content="United States"' in page
    assert 'https://jacobgoldstein.dev' in page
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
    assert schema["softwareVersion"] == _current_version()
    assert schema["offers"]["price"] == "0"
    assert schema["publisher"]["name"] == "Jake Goldstein"
    assert schema["publisher"]["url"] == "https://jacobgoldstein.dev"


def test_homepage_faq_schema_matches_visible_faq_in_order() -> None:
    page = (ROOT / "site" / "index.html").read_text(encoding="utf-8")

    schemas = [
        json.loads(match.group(1))
        for match in re.finditer(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            page,
            flags=re.DOTALL,
        )
    ]
    faq_schemas = [schema for schema in schemas if schema.get("@type") == "FAQPage"]
    assert faq_schemas, "homepage must publish FAQPage structured data"

    structured_entries = []
    for schema in faq_schemas:
        for entity in schema["mainEntity"]:
            assert entity["@type"] == "Question"
            assert entity["acceptedAnswer"]["@type"] == "Answer"
            structured_entries.append(
                (
                    _normalize_whitespace(entity["name"]),
                    _normalize_whitespace(entity["acceptedAnswer"]["text"]),
                )
            )

    parser = _VisibleFaqParser()
    parser.feed(page)
    parser.close()
    assert parser.entries, "homepage must contain visible .faq details"
    assert structured_entries == parser.entries


def test_quickstart_page_has_metadata_and_guide_schema() -> None:
    page = (ROOT / "site" / "quickstart.html").read_text(encoding="utf-8")

    assert '<link rel="canonical" href="https://sam-doctor.jacobgoldstein.dev/quickstart.html"' in page
    assert "geo.region" in page
    assert "geo.placename" in page
    assert 'property="og:image"' in page
    assert 'name="twitter:image"' in page
    assert "application/ld+json" in page
    assert '"@type": "HowTo"' in page
    assert "Install SAM Doctor" in page


def test_action_examples_show_opt_in_failure_gate() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    matrix_doc = (ROOT / "docs" / "ci-command-matrix.md").read_text(encoding="utf-8")
    integration_doc = (ROOT / "docs" / "github-actions-integration.md").read_text(
        encoding="utf-8"
    )
    starter = ROOT / "examples" / "github-actions-workflow.yml"
    starter_sync = ROOT / "examples" / "github-actions-workflow-sam-sync.yml"
    starter_cf = ROOT / "examples" / "github-actions-workflow-cf-pipeline.yml"
    starter_cdk = ROOT / "examples" / "github-actions-workflow-cdk.yml"
    starter_gitlab = ROOT / "examples" / "gitlab-ci-sam-doctor.yml"
    starter_circle = ROOT / "examples" / "circleci-sam-doctor.yml"
    starter_azure = ROOT / "examples" / "azure-pipelines-sam-doctor.yml"
    starter_bitbucket = ROOT / "examples" / "bitbucket-pipelines-sam-doctor.yml"
    starter_two_phase = ROOT / "examples" / "github-actions-workflow-two-phase-gating.yml"

    assert "fail-on-findings: true" in readme
    assert "fail-on-findings: true" in site
    assert "--fail-on-findings" in readme
    assert "--fail-on-findings" in site
    assert "examples/github-actions-workflow.yml" in readme
    assert "sam-doctor GitHub Actions starter" in site
    assert "github-actions-workflow-sam-sync.yml" in readme
    assert "github-actions-workflow-cdk.yml" in readme
    assert "github-actions-workflow-cf-pipeline.yml" in readme
    assert "gitlab-ci-sam-doctor.yml" in readme
    assert "circleci-sam-doctor.yml" in readme
    assert "azure-pipelines-sam-doctor.yml" in readme
    assert "bitbucket-pipelines-sam-doctor.yml" in readme
    assert "github-actions-workflow-two-phase-gating.yml" in readme
    assert "ci-command-matrix.md" in readme
    assert "ci-command-matrix.md" in site
    assert "has-findings" in readme
    assert "finding-count" in readme
    assert "has-findings" in integration_doc
    assert "finding-count" in integration_doc
    assert "sam sync" in matrix_doc
    assert "examples/README.md" in readme
    assert "github-actions-workflow-sam-sync.yml" in site
    assert "github-actions-workflow-cdk.yml" in site
    assert "github-actions-workflow-cf-pipeline.yml" in site
    assert "gitlab-ci-sam-doctor.yml" in site
    assert "circleci-sam-doctor.yml" in site
    assert "azure-pipelines-sam-doctor.yml" in site
    assert "bitbucket-pipelines-sam-doctor.yml" in site
    assert "github-actions-workflow-two-phase-gating.yml" in site
    assert "examples/README.md" in site
    assert starter.exists()
    assert starter_sync.exists()
    assert starter_cf.exists()
    assert starter_cdk.exists()
    assert starter_gitlab.exists()
    assert starter_circle.exists()
    assert starter_azure.exists()
    assert starter_bitbucket.exists()
    assert starter_two_phase.exists()


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
        "github-actions-workflow-cdk.yml",
        "gitlab-ci-sam-doctor.yml",
        "circleci-sam-doctor.yml",
        "azure-pipelines-sam-doctor.yml",
        "bitbucket-pipelines-sam-doctor.yml",
        "github-actions-workflow-two-phase-gating.yml",
    ]:
        assert name in contents
    assert "ci-command-matrix.md" in contents

    assert starter_default.exists()
    assert starter_sync.exists()
    assert starter_cf.exists()
    assert (ROOT / "examples" / "github-actions-workflow-cdk.yml").exists()
    assert (ROOT / "examples" / "gitlab-ci-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "circleci-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "azure-pipelines-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "bitbucket-pipelines-sam-doctor.yml").exists()
    assert (ROOT / "examples" / "github-actions-workflow-two-phase-gating.yml").exists()


def test_researcher_overview_doc_is_discoverable() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    overview = ROOT / "RESEARCHER_OVERVIEW.md"

    assert overview.exists()
    assert "RESEARCHER_OVERVIEW.md" in readme
    assert "RESEARCHER_OVERVIEW.md" in site
