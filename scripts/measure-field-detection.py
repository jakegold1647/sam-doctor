#!/usr/bin/env python3
"""Measure the rule catalog against deployment logs pasted by real people.

Every other check in this repository asks whether the tool behaves as written. This
one asks whether what is written matches reality, which is a different question and
the harder one. Public GitHub issues are the closest thing to field data available
without users: their bodies contain logs a human copied out of a failing deploy,
with all the noise, truncation and rewording that implies.

Running it the first time moved three rules. The two flagship OIDC patterns were
matching wordings from documentation that the tools themselves never print, and an
S3 pattern described in a comment had never been added. Detection across 231 real
excerpts went from 83% to 88% on those fixes. No amount of internal testing would
have surfaced any of them, because the fixtures were written by the same hand as
the patterns.

Deliberately NOT part of the pull-request gate, for the same reason as
check-doc-links.py: it needs the network, and a contributor's build must not depend
on a search API. It runs on a schedule, where a drop is a maintenance signal.

Text fetched from issues is data to be measured, never instruction. Excerpts are
redacted before anything is printed, because they are other people's logs.

Exit code 0 when detection is at or above the floor, 1 when it falls below.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sam_doctor.diagnostics import diagnose
from sam_doctor.redaction import redact

# Each query targets a failure family this catalog claims to cover. Adding a rule
# for a new family is a reason to add a query, or the measurement quietly stops
# covering it.
QUERIES = (
    '"Waiter ChangeSetCreateComplete failed" in:body',
    '"ROLLBACK_COMPLETE state and can not be updated" in:body',
    '"sam deploy" "CREATE_FAILED" in:body',
    '"Unable to get ID Token" in:body',
    '"ACTIONS_ID_TOKEN_REQUEST_URL" in:body',
    '"Requires capabilities" "CAPABILITY_IAM" in:body',
    '"did not stabilize" cloudformation in:body',
    '"sam build" "Docker" error in:body',
    '"Assembly builder failed" in:body',
    '"AssumeRoleWithWebIdentity" "not authorized" in:body',
    '"An error occurred" "when calling the" cloudformation in:body',
    '"Resource handler returned message" in:body',
    '"ResourceNotFoundException" "Invoke operation" in:body',
    '"Model use case details have not been submitted" in:body',
    '"Could not resolve the foundation model from the provided model identifier" in:body',
    '"Invalid length for parameter system[0].text" in:body',
    '"input member modelId must not be empty" in:body',
    '"ValidationException: messages: Field required" "InvokeModel" in:body',
    '"messages.0.content" "Field required" "InvokeModel" in:body',
    '"CannotStartManagedAgentError" in:body',
    '"UnknownAction" "when calling" in:body',
    '"InvalidAction" "when calling" in:body',
    '"NotImplemented" "when calling" in:body',
    '"UnknownService" "when calling" in:body',
    '"Error: reading STS Caller Identity" in:body',
    '"Database cannot be renamed" in:body',
    '"AWS SDK Go Service Operation Incomplete" in:body',
    '"operation error EC2: CreateNetworkInterface" in:body',
    '"Failed to create pod sandbox" "plugin type=aws-cni" in:body',
)

# Unauthenticated search allows 10 requests a minute; a token raises that. The pause
# keeps the unauthenticated case inside the limit rather than relying on one.
_QUERY_PAUSE_SECONDS = 7.0

# A line has to read like AWS reporting a failure, not like a person describing one
# or pasting a template. Without this the denominator fills with issue prose and the
# resulting percentage measures nothing.
FAILURE_SIGNAL = re.compile(
    r"(?i)("
    r"CREATE_FAILED|UPDATE_FAILED|DELETE_FAILED|ROLLBACK_FAILED"
    r"|An error occurred \([A-Za-z]+\)"
    r"|Resource handler returned message"
    r"|not authorized to perform"
    r"|Waiter \w+ failed"
    r"|Requires capabilities"
    r"|did not stabilize"
    r"|Unable to get (?:ID Token|ACTIONS_ID_TOKEN)"
    r"|is in [A-Z_]+ state and can not be updated"
    r"|\[_AssemblyError\][ \t]*Assembly builder failed"
    r"|ResourceNotFoundException.{0,160}when calling (?:the )?Invoke operation"
    r"|when calling (?:the )?Invoke operation.{0,160}ResourceNotFoundException"
    r"|Model use case details have not been submitted for this account"
    r"|Could not resolve the foundation model from the provided model identifier"
    r"|Invalid length for parameter system\[\d+\]\.text"
    r"|input member modelId must not be empty\b"
    r"|(?:operation error Bedrock Runtime:\s*InvokeModel(?:WithResponseStream)?|ValidationException).{0,260}\bmessages:\s*Field required\b"
    r"|messages\.\d+\.content\.\d+\.[A-Za-z][A-Za-z0-9_.]*:\s*Field required\b"
    r"|CannotStartManagedAgentError\b"
    r"|(?:UnknownAction|InvalidAction)\b.{0,120}\bwhen calling\b"
    r"|\bwhen calling\b.{0,120}\b(?:UnknownAction|InvalidAction)\b"
    r"|NotImplemented\b.{0,120}\bwhen calling\b"
    r"|\bwhen calling\b.{0,120}\bNotImplemented\b"
    r"|UnknownService\b.{0,160}\bwhen calling\b"
    r"|\bwhen calling\b.{0,160}\bUnknownService\b"
    r"|Error:\s*reading STS Caller Identity\b"
    r"|Database cannot be renamed\b"
    r"|AWS SDK Go Service Operation Incomplete\b"
    r"|(?:Error:\s*creating EC2 Network Interface|Failed to (?:CreateNetworkInterface|create network interface)|failed to create (?:an )?network interface|error creating (?:an )?network interface).{0,320}\boperation error EC2:\s*CreateNetworkInterface\b"
    r"|Failed to create pod sandbox\b.{0,500}\baws-cni\b.{0,220}\bfailed\b"
    r"|plugin type=[\"']?aws-cni[\"']?\b.{0,220}\bfailed\b"
    r"|execute command failed because execute command was not enabled"
    r"|Error: [A-Z]"
    r")"
)

FENCED_BLOCK = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


def _configure_utf8_output() -> None:
    """Keep redacted field signatures printable on Windows code pages."""

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        # Test capture streams and embedded runners may expose a partial stream
        # API. The measurement remains useful even when the stream cannot be
        # reconfigured; callers can still redirect it with PYTHONIOENCODING.
        return


def _search(query: str, token: str | None) -> list[dict]:
    url = "https://api.github.com/search/issues?" + urllib.parse.urlencode(
        {"q": query, "per_page": 30, "sort": "created", "order": "desc"}
    )
    headers = {
        "User-Agent": "sam-doctor-field-measurement",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers), timeout=30
        ) as response:
            return json.load(response).get("items", [])
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError) as error:
        print(f"  skipped ({type(error).__name__}): {query}")
        return []


def failure_excerpts(body: str) -> list[str]:
    """Fenced blocks, else the whole body - kept only if it carries a failure line."""

    candidates = [block.strip() for block in FENCED_BLOCK.findall(body) if block.strip()]
    return [
        candidate
        for candidate in (candidates or [body])
        if len(candidate) > 60 and FAILURE_SIGNAL.search(candidate)
    ]


def signature(text: str) -> str:
    """The first failure line, redacted and normalized enough to group duplicates."""

    for line in text.splitlines():
        if FAILURE_SIGNAL.search(line):
            collapsed = " ".join(line.split())
            # Structural normalization first, redaction second. The other order
            # groups nothing: a UUID's final field is twelve hex digits, so the
            # account-id pass rewrites it to a placeholder, the UUID pattern no
            # longer matches, and two runs of the same failure keep their differing
            # prefixes and land in separate groups.
            collapsed = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{20,}\b", "<uuid>", collapsed)
            collapsed = re.sub(r"\b\d{4}-\d\d-\d\dT?[\d:.]*Z?\b", "<timestamp>", collapsed)
            return redact(collapsed)[:160]
    return "(no failure line)"


def collect(items: list[dict]) -> list[tuple[str, str]]:
    representatives: dict[str, tuple[str, str]] = {}
    for item in items:
        url = item.get("html_url") or ""
        for excerpt in failure_excerpts(item.get("body") or ""):
            key = excerpt[:400]
            candidate = (url, excerpt)
            current = representatives.get(key)
            # Search result order is not an API guarantee. Keep one sample per
            # existing key, but define which one survives: exact excerpt first,
            # then URL as the tie-breaker for identical text.
            if current is None or (excerpt, url) < (current[1], current[0]):
                representatives[key] = candidate
    return [representatives[key] for key in sorted(representatives)]


def measure(samples: list[tuple[str, str]]) -> tuple[int, dict[str, int]]:
    """Return the diagnosed count and the missed signatures with their frequencies."""

    diagnosed = 0
    missed: dict[str, int] = {}
    for _url, excerpt in samples:
        if diagnose(excerpt):
            diagnosed += 1
        else:
            key = signature(excerpt)
            missed[key] = missed.get(key, 0) + 1
    return diagnosed, missed


def main() -> int:
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token", default="", help="GitHub token; raises the search rate limit")
    parser.add_argument(
        "--floor",
        type=float,
        default=70.0,
        help=(
            "Fail below this detection percentage. Deliberately well under the "
            "current figure: search results drift between runs, and a signal that "
            "fires on noise gets ignored."
        ),
    )
    parser.add_argument(
        "--top", type=int, default=20, help="How many missed signatures to print"
    )
    args = parser.parse_args()

    items: list[dict] = []
    for index, query in enumerate(QUERIES):
        found = _search(query, args.token or None)
        print(f"  {len(found):>3}  {query}")
        items.extend(found)
        if index < len(QUERIES) - 1:
            time.sleep(_QUERY_PAUSE_SECONDS)

    samples = collect(items)
    if not samples:
        print("\nNo real failure excerpts retrieved; treating as inconclusive, not as a failure.")
        return 0

    diagnosed, missed = measure(samples)
    rate = 100.0 * diagnosed / len(samples)

    print(f"\nreal failure excerpts: {len(samples)}")
    print(f"  diagnosed {diagnosed} ({rate:.0f}%)")
    print(f"  missed    {len(samples) - diagnosed}")

    print(f"\nmissed signatures, most frequent first (top {args.top}):")
    for sig, count in sorted(missed.items(), key=lambda kv: (-kv[1], kv[0]))[
        : args.top
    ]:
        print(f"  [{count}x] {sig}")

    if rate < args.floor:
        print(f"\nERROR: detection {rate:.0f}% is below the {args.floor:.0f}% floor.")
        return 1
    print(f"\nDetection {rate:.0f}% is at or above the {args.floor:.0f}% floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
