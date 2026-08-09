"""Command-line interface for SAM Doctor."""

from __future__ import annotations

import argparse
import codecs
import glob
import json
import sys
import textwrap
from datetime import datetime, timezone
from html import escape
from importlib.resources import files
from pathlib import Path

from . import __version__
from .diagnostics import (
    RULE_REQUEST_URL,
    Finding,
    diagnose,
    json_report,
    likely_error_excerpt,
    markdown_report,
    rules_report,
    sarif_report,
    terminal_report,
)
from .redaction import redact

_DEMO_FILES = {
    "oidc": "oidc-assume-role-failure.txt",
    "cloudformation": "cloudformation-resource-failure.txt",
    "capabilities": "capability-acknowledgement-failure.txt",
    "api-gateway": "api-gateway-no-methods-failure.txt",
    "s3-bucket-conflict": "s3-bucket-conflict-failure.txt",
    "esbuild": "esbuild-missing-failure.txt",
    "python-pip": "python-pip-build-failure.txt",
    "interactive-changeset": "interactive-changeset-failure.txt",
}

_WORKFLOW_TEMPLATE = """name: diagnose deployment failures

on:
{trigger}
jobs:
  diagnose:
    runs-on: ubuntu-latest
    # Naming permissions replaces the defaults rather than adding to them, so if
    # your deploy step needs something else - packages: read for a private base
    # image, pull-requests: write to comment - add it here.
    #
    # id-token: write is what lets the deploy step exchange an OIDC token for AWS
    # credentials. Without it the runner never sets ACTIONS_ID_TOKEN_REQUEST_URL
    # and the deploy fails before it starts. That failure is the single most
    # common one in real logs, and sam-doctor diagnoses it - but it is a poor
    # first experience to ship a scaffold that walks into it.
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - name: Deploy
        shell: bash
        run: |
          set -o pipefail
          {deploy_command} 2>&1 | tee deployment.log
      - name: Diagnose deployment log
        if: always()
        id: sam-doctor
        uses: jakegold1647/sam-doctor@v0
        with:
          log-file: deployment.log
          summary: {summary}
          annotations: {annotations}
          batch: {batch}
          fail-on-findings: {fail_on_findings}
          fail-on-confidence: "{fail_on_confidence}"
      # Optional: route high-signal failures to a follow-up job/thread.
      # - name: Open a follow-up note when issues are found
      #   if: steps.sam-doctor.outputs.has-findings == 'true'
      #   run: echo "SAM Doctor found ${{{{ steps.sam-doctor.outputs.finding-count }}}} findings."
"""
# The braces above are quadrupled on purpose. This template is rendered with
# str.format(), which collapses `{{` to `{`, so writing the GitHub expression as
# `${{ ... }}` emitted `${ ... }` - single braces, which GitHub does not
# interpolate. The line is commented out in the generated workflow and meant to
# be uncommented, so it has to be correct when it is.

_TRIGGER_MANUAL = (
    "  # Manual only: run from the Actions tab. Nothing here deploys on push.\n"
    "  # Regenerate with `sam-doctor init --on-push` to also deploy on pushes\n"
    "  # to main.\n"
    "  workflow_dispatch: {}\n"
)
_TRIGGER_ON_PUSH = "  push:\n    branches: [main]\n  workflow_dispatch: {}\n"

_SCHEMA_URLS = {
    "diagnose": "https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/docs/schemas/diagnose-report.schema.json",
    "batch": "https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/docs/schemas/batch-report.schema.json",
    "rules": "https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/docs/schemas/rules-report.schema.json",
    "sarif": "https://raw.githubusercontent.com/jakegold1647/sam-doctor/main/docs/schemas/sarif-report.schema.json",
}


