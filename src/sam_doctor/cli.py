"""Command-line interface for SAM Doctor."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from html import escape
from importlib.resources import files
from pathlib import Path

from . import __version__
from .diagnostics import (
    Finding,
    diagnose,
    json_report,
    markdown_report,
    rules_report,
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sam-doctor",
        description="Diagnose common AWS SAM and GitHub Actions deployment failure patterns locally.",
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
        choices=("terminal", "markdown", "json", "github"),
        default="terminal",
        help="Report format for stdout or --output.",
    )
    diagnose_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")
    diagnose_parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Exit with status 1 when one or more supported findings are detected.",
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
        choices=("terminal", "markdown", "json", "github"),
        default="terminal",
    )
    demo_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")

    rules_parser = subcommands.add_parser("rules", help="List the currently supported diagnostic rules.")
    rules_parser.add_argument("--format", choices=("terminal", "json"), default="terminal")
    rules_parser.add_argument("--output", type=Path, help="Write the rule catalog to this path instead of stdout.")

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
        choices=("terminal", "markdown", "json", "github"),
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
    return parser


def _read_text(path: Path) -> str:
    if path == Path("-"):
        return sys.stdin.read()
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ValueError(f"Could not read {path}: {error}") from error


def _render_findings(findings: list[Finding], source_name: str, output_format: str) -> str:
    if output_format == "markdown":
        return markdown_report(findings, source_name)
    if output_format == "github":
        return _render_github(findings, source_name)
    if output_format == "json":
        return json_report(findings, source_name)
    return terminal_report(findings, source_name) + "\n"


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
        )
        message = (
            f"{finding.title}. Line {finding.line_number}: {verification}. "
            f"Docs: {finding.documentation_url}"
        )
        lines.append(
            f"::notice file={escaped_source},line={finding.line_number},title=SAM Doctor::"
            f"{_escape_github_command_value(message)}"
        )
    return "\n".join(lines) + "\n"


def _render(text: str, source_name: str, output_format: str) -> str:
    return _render_findings(diagnose(text), source_name, output_format)


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
    return sorted(set(expanded))


def _batch_render(inputs: list[str], output_format: str) -> tuple[str, bool]:
    if not inputs:
        raise ValueError("No inputs provided for batch mode.")

    text_reports: list[str] = []
    batch_payload: list[dict[str, object]] = []
    report_has_findings = False
    for input_value in inputs:
        for file_path in _expand_input_paths(input_value):
            text = _read_text(file_path)
            source = str(file_path)
            findings = diagnose(text)
            if findings:
                report_has_findings = True
            report = _render_findings(findings, source, output_format)

            if output_format == "json":
                rendered_json = json.loads(json_report(findings, source))
                batch_payload.append(
                    {
                        "source": rendered_json["source"],
                        "finding_count": rendered_json["finding_count"],
                        "findings": rendered_json["findings"],
                    }
                )
            else:
                if output_format == "markdown":
                    text_reports.append(
                        f"## Source: <code>{escape(str(file_path))}</code>\n\n{report.rstrip()}"
                    )
                else:
                    text_reports.append(f"{source}\n{report.rstrip()}")

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
            report_has_findings,
        )

    return (
        "\n\n".join(text_reports) + ("\n" if text_reports else ""),
        report_has_findings,
    )


def _read_demo(scenario: str = "oidc") -> str:
    """Read a packaged example so `sam-doctor demo` works after installation."""

    return files("sam_doctor").joinpath("data", _DEMO_FILES[scenario]).read_text(encoding="utf-8")


def _write_report(path: Path, report: str) -> None:
    try:
        path.write_text(report, encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not write {path}: {error}") from error


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
                f"- Generated: {datetime.now(UTC).isoformat()}",
                f"- Scenario: {scenario}",
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
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.input == "-":
        stdin_text = sys.stdin.read()
        if not stdin_text:
            raise ValueError("stdin input was empty; provide an error excerpt.")
        source_name = "<stdin>"
        findings = diagnose(stdin_text)
    else:
        source_path = Path(args.input)
        source_name = str(source_path)
        text = _read_text(source_path)
        findings = diagnose(text)

    markdown_path = output_dir / args.markdown_name
    json_path = output_dir / args.json_name
    notes_path = output_dir / args.notes_name

    _write_report(markdown_path, _render_findings(findings, source_name, "markdown"))
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


def _print_error(parser: argparse.ArgumentParser, message: str) -> None:
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: {message}", file=sys.stderr)


def main(argv: list[object] | None = None) -> int:
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
            report, report_has_findings = _batch_render(args.inputs, args.format)
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
        return 1 if args.fail_on_findings and report_has_findings else 0

    if args.command == "packet":
        try:
            return _packet_command(args)
        except ValueError as error:
            _print_error(parser, str(error))
            return 2

    try:
        text = _read_text(args.input)
    except ValueError as error:
        _print_error(parser, str(error))
        return 2

    source_name = "<stdin>" if args.input == Path("-") else args.input.name
    findings = diagnose(text)
    report = _render_findings(findings, source_name, args.format)
    if args.output:
        try:
            _write_report(args.output, report)
        except ValueError as error:
            _print_error(parser, str(error))
            return 2
        print(f"Wrote {args.format} report to {args.output}")
    else:
        sys.stdout.write(report)
    return 1 if args.fail_on_findings and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
