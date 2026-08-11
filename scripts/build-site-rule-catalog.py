#!/usr/bin/env python3
"""Generate the browser rule catalog for the website's in-page demo.

`site/index.html` lets a visitor paste a failed deployment log and get the same
first finding the CLI would report, without the log leaving the page. That only
stays honest if the browser matches on *these* rules, so the catalog is
generated from `sam_doctor.diagnostics` and `sam_doctor.redaction` rather than
transcribed. Run with `--check` to fail when the committed file no longer
matches the Python source - that is the drift gate, and it runs in the tests.

The rule patterns are Python regular expressions and the browser needs
JavaScript ones. Almost all of them are already common syntax; the translator
below converts the handful of constructs that are not (`(?s:...)` scoped
modifier groups, `\\Z`, `re.VERBOSE` layout) and refuses to guess about
anything it does not recognize. A pattern that cannot be translated is a build
failure, not a silently dropped rule.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor import __version__, diagnostics, redaction

OUTPUT_PATH = REPO_ROOT / "site" / "assets" / "rule-catalog.js"
SAMPLE_DIR = REPO_ROOT / "src" / "sam_doctor" / "data"

# Short, human labels for the bundled sample logs offered by "Try a sample
# failure". The keys are the shipped filenames; a sample without a label here
# is a build failure so a new one cannot appear in the picker unnamed.
SAMPLE_LABELS = {
    "oidc-assume-role-failure.txt": "GitHub Actions OIDC role assumption",
    "cloudformation-resource-failure.txt": "CloudFormation resource failure",
    "capability-acknowledgement-failure.txt": "Missing IAM capability",
    "python-pip-build-failure.txt": "Python build dependency failure",
    "s3-bucket-conflict-failure.txt": "S3 bucket configuration conflict",
    "interactive-changeset-failure.txt": "Interactive changeset prompt",
    "esbuild-missing-failure.txt": "esbuild not found",
    "api-gateway-no-methods-failure.txt": "API Gateway stage has no methods",
}

# The order samples appear in the picker. First entry is the default sample.
SAMPLE_ORDER = (
    "oidc-assume-role-failure.txt",
    "cloudformation-resource-failure.txt",
    "capability-acknowledgement-failure.txt",
    "python-pip-build-failure.txt",
    "s3-bucket-conflict-failure.txt",
    "interactive-changeset-failure.txt",
    "esbuild-missing-failure.txt",
    "api-gateway-no-methods-failure.txt",
)


class UntranslatablePattern(RuntimeError):
    """A Python regex construct with no safe JavaScript equivalent."""


def _strip_verbose(pattern: str) -> str:
    """Remove `re.VERBOSE` whitespace and comments, preserving semantics."""

    out: list[str] = []
    index = 0
    in_class = False
    while index < len(pattern):
        char = pattern[index]
        if char == "\\" and index + 1 < len(pattern):
            out.append(pattern[index : index + 2])
            index += 2
            continue
        if in_class:
            if char == "]":
                in_class = False
            out.append(char)
            index += 1
            continue
        if char == "[":
            in_class = True
            out.append(char)
            index += 1
            continue
        if char == "#":
            while index < len(pattern) and pattern[index] != "\n":
                index += 1
            continue
        if char.isspace():
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


_GROUP_OPENERS = ("(?:", "(?=", "(?!", "(?<=", "(?<!")
_REJECTED_OPENERS = ("(?P", "(?#", "(?(", "(?>", "(?&")
_MODIFIER_GROUP = re.compile(r"\(\?([aimsux]+)(?:-[aimsux]+)?([:)])")


def translate_pattern(pattern: str, *, verbose: bool = False) -> tuple[str, set[str]]:
    """Translate a Python pattern to JavaScript source plus required flags.

    Returns the JavaScript regex body and the set of flags the translation
    depends on (`i` when the pattern carried an inline case-insensitive
    modifier). Raises `UntranslatablePattern` rather than emitting something
    that would match differently in a browser.
    """

    if verbose:
        pattern = _strip_verbose(pattern)

    flags: set[str] = set()
    out: list[str] = []
    # One entry per open group: True when `.` inside it means "any character
    # including a newline" because a `(?s:...)` modifier group encloses it.
    group_dotall: list[bool] = []
    dotall_depth = 0
    index = 0
    in_class = False

    while index < len(pattern):
        char = pattern[index]

        if char == "\\":
            if index + 1 >= len(pattern):
                raise UntranslatablePattern("pattern ends with a lone backslash")
            following = pattern[index + 1]
            if following == "Z" and not in_class:
                # Python's absolute end-of-string. JavaScript's `$` means the
                # same thing as long as the `m` flag is absent, which it is.
                out.append("$")
                index += 2
                continue
            if following == "A" and not in_class:
                out.append("^")
                index += 2
                continue
            if following in "zGKQEpP":
                raise UntranslatablePattern(rf"unsupported escape \{following}")
            out.append(char)
            out.append(following)
            index += 2
            continue

        if in_class:
            if char == "]":
                in_class = False
            out.append(char)
            index += 1
            continue

        if char == "[":
            in_class = True
            out.append(char)
            index += 1
            if index < len(pattern) and pattern[index] == "^":
                out.append("^")
                index += 1
            if index < len(pattern) and pattern[index] == "]":
                # A literal `]` directly after `[` closes nothing in Python but
                # does close the class in JavaScript, so escape it.
                out.append("\\]")
                index += 1
            continue

        if char == ".":
            out.append("[\\s\\S]" if dotall_depth else ".")
            index += 1
            continue

        if char == "(":
            rest = pattern[index:]
            if any(rest.startswith(bad) for bad in _REJECTED_OPENERS):
                raise UntranslatablePattern(f"unsupported group {rest[:4]!r}")
            opener = next((o for o in _GROUP_OPENERS if rest.startswith(o)), None)
            if opener is not None:
                out.append(opener)
                group_dotall.append(False)
                index += len(opener)
                continue
            modifier = _MODIFIER_GROUP.match(rest)
            if modifier is not None:
                letters, terminator = modifier.group(1), modifier.group(2)
                unsupported = set(letters) - {"i", "s"}
                if unsupported:
                    raise UntranslatablePattern(
                        f"unsupported inline flags {''.join(sorted(unsupported))!r}"
                    )
                if terminator == ")":
                    # A whole-pattern inline modifier such as `(?i)`.
                    if "s" in letters:
                        raise UntranslatablePattern(
                            "whole-pattern (?s) is not translated; use (?s:...)"
                        )
                    flags.add("i")
                    index += modifier.end()
                    continue
                # A scoped modifier group such as `(?s:...)`. Scoped `i` is only
                # safe because every catalog pattern is matched case-insensitively
                # anyway; record the dependency so the flag is not dropped.
                if "i" in letters:
                    flags.add("i")
                enables_dotall = "s" in letters
                out.append("(?:")
                group_dotall.append(enables_dotall)
                if enables_dotall:
                    dotall_depth += 1
                index += modifier.end()
                continue
            if rest.startswith("(?"):
                raise UntranslatablePattern(f"unrecognized group {rest[:4]!r}")
            out.append("(")
            group_dotall.append(False)
            index += 1
            continue

        if char == ")":
            if group_dotall and group_dotall.pop():
                dotall_depth -= 1
            out.append(char)
            index += 1
            continue

        out.append(char)
        index += 1

    if in_class or group_dotall:
        raise UntranslatablePattern("unbalanced group or character class")
    return "".join(out), flags


def _js_regex(pattern: str, base_flags: str, *, verbose: bool = False) -> dict:
    source, extra = translate_pattern(pattern, verbose=verbose)
    flags = "".join(sorted(set(base_flags) | extra))
    return {"source": source, "flags": flags}


# The redaction passes, in the exact order `redaction.redact()` applies them,
# each paired with the JavaScript replacement template that reproduces its
# Python substitution. `@url-credentials` marks the one pass whose replacement
# is a decision rather than a template; the browser implements it by name.
REDACTION_PASSES: tuple[tuple[str, str], ...] = (
    ("_WEBHOOK_URL", "[REDACTED_WEBHOOK_URL]"),
    ("_LOGIN_PASSWORD_FLAG", "$1$2$3[REDACTED_PASSWORD]"),
    ("_NETRC_PASSWORD", "$1 [REDACTED_PASSWORD]"),
    ("_CURL_USERINFO", "$1$2$3:[REDACTED_PASSWORD]"),
    ("_DOCKER_HUB_TOKEN", "[REDACTED_DOCKER_TOKEN]"),
    ("_ARN", "[REDACTED_ARN]"),
    ("_ACCOUNT_ID", "[REDACTED_ACCOUNT_ID]"),
    ("_AWS_ACCESS_KEY_ID", "[REDACTED_AWS_ACCESS_KEY]"),
    ("_AWS_SESSION_TOKEN", "[REDACTED_AWS_SESSION_TOKEN]"),
    ("_GITHUB_TOKEN", "[REDACTED_GITHUB_TOKEN]"),
    ("_SLACK_TOKEN", "[REDACTED_SLACK_TOKEN]"),
    ("_PRIVATE_KEY_BLOCK", "[REDACTED_PRIVATE_KEY]"),
    ("_BEARER_TOKEN", "$1 [REDACTED_BEARER_TOKEN]"),
    ("_BASIC_AUTH", "$1 [REDACTED_BASIC_AUTH]"),
    ("_SECRET_ASSIGNMENT", "$1$2[REDACTED_SECRET]"),
    ("_JWT", "[REDACTED_JWT]"),
    ("_URL_CREDENTIALS", "@url-credentials"),
    ("_EMAIL", "[REDACTED_EMAIL]"),
)


def _redaction_catalog() -> list[dict]:
    """Translate every redaction pass, failing if the module gained or lost one."""

    known = {name for name, _ in REDACTION_PASSES}
    present = {
        name
        for name in vars(redaction)
        if name.startswith("_") and isinstance(getattr(redaction, name), re.Pattern)
    }
    if known != present:
        missing = sorted(present - known)
        stale = sorted(known - present)
        raise SystemExit(
            "redaction passes changed; update REDACTION_PASSES in this script "
            f"(new: {missing}, removed: {stale})"
        )

    passes = []
    for name, replacement in REDACTION_PASSES:
        compiled: re.Pattern = getattr(redaction, name)
        verbose = bool(compiled.flags & re.VERBOSE)
        entry = _js_regex(compiled.pattern, "g", verbose=verbose)
        if compiled.flags & re.IGNORECASE:
            entry["flags"] = "".join(sorted(set(entry["flags"]) | {"i"}))
        entry["name"] = name.lstrip("_").lower()
        entry["replacement"] = replacement
        passes.append(entry)
    return passes


def _rule_catalog() -> list[dict]:
    rules = []
    for rule in diagnostics.supported_rules():
        rules.append(
            {
                "id": rule.id,
                "title": rule.title,
                "confidence": rule.confidence,
                "patterns": [_js_regex(p, "i") for p in rule.patterns],
                "explanation": rule.explanation,
                "verification": list(rule.verification),
                "documentation_url": rule.documentation_url,
                "suppressed_by": [_js_regex(p, "i") for p in rule.suppressed_by],
                "excluded_line_patterns": [
                    _js_regex(p, "i") for p in rule.excluded_line_patterns
                ],
                "parse_denial_context": rule.parse_denial_context,
                "parse_stabilization_context": rule.parse_stabilization_context,
            }
        )
    return rules


def _samples() -> list[dict]:
    on_disk = {path.name for path in SAMPLE_DIR.glob("*.txt")}
    unlabelled = sorted(on_disk - set(SAMPLE_LABELS))
    if unlabelled:
        raise SystemExit(
            "bundled sample has no label for the website picker; add it to "
            f"SAMPLE_LABELS: {unlabelled}"
        )
    ordered = [name for name in SAMPLE_ORDER if name in on_disk]
    ordered += sorted(on_disk - set(ordered))
    return [
        {
            "name": name,
            "label": SAMPLE_LABELS[name],
            "log": (SAMPLE_DIR / name).read_text(encoding="utf-8"),
        }
        for name in ordered
    ]


def build_catalog() -> dict:
    """Assemble everything the browser matcher needs, from the Python source."""

    return {
        "sam_doctor_version": __version__,
        "max_evidence_length": diagnostics._MAX_EVIDENCE_LENGTH,
        "max_evidence_lines": 3,
        "ansi_escape": _js_regex(
            diagnostics._ANSI_ESCAPE.pattern, "g", verbose=True
        ),
        "redaction": _redaction_catalog(),
        "denial_context": {
            "action": _js_regex(diagnostics._DENIED_ACTION.pattern, ""),
            "principal": _js_regex(diagnostics._DENIED_PRINCIPAL.pattern, "i"),
            "resource": _js_regex(diagnostics._DENIED_RESOURCE.pattern, "i"),
            "explicit_deny_scp": _js_regex(
                diagnostics._EXPLICIT_DENY_SCP.pattern, "i"
            ),
            "explicit_deny": _js_regex(diagnostics._EXPLICIT_DENY.pattern, "i"),
            "implicit_deny_layer": _js_regex(
                diagnostics._IMPLICIT_DENY_LAYER.pattern, "i"
            ),
        },
        "stabilization_context": {
            "handler_message": _js_regex(diagnostics._HANDLER_MESSAGE.pattern, "i"),
            "resource_type": _js_regex(diagnostics._RESOURCE_TYPE.pattern, ""),
            "slow_resource_hints": [
                list(entry) for entry in diagnostics._SLOW_RESOURCE_HINTS
            ],
        },
        "rules": _rule_catalog(),
        "samples": _samples(),
    }


def render(catalog: dict) -> str:
    """Render the catalog as a plain script that defines a global.

    A script rather than a JSON fetch on purpose: the page then makes no
    network request at all to run a diagnosis, which is the claim the demo is
    making, and it works just as well from a local copy of the site.
    """

    payload = json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=False)
    return (
        "/* Generated by scripts/build-site-rule-catalog.py from\n"
        " * src/sam_doctor/diagnostics.py and src/sam_doctor/redaction.py.\n"
        " * Do not edit by hand: regenerate instead, or the in-page demo will\n"
        " * disagree with the CLI it is demonstrating. */\n"
        "window.SAM_DOCTOR_CATALOG = "
        + payload
        + ";\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero when the committed catalog is out of date",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_PATH),
        help="where to write the catalog (default: site/assets/rule-catalog.js)",
    )
    args = parser.parse_args()

    rendered = render(build_catalog())
    output = Path(args.output)

    if args.check:
        if not output.exists():
            print(f"ERROR: {output} does not exist; run this script to create it.")
            return 1
        current = output.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"ERROR: {output} is out of date with the Python rule source. "
                "Run scripts/build-site-rule-catalog.py to regenerate it."
            )
            return 1
        print(f"Site rule catalog is current: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    catalog = build_catalog()
    print(
        f"Wrote {output} with {len(catalog['rules'])} rule(s), "
        f"{len(catalog['redaction'])} redaction pass(es), "
        f"{len(catalog['samples'])} sample log(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