def _build_parser() -> argparse.ArgumentParser:
    epilog = """
Exit codes:
  0  - command completed successfully, or no enforced fail gate was hit.
  1  - findings were detected and --fail-on-findings was used, or a finding
       met the --fail-on-confidence threshold.
  2  - usage/runtime error (missing input, invalid arguments, I/O failure).

Command behavior:
  diagnose: default exit 0 (no enforced failure), 1 with --fail-on-findings
            or a met --fail-on-confidence threshold.
  batch: default exit 0 (no enforced failure), 1 with --fail-on-findings
         or a met --fail-on-confidence threshold.
  demo, rules, schemas, packet, request-packet, init: 0 on successful execution.

GitHub Action behavior:
  0  - action runs without an enforced failure gate being hit.
  1  - findings are present and fail-on-findings is enabled, or a finding
       meets the fail-on-confidence threshold.
  2  - invalid action input or action runtime failure.
"""

    parser = argparse.ArgumentParser(
        prog="sam-doctor",
        description="Diagnose common AWS SAM and GitHub Actions deployment failure patterns locally.",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    diagnose_parser = subcommands.add_parser("diagnose", help="Analyze a deployment log or text file.")
    diagnose_parser.add_argument(
        "input",
        type=Path,
        help="Path to a UTF-8 text log, or - to read the log from stdin.",
    )
    diagnose_parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json", "github", "sarif"),
        default="terminal",
        help="Report format for stdout or --output.",
    )
    diagnose_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")
    diagnose_parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with status 1 when one or more supported findings are detected.",
    )
    diagnose_parser.add_argument(
        "--fail-on-confidence",
        choices=("high", "medium"),
        help=(
            "Exit with status 1 only when a finding at this confidence or above "
            "is detected. Reports still show every finding; only the exit "
            "status is gated. Implies --fail-on-findings at the threshold."
        ),
    )

    demo_parser = subcommands.add_parser("demo", help="Run a bundled deployment failure example.")
    demo_parser.add_argument(
        "--scenario",
        choices=tuple(_DEMO_FILES),
        default="oidc",
        help="Bundled failure scenario to diagnose.",
    )
    demo_parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json", "github", "sarif"),
        default="terminal",
    )
    demo_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")

    rules_parser = subcommands.add_parser("rules", help="List the currently supported diagnostic rules.")
    rules_parser.add_argument("--format", choices=("terminal", "json"), default="terminal")
    rules_parser.add_argument("--output", type=Path, help="Write the rule catalog to this path instead of stdout.")

    schemas_parser = subcommands.add_parser(
        "schemas", help="Show schema references for current machine-readable outputs."
    )
    schemas_parser.add_argument(
        "--format",
        choices=("terminal", "json"),
        default="terminal",
        help="Render schema references as text or machine-readable JSON.",
    )

    packet_parser = subcommands.add_parser(
        "packet",
        help="Generate a reproducible evidence packet (markdown/json + notes).",
    )
    packet_parser.add_argument(
        "input",
        type=str,
        help="Path to a UTF-8 text log, or - to read the log from stdin.",
    )
    packet_parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory for generated packet files.",
    )
    packet_parser.add_argument(
        "--markdown-name",
        default="diagnosis.md",
        help="Markdown report filename.",
    )
    packet_parser.add_argument(
        "--json-name",
        default="diagnosis.json",
        help="JSON report filename.",
    )
    packet_parser.add_argument(
        "--notes-name",
        default="researcher-notes.md",
        help="Template notes filename.",
    )
    packet_parser.add_argument(
        "--scenario",
        default="Deployment failure triage",
        help="Short scenario label to include in the notes file.",
    )

    request_packet_parser = subcommands.add_parser(
        "request-packet",
        help="Generate a small, sanitized excerpt for a rule request when diagnose finds no match.",
    )
    request_packet_parser.add_argument(
        "input",
        type=str,
        help="Path to a UTF-8 text log, or - to read the log from stdin.",
    )
    request_packet_parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory for the generated excerpt file.",
    )
    request_packet_parser.add_argument(
        "--name",
        default="rule-request.md",
        help="Excerpt file name.",
    )
    request_packet_parser.add_argument(
        "--context",
        type=int,
        default=2,
        help="Lines of context to keep on each side of the first likely error.",
    )
    request_packet_parser.add_argument(
        "--max-lines",
        type=int,
        default=15,
        help="Upper bound on the number of lines included in the excerpt.",
    )

    batch_parser = subcommands.add_parser("batch", help="Analyze multiple logs in one run.")
    batch_parser.add_argument(
        "inputs",
        nargs="+",
        help=(
            "One or more log files, directories, or wildcard paths. "
            "Directories are scanned for *.log, *.txt, and *.out files."
        ),
    )
    batch_parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json", "github", "sarif"),
        default="terminal",
        help="Report format for each file or the overall JSON output.",
    )
    batch_parser.add_argument(
        "--output",
        type=Path,
        help="Write the batch report to this path instead of stdout.",
    )
    batch_parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help=(
            "Exit with status 1 when any analyzed file returns one or more supported "
            "findings."
        ),
    )
    batch_parser.add_argument(
        "--fail-on-confidence",
        choices=("high", "medium"),
        help=(
            "Exit with status 1 only when any analyzed file has a finding at "
            "this confidence or above. Reports still show every finding; only "
            "the exit status is gated. Implies --fail-on-findings at the "
            "threshold."
        ),
    )
    init_parser = subcommands.add_parser(
        "init", help="Create a starter GitHub Actions workflow for SAM Doctor."
    )
    init_parser.add_argument(
        "--workflow-file",
        default=".github/workflows/sam-doctor.yml",
        help="Path where the starter workflow should be written.",
    )
    init_parser.add_argument(
        "--deploy-command",
        default="sam deploy --no-confirm-changeset",
        help="Deployment command to capture in the starter workflow.",
    )
    summary_group = init_parser.add_mutually_exclusive_group()
    summary_group.add_argument(
        "--summary",
        action="store_true",
        dest="summary",
        help="Write a GitHub Actions summary from the diagnosis output.",
    )
    summary_group.add_argument(
        "--no-summary",
        action="store_false",
        dest="summary",
        help="Disable the GitHub Actions summary output in the generated workflow.",
    )
    annotation_group = init_parser.add_mutually_exclusive_group()
    annotation_group.add_argument(
        "--annotations",
        action="store_true",
        dest="annotations",
        help="Emit GitHub Actions notices for findings.",
    )
    annotation_group.add_argument(
        "--no-annotations",
        action="store_false",
        dest="annotations",
        help="Disable GitHub Actions notices for findings.",
    )
    init_parser.set_defaults(summary=True, annotations=True)
    init_parser.add_argument(
        "--batch",
        action="store_true",
        help="Use batch mode on a directory or glob in the generated workflow.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing workflow file.",
    )
    init_parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Fail the action step when one or more findings are found.",
    )
    init_parser.add_argument(
        "--fail-on-confidence",
        choices=("high", "medium"),
        help=(
            "Write a fail-on-confidence threshold into the generated workflow, "
            "so the action step fails only on findings at that confidence or "
            "above."
        ),
    )
    init_parser.add_argument(
        "--on-push",
        action="store_true",
        help=(
            "Also trigger the generated workflow on pushes to main, running the "
            "deploy command automatically. Off by default so `init` can never "
            "wire up an AWS deployment without an explicit opt-in; the generated "
            "workflow stays manual (workflow_dispatch) until you pass this flag."
        ),
    )
    return parser


