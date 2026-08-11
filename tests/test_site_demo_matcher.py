"""The website's in-page demo must agree with the Python rules it advertises.

`site/index.html` invites a visitor to paste a real failed deployment log and
shows them a diagnosis computed in their browser. That is a claim about this
tool's output, so a browser finding that differs from the CLI's is a wrong
answer published on the front page - and regex dialects differ enough between
Python and JavaScript for that to happen quietly.

Two gates:

- the generated catalog is current with `diagnostics.py` / `redaction.py`
- the shipped JavaScript, run under Node, returns exactly what `diagnose()`
  returns for every rule fixture, every bundled sample, and a redaction corpus

The second needs Node and skips without it. It is the one that matters, so the
skip says so rather than passing silently.
"""

from __future__ import annotations

import importlib.util
import json
import random
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from sam_doctor.diagnostics import diagnose
from sam_doctor.redaction import redact

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "site" / "assets" / "rule-catalog.js"
DEMO_SCRIPT = ROOT / "site" / "assets" / "hero-demo.js"
RUNNER = ROOT / "scripts" / "run-site-demo-matcher.js"


def _load_script(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover - import plumbing
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load_script(
    ROOT / "scripts" / "build-site-rule-catalog.py", "build_site_rule_catalog"
)
FIXTURES = _load_script(
    ROOT / "scripts" / "check-rule-fixtures.py", "check_rule_fixtures_for_demo"
)


def _node() -> str | None:
    return shutil.which("node")


def _run_node(inputs: list[str], mode: str = "diagnose"):
    node = _node()
    assert node is not None
    result = subprocess.run(
        [node, str(RUNNER)],
        input=json.dumps({"mode": mode, "inputs": inputs}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _python_findings(text: str) -> list[dict]:
    return [asdict(finding) for finding in diagnose(text)]


def _normalize(findings) -> list[dict]:
    """Tuples from the dataclass and arrays from JSON have to compare equal."""

    return [
        {
            key: list(value) if isinstance(value, (list, tuple)) else value
            for key, value in finding.items()
        }
        for finding in findings
    ]


def test_committed_catalog_matches_the_python_rule_source() -> None:
    assert CATALOG.exists(), "run scripts/build-site-rule-catalog.py"
    expected = BUILDER.render(BUILDER.build_catalog())
    assert CATALOG.read_text(encoding="utf-8") == expected, (
        "site/assets/rule-catalog.js is stale; regenerate it with "
        "scripts/build-site-rule-catalog.py"
    )


def test_catalog_covers_every_supported_rule() -> None:
    catalog = _catalog_payload()
    assert len(catalog["rules"]) == len(FIXTURES.supported_rules())
    assert {rule["id"] for rule in catalog["rules"]} == {
        rule.id for rule in FIXTURES.supported_rules()
    }


def test_every_bundled_sample_is_offered_in_the_picker() -> None:
    catalog = _catalog_payload()
    on_disk = {path.name for path in BUILDER.SAMPLE_DIR.glob("*.txt")}
    assert {sample["name"] for sample in catalog["samples"]} == on_disk
    assert all(sample["label"] for sample in catalog["samples"])


def _catalog_payload() -> dict:
    text = CATALOG.read_text(encoding="utf-8")
    start = text.index("{", text.index("window.SAM_DOCTOR_CATALOG"))
    return json.loads(text[start:].rstrip().rstrip(";"))


def test_the_static_hero_example_survives_without_javascript() -> None:
    """The fallback is the whole reason the demo is safe to ship."""

    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    example_start = html.index('id="hero-demo-example"')
    example_tag = html.rindex("<div", 0, example_start)
    assert "hidden" not in html[example_tag:example_start], (
        "the worked example must be visible in the markup; hero-demo.js hides "
        "it only after the matcher is ready"
    )
    form_start = html.index('id="hero-demo-form"')
    form_end = html.index(">", form_start)
    assert "hidden" in html[form_start:form_end], (
        "the interactive form must start hidden so it never appears inert"
    )


def test_hidden_actually_hides_inside_the_demo_panel() -> None:
    """`hidden` on a `display: grid` element does nothing without this rule.

    An author `display` declaration beats the user-agent `[hidden] { display:
    none }` rule regardless of specificity, so `.demo-form { display: grid }`
    rendered the whole interactive block before any script ran - the no-script
    state it exists to protect was the one it broke.
    """

    css = (ROOT / "site" / "styles.css").read_text(encoding="utf-8")
    assert "#hero-demo [hidden]" in css, (
        "the demo panel needs a rule that hides [hidden] elements; without it "
        "the form is visible before hero-demo.js runs"
    )
    block = css[css.index("#hero-demo [hidden]") :]
    block = block[: block.index("}")]
    assert "display: none" in block


@pytest.mark.skipif(_node() is None, reason="node is required to run the site matcher")
def test_browser_matcher_agrees_with_python_on_every_rule_fixture() -> None:
    cases: list[str] = []
    labels: list[str] = []
    for rule_id, fixture in FIXTURES.RULE_FIXTURES.items():
        cases.append(fixture.positive)
        labels.append(f"{rule_id} positive")
        cases.append(fixture.negative)
        labels.append(f"{rule_id} negative")

    actual = _run_node(cases)
    mismatches = [
        label
        for label, text, produced in zip(labels, cases, actual)
        if _normalize(produced) != _normalize(_python_findings(text))
    ]
    assert not mismatches, (
        f"{len(mismatches)} of {len(cases)} fixture cases disagree with the "
        f"Python rules: {mismatches[:10]}"
    )


@pytest.mark.skipif(_node() is None, reason="node is required to run the site matcher")
def test_browser_matcher_agrees_with_python_on_realistic_logs() -> None:
    paths = sorted((ROOT / "src" / "sam_doctor" / "data").glob("*.txt"))
    paths += sorted((ROOT / "examples").glob("*.txt"))
    assert paths
    cases = [path.read_text(encoding="utf-8") for path in paths]

    actual = _run_node(cases)
    for path, text, produced in zip(paths, cases, actual):
        assert _normalize(produced) == _normalize(_python_findings(text)), (
            f"{path.name}: the in-page demo reports something the CLI does not"
        )


# Evidence lines are shown to the visitor after redaction, so a redaction pass
# that behaves differently in the browser leaks something the CLI would not.
REDACTION_CORPUS = (
    "Role ARN: arn:aws:iam::123456789012:role/github-production-deploy",
    "Workflow actor: builder@example.com",
    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMIabcdEXAMPLEKEYabcdEXAMPLEKEY",
    "MY_API_KEY: 'sk-abcdefghijklmnopqrstuvwxyz'",
    "permissions: id-token: write",
    "AKIAIOSFODNN7EXAMPLE was rejected",
    "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789",
    "Authorization: Basic dXNlcjpwYXNzd29yZA==",
    "git clone https://oauth2:ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@gitlab/repo",
    "git clone https://ghp_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb@internalhost/repo",
    "docker login -u AWS -p hunter2hunter2 registry.example.com",
    "curl -u ci:supersecrettoken https://example.com/artifact",
    "machine host login ci password hunter2hunter2",
    "POST https://hooks.slack.com/services/T00000000/B00000000/abcdefghijklmnop failed",
    "token: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
    "xoxb-1234567890-abcdefghijkl posted the failure",
    "dckr_pat_abcdefghijklmnopqrstuvwxyz expired",
    "no identifiers on this line at all",
)


@pytest.mark.skipif(_node() is None, reason="node is required to run the site matcher")
def test_browser_redaction_matches_python_redaction() -> None:
    actual = _run_node(list(REDACTION_CORPUS), mode="redact")
    for source, produced in zip(REDACTION_CORPUS, actual):
        assert produced == redact(source), f"redaction differs for: {source!r}"


def _fuzz_corpus(count: int) -> list[str]:
    """Mutated fixture lines: the shapes real CI logs take, deliberately ugly.

    The fixtures are clean single lines, and a clean single line is the case a
    regex dialect difference is least likely to show up in. Colour escapes,
    CRLF, lone carriage returns from progress bars, mixed case, and two rules
    on adjacent lines are all ordinary in a real log and each one exercises a
    different part of the port.
    """

    rng = random.Random(1337)
    seeds = [fixture.positive for fixture in FIXTURES.RULE_FIXTURES.values()]
    seeds += [fixture.negative for fixture in FIXTURES.RULE_FIXTURES.values()]
    alphabet = list("abcXYZ019 \t:/\\-_.,'\"`()[]{}*@#$%&|+=<>?!;\r\n\x1b") + [
        "arn:aws:iam::123456789012:role/example",
        "user@example.com",
        "AKIAIOSFODNN7EXAMPLE",
        "password=hunter2hunter2",
        "\u00e9",
        "\u2028",
    ]
    corpus = []
    for _ in range(count):
        text = rng.choice(seeds)
        for _ in range(rng.randint(1, 5)):
            choice = rng.random()
            cut = rng.randrange(len(text) + 1)
            if choice < 0.3:
                text = text[:cut] + rng.choice(alphabet) + text[cut:]
            elif choice < 0.5 and text:
                drop = rng.randrange(len(text))
                text = text[:drop] + text[drop + 1 :]
            elif choice < 0.7:
                text = text[:cut] + rng.choice(seeds) + text[cut:]
            elif choice < 0.85:
                text = "".join(
                    char.upper() if rng.random() < 0.5 else char.lower()
                    for char in text
                )
            else:
                text = text + "\n" + rng.choice(seeds)
        corpus.append(text)
    return corpus


@pytest.mark.skipif(_node() is None, reason="node is required to run the site matcher")
def test_browser_matcher_agrees_with_python_on_mutated_logs() -> None:
    corpus = _fuzz_corpus(400)
    actual = _run_node(corpus)
    mismatches = [
        text
        for text, produced in zip(corpus, actual)
        if _normalize(produced) != _normalize(_python_findings(text))
    ]
    assert not mismatches, (
        f"{len(mismatches)} of {len(corpus)} mutated logs disagree with the "
        f"Python rules; first: {mismatches[0]!r}"
    )


@pytest.mark.skipif(_node() is None, reason="node is required to run the site matcher")
def test_browser_redaction_agrees_with_python_on_mutated_logs() -> None:
    corpus = _fuzz_corpus(400)
    actual = _run_node(corpus, mode="redact")
    mismatches = [
        text for text, produced in zip(corpus, actual) if produced != redact(text)
    ]
    assert not mismatches, (
        f"{len(mismatches)} of {len(corpus)} mutated logs redact differently; "
        f"first: {mismatches[0]!r}"
    )


@pytest.mark.skipif(_node() is None, reason="node is required to run the site matcher")
def test_the_demo_makes_no_network_call() -> None:
    """The privacy claim in the hero is enforceable, so enforce it."""

    for path in (DEMO_SCRIPT, CATALOG):
        source = path.read_text(encoding="utf-8")
        for forbidden in (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket",
            "navigator.sendBeacon",
            "importScripts",
            "eval(",
        ):
            assert forbidden not in source, (
                f"{path.name} contains {forbidden!r}; the hero states that "
                "nothing leaves the page"
            )
