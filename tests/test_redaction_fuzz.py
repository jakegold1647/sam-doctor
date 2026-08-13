"""Deterministic fuzz: no output format may leak an identifier.

Composes logs from shuffled bundled-sample lines interleaved with synthetic
secrets, then asserts every report format redacts all of them. The seed is
fixed so failures reproduce exactly.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from sam_doctor.cli import _render_findings
from sam_doctor.diagnostics import diagnose

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "src" / "sam_doctor" / "data"

# Key-shaped fixtures are assembled at runtime so secret scanners don't flag
# literal credentials in source; none of these are real.
SECRETS = (
    "AKIA" + "IOSFODNN7EXAMPLE",
    "ASIA" + "Y34FZKBOKMUTVV7A",
    "IQoJb3JpZ2luX2VjENr" + "A1b2C3d4" * 12,
    "ghp_abcdefghij0123456789abcdefghij456789",
    "arn:aws:iam::123456789012:role/deploy-role",
    "111122223333",
    "build-owner@example.com",
    'password="fuzz-hunter2"',
    "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'",
    '"SecretAccessKey": "je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY"',
    "xoxb-" + "1234567890-fuzzslackbot",
    "X-Amz-Signature=" + "deadbeef" * 8,
    # Prefixed UPPER_SNAKE_CASE names: the conventional spelling for an
    # environment variable, and the shape a word boundary on the keyword missed
    # entirely (`\bpassword` never matches inside `DB_PASSWORD`).
    "DB_PASSWORD=fuzz-prefixed-secret",
    "MY_API_KEY=fuzz-prefixed-apikey",
    'DB_PASSWORD="fuzz multi word credential"',
    # Credentials in a URL against a dotless internal host, which the email
    # pattern that used to catch this incidentally cannot match.
    "https://oauth2:glpat-fuzzgitlabtoken12345@gitlab/team/repo.git",
    # Basic auth: base64 of user:password, so it hands over a reusable credential
    # rather than an expiring token. Bearer was handled and this was not.
    "Authorization: Basic ZnV6ei1iYXNpYy1jcmVkZW50aWFs",
    # Incoming webhook URLs, which are credentials in link form - whoever holds
    # one can post as the integration. A deploy notification step prints them
    # when the post fails, which is the log that ends up attached to a report.
    "https://hooks.slack.com/services/T00000000/B00000000/fuzzslackwebhooktoken00",
    "https://discord.com/api/webhooks/123456789012/fuzzdiscordwebhooktoken",
)

LEAK_MARKERS = (
    "fuzz-prefixed-secret",
    "fuzz-prefixed-apikey",
    "fuzz multi word credential",
    "glpat-fuzzgitlabtoken12345",
    "AKIA" + "IOSFODNN7EXAMPLE",
    "ASIA" + "Y34FZKBOKMUTVV7A",
    "IQoJb3JpZ2luX2VjENr",
    "ghp_abcdefghij",
    "123456789012",
    "111122223333",
    "build-owner@example.com",
    "fuzz-hunter2",
    "wJalrXUtnFEMI",
    "je7MtGbClwBF",
    "fuzzslackbot",
    "deadbeef" * 8,
    "ZnV6ei1iYXNpYy1jcmVkZW50aWFs",
    "fuzzslackwebhooktoken00",
    "fuzzdiscordwebhooktoken",
)


def test_fuzzed_logs_never_leak_identifiers_in_any_format() -> None:
    sample_lines = [
        line
        for sample in sorted(SAMPLES_DIR.glob("*.txt"))
        for line in sample.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rng = random.Random(20260804)
    rendered_redactions = 0

    for round_number in range(25):
        lines = rng.sample(sample_lines, k=min(40, len(sample_lines)))
        for secret in rng.sample(SECRETS, k=4):
            position = rng.randrange(len(lines) + 1)
            # Ride each secret on a rule-matching line so it lands in the
            # evidence that reports actually render; a secret on a noise line
            # never reaches the output and would make this test vacuous.
            carrier = rng.choice(
                [
                    f"Not authorized to perform: sts:AssumeRoleWithWebIdentity as {secret}",
                    f"AccessDeniedException for caller {secret}",
                    f"MyResource CREATE_FAILED Resource handler {secret} returned failure",
                    f"An error occurred (Throttling) Rate exceeded for {secret}",
                ]
            )
            lines.insert(position, carrier)
        log = "\n".join(lines)

        findings = diagnose(log)
        # sarif is included defensively rather than because it leaks today: its
        # results carry the title, explanation and a line number, and no evidence
        # snippet, so an evidence-borne secret cannot currently reach it. If a
        # `region.snippet` is ever added - SARIF consumers do expect one - this
        # loop is what stops that change from shipping a leak.
        for output_format in ("terminal", "markdown", "json", "github", "sarif"):
            report = _render_findings(findings, "fuzz.log", output_format)
            for marker in LEAK_MARKERS:
                assert marker not in report, (
                    f"round {round_number}: {marker!r} leaked in {output_format}"
                )
            rendered_redactions += report.count("[REDACTED")

    # Guard against vacuity: the fuzz must actually have pushed secrets into
    # rendered evidence, not just onto lines the reports never show.
    assert rendered_redactions > 50


def test_a_quoted_multi_word_secret_never_leaks_in_any_format() -> None:
    secret = "correct horse battery staple"
    log = f'AccessDeniedException for caller DB_PASSWORD="{secret}"'
    findings = diagnose(log)

    assert findings, "the carrier line must reach rendered evidence"
    for output_format in ("terminal", "markdown", "json", "github", "sarif"):
        report = _render_findings(findings, "quoted-secret.log", output_format)
        assert secret not in report, f"quoted secret leaked in {output_format}"


def _pattern_names(module) -> list[str]:
    """Compiled patterns in the module, by name.

    Selecting on `isinstance(..., re.Pattern)` rather than on the shape of the name:
    the first version of these checks matched any UPPER_CASE module constant, which
    flagged a plain tuple of benign values as an unapplied pattern. A guard that
    reports something it does not understand is a guard people learn to route
    around.
    """

    import re as _re

    return sorted(name for name, value in vars(module).items() if isinstance(value, _re.Pattern))

def test_a_webhook_url_is_redacted_whole_not_in_pieces() -> None:
    # Ordering trap, hit while adding this: a Discord webhook path starts with a
    # numeric id, and the twelve-digit account-id pass rewrites that id first.
    # After that this URL no longer looks like a webhook, so the token half - the
    # part that is actually the secret - survived into the report while the
    # harmless id was starred out. The webhook pass has to run before it.
    from sam_doctor.redaction import redact

    text = "POST https://discord.com/api/webhooks/123456789012/tokenpart-abcdef failed"

    redacted = redact(text)

    assert "tokenpart-abcdef" not in redacted
    assert redacted == "POST [REDACTED_WEBHOOK_URL] failed"


def test_ordinary_documentation_links_are_left_alone() -> None:
    # Over-redaction has a cost of its own: every rule points at a documentation
    # URL, and a report that stars them out is harder to act on.
    from sam_doctor.redaction import redact

    for url in (
        "https://docs.aws.amazon.com/IAM/latest/UserGuide/id_tags.html",
        "https://api.slack.com/messaging/webhooks",
        "https://github.com/jakegold1647/sam-doctor",
    ):
        assert redact(url) == url


def test_the_ecr_rule_line_survives_redaction() -> None:
    # "no basic auth credentials" is the ECR rule's own pattern. A Basic-auth
    # rule that matched the prose would redact the very line a diagnosis needs.
    from sam_doctor.redaction import redact

    line = "Error response from daemon: Head https://registry/v2/app: no basic auth credentials"

    assert "no basic auth credentials" in redact(line)


CREDENTIAL_COMMAND_LINES = (
    # `ecr.auth.login-failed` is a rule in this catalog, so a log with a failed
    # registry login is a log this tool is built to receive - and `-p` puts a live
    # registry credential in it.
    ("docker login -u AWS -p leakmarkerecrtoken 1234.dkr.ecr.us-east-1.amazonaws.com", "leakmarkerecrtoken"),
    ("docker login --password leakmarkerdockerpass registry.example.test", "leakmarkerdockerpass"),
    ("npm login --registry https://npm.example.test --password leakmarkernpmpass", "leakmarkernpmpass"),
    # The .netrc shape: whitespace instead of `=`, invisible to the assignment pattern.
    ("machine registry.example.test login deploy password leakmarkernetrc", "leakmarkernetrc"),
    ("curl -u deploy:leakmarkercurltoken https://api.example.test/v1/build", "leakmarkercurltoken"),
    ("using dckr_pat_" + "abcdefghij0123456789abcdef", "dckr_pat_abcdefghij"),
)


@pytest.mark.parametrize(("line", "marker"), CREDENTIAL_COMMAND_LINES)
def test_credentials_on_a_command_line_are_redacted(line: str, marker: str) -> None:
    from sam_doctor.redaction import redact

    assert marker not in redact(line)


# Redaction has to stay narrow enough to leave build output readable. Each of
# these is a near-miss for one of the patterns above, and several would be
# actively harmful to redact: `--password-stdin` is the *safe* idiom, and starring
# it out would hide the fact that the log shows someone doing the right thing.
MUST_SURVIVE = (
    "aws ecr get-login-password | docker login --password-stdin 1234.dkr.ecr.us-east-1.amazonaws.com",
    "mkdir -p /home/runner/work/app/build/artifacts",
    "cp -p /usr/local/lib/node_modules/pkg/index.js dist/",
    "docker run -p 8080:8080 myimage:latest",
    "Error: password is invalid or has expired",
    "curl -u AWS https://api.example.test/v1/build",
    "Login Succeeded",
    "Error response from daemon: Head https://registry/v2/app: no basic auth credentials",
)


@pytest.mark.parametrize("line", MUST_SURVIVE)
def test_ordinary_build_output_is_not_redacted(line: str) -> None:
    from sam_doctor.redaction import redact

    assert redact(line) == line


def test_the_readme_names_every_redaction_pattern_family() -> None:
    """The README enumerates what redaction covers, and that list is a promise.

    A pattern added without updating it leaves the README claiming less than the
    tool does, which is harmless; the dangerous direction is a pattern *removed*
    while the README still promises it, so a reader trusts coverage that is gone.
    This checks the count rather than the wording, so rephrasing is free but adding
    or removing a family forces a look at the paragraph.
    """

    from sam_doctor import redaction

    families = _pattern_names(redaction)
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    claim = readme[readme.index("Reports redact AWS account IDs") :][:1400]

    assert len(families) == 18, (
        f"redaction has {len(families)} pattern families ({sorted(families)}); "
        "update the README paragraph that enumerates them, then this count"
    )
    for phrase in (
        "account IDs",
        "ARNs",
        "email addresses",
        "bearer tokens",
        "Authorization: Basic",
        "private-key blocks",
        "webhook URLs",
        "login command line",
        "Docker Hub",
    ):
        assert phrase in claim, f"the README no longer mentions {phrase!r}"


def test_every_pattern_is_actually_applied() -> None:
    """A pattern that is defined but never used protects nothing, silently.

    This morning's site-QA gate had exactly that shape: a check for `javascript:`
    links sat below a filter that had already dropped them, so the guard could
    never fire and read as coverage for years. Eighteen patterns applied by hand in
    a fixed order is the same risk - one can be added to the module and left out of
    `redact()`, and every test that does not happen to use it still passes.
    """

    import inspect

    from sam_doctor import redaction

    body = inspect.getsource(redaction.redact)
    unused = [name for name in _pattern_names(redaction) if name not in body]

    assert unused == [], f"defined but never applied in redact(): {unused}"


# `permissions: id-token: write` is a GitHub permission level, and `token` sits in
# the secret-keyword list, so redaction was rewriting it to `id-token=[REDACTED]`.
# That is the evidence line for github.oidc.token-request-denied - the rule that
# fires most often on real logs - so the finding deleted the one word a reader needs
# in order to fix the failure, and mangled the YAML separator while doing it.
CONFIGURATION_NOT_CREDENTIALS = (
    "id-token: write",
    "permissions: id-token: write",
    "the job is missing id-token: write",
    "contents: read",
    "id-token=write",
    "secret: none",
    'id-token: "write"',
    "secret: 'none'",
    "packages: read",
)


@pytest.mark.parametrize("line", CONFIGURATION_NOT_CREDENTIALS)
def test_a_permission_level_is_not_treated_as_a_secret(line: str) -> None:
    from sam_doctor.redaction import redact

    assert redact(line) == line


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # The separator is preserved, so a redacted line keeps the syntax it had.
        ("password: hunter2-real", "password: [REDACTED_SECRET]"),
        ("DB_PASSWORD=s3cr3t-value", "DB_PASSWORD=[REDACTED_SECRET]"),
        ("api_key = abcdef123456", "api_key = [REDACTED_SECRET]"),
        (
            'DB_PASSWORD="correct horse battery staple"',
            'DB_PASSWORD="[REDACTED_SECRET]"',
        ),
        (
            '"SecretAccessKey": "abcdef ghijkl mnop"',
            '"SecretAccessKey": "[REDACTED_SECRET]"',
        ),
        ("password='two words here'", "password='[REDACTED_SECRET]'"),
        ("client_secret=`two words here`", "client_secret=`[REDACTED_SECRET]`"),
        (
            'password="unterminated value remains visible',
            'password="[REDACTED_SECRET]',
        ),
    ],
)
def test_a_real_secret_is_still_redacted_in_place(line: str, expected: str) -> None:
    from sam_doctor.redaction import redact

    assert redact(line) == expected


def test_the_oidc_finding_keeps_its_fix_visible() -> None:
    # End to end: the rule fires, and the evidence still says `write`.
    from sam_doctor.diagnostics import diagnose

    findings = diagnose(
        "Error: Unable to get ID Token. Ensure the workflow grants id-token: write\n"
    )

    assert findings, "the OIDC rule did not fire"
    evidence = " ".join(findings[0].evidence)
    assert "id-token: write" in evidence, evidence