# Diagnosis time is proportional to log size: every line is tested against the
# whole rule catalog, which is roughly a second per megabyte. Past this size a
# run takes long enough to look like a hang, so say so. The note goes to
# stderr, leaving stdout clean for the machine-readable formats.
_SLOW_INPUT_BYTES = 25 * 1024 * 1024


def _note_slow_input(path: Path, text: str) -> None:
    if len(text) < _SLOW_INPUT_BYTES:
        return
    print(
        f"Note: {path} is {len(text) / 1_048_576:.0f} MB; diagnosing it takes "
        "roughly a second per megabyte. Trimming the log to the failing "
        "section is faster and produces the same finding.",
        file=sys.stderr,
    )


# Byte-order marks, longest first: a UTF-32 LE mark (ff fe 00 00) begins with a
# UTF-16 LE mark, so testing UTF-16 first would decode UTF-32 as the wrong
# encoding. The names without an endianness suffix let the codec consume the mark
# itself rather than leaving U+FEFF at the start of the first line.
_BOM_ENCODINGS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
    (codecs.BOM_UTF8, "utf-8-sig"),
)


def _decode_log_bytes(raw: bytes) -> str:
    """Decode log bytes, honouring a byte-order mark when one is present.

    Reading everything as UTF-8 loses whole logs on Windows. PowerShell writes
    redirected output as BOM-marked Unicode - `sam deploy > deploy.log` under
    PowerShell 5.1 produces UTF-16 LE - and decoding that as UTF-8 leaves a NUL
    between every character, so no rule matches and the report says "no
    supported pattern found" for a log that is full of failures.

    Anything without a mark is still read as UTF-8 with replacement, which keeps
    a latin-1 or otherwise mixed log readable instead of raising.
    """

    for bom, encoding in _BOM_ENCODINGS:
        if raw.startswith(bom):
            return raw.decode(encoding, errors="replace")
    return raw.decode("utf-8", errors="replace")


def _read_text(path: Path) -> str:
    if path == Path("-"):
        return sys.stdin.read()
    try:
        text = _decode_log_bytes(path.read_bytes())
    except OSError as error:
        raise ValueError(f"Could not read {path}: {error}") from error
    _note_slow_input(path, text)
    return text


# Ordered so a threshold means "this confidence or above". "low" is in the
# rule vocabulary even though no shipped rule uses it yet.
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _should_fail(
    confidences: list[str], fail_on_findings: bool, fail_on_confidence: str | None
) -> bool:
    """Decide the exit gate; reports are never filtered, only the exit status.

    A confidence threshold is its own opt-in gate: it fails on findings at or
    above the threshold whether or not --fail-on-findings was also given, so
    a team can gate on high confidence first and tighten later.
    """

    if fail_on_confidence is not None:
        threshold = _CONFIDENCE_RANK[fail_on_confidence]
        return any(
            _CONFIDENCE_RANK.get(confidence, 0) >= threshold
            for confidence in confidences
        )
    return fail_on_findings and bool(confidences)


def _render_findings(
    findings: list[Finding],
    source_name: str,
    output_format: str,
    *,
    input_is_empty: bool = False,
) -> str:
    # Only the human-readable formats distinguish an empty input. The JSON and
    # SARIF payloads already say it accurately with a zero finding count, and
    # their shapes are covered by the stability promise.
    if output_format == "markdown":
        return markdown_report(findings, source_name, input_is_empty=input_is_empty)
    if output_format == "github":
        return _render_github(findings, source_name)
    if output_format == "json":
        return json_report(findings, source_name)
    if output_format == "sarif":
        return sarif_report([(source_name, findings)])
    return (
        terminal_report(findings, source_name, input_is_empty=input_is_empty) + "\n"
    )


def _escape_github_command_value(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_github_command_property(value: str) -> str:
    # Property values additionally reserve ':' and ',' as delimiters.
    return _escape_github_command_value(value).replace(":", "%3A").replace(",", "%2C")


def _render_github(findings: list[Finding], source_name: str) -> str:
    if not findings:
        return ""

    escaped_source = _escape_github_command_property(redact(source_name))
    lines = []
    for finding in findings:
        verification = (
            finding.verification[0] if finding.verification else "Review the documentation link."
        ).rstrip()
        # The period was appended unconditionally, and every rule in the catalog
        # already ends its first verification step with one - so every annotation
        # this tool has ever written said `write`..` on the surface people actually
        # read, the workflow annotation in the GitHub UI.
        if not verification.endswith((".", "!", "?", ":")):
            verification = f"{verification}."
        message = (
            f"{finding.title}. Line {finding.line_number}: {verification} "
            f"Docs: {finding.documentation_url}"
        )
        lines.append(
            f"::notice file={escaped_source},line={finding.line_number},title=SAM Doctor::"
            f"{_escape_github_command_value(message)}"
        )
    return "\n".join(lines) + "\n"


def _findings_from_payload_items(items: list[object]) -> list[Finding]:
    findings: list[Finding] = []
    for item in items:
        finding = dict(item)
        findings.append(
            Finding(
                rule_id=str(finding.get("rule_id", "")),
                title=str(finding["title"]),
                confidence=str(finding["confidence"]),
                explanation=str(finding["explanation"]),
                verification=tuple(str(step) for step in finding.get("verification", ())),
                documentation_url=str(finding["documentation_url"]),
                evidence=tuple(str(evidence) for evidence in finding.get("evidence", ())),
                line_number=int(finding["line_number"]),
            )
        )
    return findings


def github_notices_from_payload(payload: dict[str, object], is_batch: bool) -> str:
    notices: list[str] = []
    if is_batch:
        for raw_result in payload.get("results", []):
            result = dict(raw_result)
            source = str(result.get("source", ""))
            raw_findings = result.get("findings", [])
            if not isinstance(raw_findings, list):
                continue
            findings = _findings_from_payload_items(raw_findings)
            rendered = _render_github(findings, source)
            if rendered.strip():
                notices.append(rendered.rstrip())
        return "\n".join(notices) + ("\n" if notices else "")

    findings = _findings_from_payload_items(payload.get("findings", []))
    source = str(payload.get("source", ""))
    rendered = _render_github(findings, source)
    return rendered


def _render(text: str, source_name: str, output_format: str) -> str:
    return _render_findings(
        diagnose(text), source_name, output_format, input_is_empty=not text.strip()
    )


def _expand_input_paths(input_value: str) -> list[Path]:
    globbed = sorted(glob.glob(input_value))
    paths = [Path(candidate) for candidate in globbed]
    direct = Path(input_value)
    if not paths and direct.exists():
        paths = [direct]

    if not paths:
        raise ValueError(f"Input path not found: {input_value}")

    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(
                sorted(
                    p
                    for p in path.rglob("*")
                    if p.is_file() and p.suffix.lower() in {".log", ".txt", ".out"}
                )
            )
            continue
        if path.is_file():
            expanded.append(path)
            continue
        raise ValueError(f"Input path not found: {path}")

    if not expanded:
        raise ValueError(f"No log files found for: {input_value}")
    # `Path` ordering follows the host path flavour: Windows compares paths
    # case-insensitively while POSIX compares their exact spelling.  Use the
    # serialized form as the key so a portable set of input names keeps the
    # same order on every runner.
    return sorted(set(expanded), key=lambda path: path.as_posix())


def _batch_render(
    inputs: list[str], output_format: str, output_path: Path | None = None
) -> tuple[str, list[str]]:
    if not inputs:
        raise ValueError("No inputs provided for batch mode.")

    text_reports: list[str] = []
    batch_payload: list[dict[str, object]] = []
    sarif_pairs: list[tuple[str, list[Finding]]] = []
    # The second return value feeds the exit gate: every finding's confidence,
    # across all files. Truthiness keeps the old has-findings meaning.
    confidences: list[str] = []
    for input_value in inputs:
        for file_path in _expand_input_paths(input_value):
            if output_path is not None:
                _ensure_input_is_not_output(file_path, (output_path,))
            text = _read_text(file_path)
            # Batch sources are part of terminal, JSON, GitHub, and SARIF
            # output.  Native separators made the same relative input appear as
            # `logs\\deploy.log` on Windows and `logs/deploy.log` elsewhere.
            source = file_path.as_posix()
            display_source = redact(source)
            findings = diagnose(text)
            confidences.extend(finding.confidence for finding in findings)
            if output_format == "sarif":
                sarif_pairs.append((source, findings))
                continue
            report = _render_findings(
                findings, source, output_format, input_is_empty=not text.strip()
            )

            if output_format == "json":
                rendered_json = json.loads(json_report(findings, source))
                batch_payload.append(
                    {
                        "source": rendered_json["source"],
                        "finding_count": rendered_json["finding_count"],
                        "findings": rendered_json["findings"],
                    }
                )
                continue
            if output_format == "github":
                if report:
                    text_reports.append(report.rstrip())
                continue
            text_reports.append(
                f"## Source: <code>{escape(display_source)}</code>\n\n{report.rstrip()}"
                if output_format == "markdown"
                else f"{display_source}\n{report.rstrip()}"
            )

    if output_format == "json":
        return (
            json.dumps(
                {
                    "sam_doctor_version": __version__,
                    "batch_count": len(batch_payload),
                    "results": batch_payload,
                },
                indent=2,
            )
            + "\n",
            confidences,
        )
    if output_format == "sarif":
        return sarif_report(sarif_pairs), confidences
    if output_format == "github":
        return (
            "\n".join(text_reports) + ("\n" if text_reports else ""),
            confidences,
        )
    return (
        "\n\n".join(text_reports) + ("\n" if text_reports else ""),
        confidences,
    )


def _init_workflow_command(
    command: str,
    workflow_file: str,
    force: bool,
    *,
    summary: bool,
    annotations: bool,
    batch: bool,
    fail_on_findings: bool,
    fail_on_confidence: str | None,
    on_push: bool,
) -> None:
    target = Path(workflow_file).expanduser().resolve()
    if target.exists() and not force:
        raise ValueError(f"Workflow file already exists: {target}. Use --force to overwrite.")
    _make_output_dir(target.parent)
    _write_report(
        target,
        textwrap.dedent(
            _WORKFLOW_TEMPLATE.format(
                trigger=_TRIGGER_ON_PUSH if on_push else _TRIGGER_MANUAL,
                deploy_command=command,
                summary=str(summary).lower(),
                annotations=str(annotations).lower(),
                batch=str(batch).lower(),
                fail_on_findings=str(fail_on_findings).lower(),
                fail_on_confidence=fail_on_confidence or "",
            )
        ),
    )



def _read_demo(scenario: str = "oidc") -> str:
    """Read a packaged example so `sam-doctor demo` works after installation."""

    return files("sam_doctor").joinpath("data", _DEMO_FILES[scenario]).read_text(encoding="utf-8")


def _write_report(path: Path, report: str) -> None:
    try:
        path.write_text(report, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ValueError(f"Could not write {path}: {error}") from error


def _artifact_path(output_dir: Path, name: str, option_name: str) -> Path:
    """Resolve an artifact name without letting it escape its output directory."""

    try:
        resolved_output_dir = output_dir.resolve()
        candidate = (resolved_output_dir / name).resolve()
        candidate.relative_to(resolved_output_dir)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError(
            f"{option_name} must resolve inside --output-dir: {name}"
        ) from error

    if candidate == resolved_output_dir:
        raise ValueError(f"{option_name} must name a file inside --output-dir: {name}")
    return candidate


def _ensure_input_is_not_output(
    input_path: Path, output_paths: tuple[Path, ...]
) -> None:
    """Reject artifact targets that would overwrite the file being diagnosed."""

    try:
        resolved_input = input_path.resolve()
        resolved_outputs = tuple(output_path.resolve() for output_path in output_paths)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"Could not resolve input or output path: {error}") from error
    aliases_output = resolved_input in resolved_outputs
    if not aliases_output:
        try:
            aliases_output = any(
                output_path.exists() and input_path.samefile(output_path)
                for output_path in output_paths
            )
        except OSError as error:
            raise ValueError(
                f"Could not compare input and output paths: {error}"
            ) from error
    if aliases_output:
        raise ValueError(
            f"Input file must not resolve to an output target: {input_path}"
        )


def _ensure_output_targets_are_not_hard_links(
    output_paths: tuple[Path, ...],
) -> None:
    """Reject packet targets that can mutate files outside the packet directory."""

    try:
        hard_linked = next(
            (
                output_path
                for output_path in output_paths
                if output_path.exists() and output_path.stat().st_nlink > 1
            ),
            None,
        )
    except OSError as error:
        raise ValueError(f"Could not inspect output targets: {error}") from error
    if hard_linked is not None:
        raise ValueError(
            "Packet output targets must not be hard links: "
            f"{hard_linked}"
        )


def _make_output_dir(path: Path) -> Path:
    """Create an output directory, reporting failure the way reads and writes do.

    `mkdir` was called bare at each site while `_read_text` and `_write_report`
    both translate OSError into a ValueError the dispatcher renders as
    `sam-doctor: error: ...` with exit 2. So an output directory that could not be
    created - a read-only checkout, a path that is already a file, a full disk -
    surfaced as a Python traceback and exit 1, which in this project's contract
    means a fail gate was hit. A CI step branching on the code would read "this
    deployment has findings" from "that directory could not be created".
    """

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ValueError(f"Could not create {path}: {error}") from error
    return path


def _write_packet_notes(
    notes_path: Path,
    scenario: str,
    markdown_path: Path,
    json_path: Path,
    command: str,
    json_payload: dict[str, object],
    source: str,
) -> None:
    findings = json_payload.get("findings", [])
    finding_count = json_payload.get("finding_count", 0)
    top_finding = "No finding payload parsed"
    if findings:
        first_finding = findings[0]
        top_finding = first_finding.get("title", first_finding.get("explanation", top_finding))  # type: ignore[union-attr]

    _write_report(
        notes_path,
        "\n".join(
            [
                "# Researcher evidence packet",
                f"- Generated: {datetime.now(timezone.utc).isoformat()}",
                f"- Scenario: {redact(scenario)}",
                f"- Source: {redact(source)}",
                f"- Command: {redact(command)}",
                f"- Markdown report: {markdown_path.name}",
                f"- JSON report: {json_path.name}",
                f"- Finding count: {finding_count}",
                f"- Top finding: {top_finding}",
                "",
                "Use only the packet files to discuss this case; do not share full raw logs.",
            ]
        )
        + "\n",
    )


def _packet_command(args: argparse.Namespace) -> int:
    output_dir = _make_output_dir(Path(args.output_dir).resolve())
    markdown_path = _artifact_path(output_dir, args.markdown_name, "--markdown-name")
    json_path = _artifact_path(output_dir, args.json_name, "--json-name")
    notes_path = _artifact_path(output_dir, args.notes_name, "--notes-name")
    if len({markdown_path, json_path, notes_path}) != 3:
        raise ValueError(
            "--markdown-name, --json-name, and --notes-name must resolve to "
            "distinct files inside --output-dir."
        )

    if args.input == "-":
        stdin_text = sys.stdin.read()
        if not stdin_text:
            raise ValueError("stdin input was empty; provide an error excerpt.")
        source_name = "<stdin>"
        text = stdin_text
        findings = diagnose(stdin_text)
    else:
        source_path = Path(args.input)
        # File name only, not the path it was read from. This packet exists to be
        # shared - its own notes say to discuss the case using these files - and
        # CONTRIBUTING asks contributors never to post private repository names,
        # which is exactly what a working path usually contains, along with the
        # OS user name. The name is the part that carries diagnostic meaning.
        source_name = source_path.name
        text = _read_text(source_path)
        _ensure_input_is_not_output(
            source_path, (markdown_path, json_path, notes_path)
        )
        findings = diagnose(text)

    _ensure_output_targets_are_not_hard_links(
        (markdown_path, json_path, notes_path)
    )
    input_is_empty = not text.strip()

    _write_report(
        markdown_path,
        _render_findings(
            findings, source_name, "markdown", input_is_empty=input_is_empty
        ),
    )
    json_report = _render_findings(findings, source_name, "json")
    _write_report(json_path, json_report)

    command = (
        f"sam-doctor packet {source_name} "
        f"--markdown-name {args.markdown_name} "
        f"--json-name {args.json_name} "
        f"--notes-name {args.notes_name} "
        f"--scenario \"{args.scenario}\""
    )
    payload = json.loads(json_report)
    _write_packet_notes(
        notes_path,
        args.scenario,
        markdown_path,
        json_path,
        command,
        payload,
        source_name,
    )

    print("Evidence packet generated:")
    print(f"- {markdown_path}")
    print(f"- {json_path}")
    print(f"- {notes_path}")
    return 0


def _request_packet_command(args: argparse.Namespace) -> int:
    output_dir = _make_output_dir(Path(args.output_dir).resolve())
    notes_path = _artifact_path(output_dir, args.name, "--name")

    if args.input == "-":
        stdin_text = sys.stdin.read()
        if not stdin_text:
            raise ValueError("stdin input was empty; provide an error excerpt.")
        source_name = "<stdin>"
        text = stdin_text
    else:
        source_path = Path(args.input)
        # File name only: this excerpt is written to be pasted into a public rule
        # request, and a full working path usually names the repository - which
        # CONTRIBUTING tells contributors never to post - as well as the OS user.
        source_name = source_path.name
        text = _read_text(source_path)
        _ensure_input_is_not_output(source_path, (notes_path,))

    _ensure_output_targets_are_not_hard_links((notes_path,))
    excerpt = likely_error_excerpt(text, context=args.context, max_lines=args.max_lines)
    command = f"sam-doctor request-packet {source_name}"

    lines = [
        "# SAM Doctor rule request excerpt",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- SAM Doctor version: {__version__}",
        f"- Source: {redact(source_name)}",
        f"- Command: {redact(command)}",
        "",
        "This is a starting excerpt for a rule request, not a diagnosis. Review "
        + "it yourself before pasting it anywhere - redaction covers common "
        + "identifiers, not every possible secret.",
        "",
    ]
    if excerpt:
        lines.extend(
            [
                "### Likely error excerpt",
                "",
                "```",
                *[f"{line_number}: {line}" for line_number, line in excerpt],
                "```",
            ]
        )
    else:
        lines.append(
            "No line looked like an error, so no excerpt was captured. Paste a "
            "short, sanitized excerpt (5-15 lines) around the actual failure "
            "yourself."
        )
    lines.extend(["", f"Open a rule request: {RULE_REQUEST_URL}"])

    _write_report(notes_path, "\n".join(lines) + "\n")
    print(f"Rule request excerpt written to {notes_path}")
    return 0


def _schemas_command(args: argparse.Namespace) -> int:
    schemas = dict(_SCHEMA_URLS)
    if args.format == "json":
        print(json.dumps(schemas, indent=2))
        return 0

    for name, schema_url in schemas.items():
        print(f"{name}: {schema_url}")
    return 0


def _print_error(parser: argparse.ArgumentParser, message: str) -> None:
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: {message}", file=sys.stderr)


def _use_portable_redirected_output() -> None:
    """Keep redirected stdout/stderr byte-stable across operating systems."""

    for stream in (sys.stdout, sys.stderr):
        if stream.isatty():
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", newline="\n")


def main(argv: list[object] | None = None) -> int:
    _use_portable_redirected_output()
    parser = _build_parser()
    try:
        args = parser.parse_args([str(arg) for arg in argv] if argv is not None else None)
    except SystemExit as error:
        if error.code in (0, "0", None):
            return 0
        return 2

    if args.command == "demo":
        report = _render(_read_demo(args.scenario), _DEMO_FILES[args.scenario], args.format)
        if args.output:
            try:
                _write_report(args.output, report)
            except ValueError as error:
                _print_error(parser, str(error))
                return 2
            print(f"Wrote {args.format} report to {args.output}")
        else:
            sys.stdout.write(report)
        return 0

    if args.command == "rules":
        report = rules_report(args.format)
        if args.output:
            try:
                _write_report(args.output, report)
            except ValueError as error:
                _print_error(parser, str(error))
                return 2
            print(f"Wrote {args.format} rule catalog to {args.output}")
        else:
            sys.stdout.write(report)
        return 0

    if args.command == "batch":
        try:
            report, confidences = _batch_render(args.inputs, args.format, args.output)
        except ValueError as error:
            _print_error(parser, str(error))
            return 2

        if args.output:
            try:
                _write_report(args.output, report)
            except ValueError as error:
                _print_error(parser, str(error))
                return 2
            print(f"Wrote batch {args.format} report to {args.output}")
        else:
            sys.stdout.write(report)
        return 1 if _should_fail(confidences, args.fail_on_findings, args.fail_on_confidence) else 0

    if args.command == "init":
        try:
            _init_workflow_command(
                args.deploy_command,
                args.workflow_file,
                args.force,
                summary=args.summary,
                annotations=args.annotations,
                batch=args.batch,
                fail_on_findings=args.fail_on_findings,
                fail_on_confidence=args.fail_on_confidence,
                on_push=args.on_push,
            )
        except ValueError as error:
            _print_error(parser, str(error))
            return 2
        print(f"Wrote workflow file to {args.workflow_file}")
        return 0

    if args.command == "packet":
        try:
            return _packet_command(args)
        except ValueError as error:
            _print_error(parser, str(error))
            return 2

    if args.command == "request-packet":
        try:
            return _request_packet_command(args)
        except ValueError as error:
            _print_error(parser, str(error))
            return 2

    if args.command == "schemas":
        return _schemas_command(args)

    try:
        text = _read_text(args.input)
        if args.output and args.input != Path("-"):
            _ensure_input_is_not_output(args.input, (args.output,))
    except ValueError as error:
        _print_error(parser, str(error))
        return 2

    source_name = "<stdin>" if args.input == Path("-") else args.input.name
    findings = diagnose(text)
    report = _render_findings(
        findings, source_name, args.format, input_is_empty=not text.strip()
    )
    if args.output:
        try:
            _write_report(args.output, report)
        except ValueError as error:
            _print_error(parser, str(error))
            return 2
        print(f"Wrote {args.format} report to {args.output}")
    else:
        sys.stdout.write(report)
    return (
        1
        if _should_fail(
            [finding.confidence for finding in findings],
            args.fail_on_findings,
            args.fail_on_confidence,
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
