"""Command-line interface for SAM Doctor."""

from __future__ import annotations

import argparse
import glob
import json
from html import escape
from importlib.resources import files
import sys
from pathlib import Path

from . import __version__
from .diagnostics import diagnose, json_report, markdown_report, rules_report, terminal_report


_DEMO_FILES = {
    "oidc": "oidc-assume-role-failure.txt",
    "cloudformation": "cloudformation-resource-failure.txt",
    "capabilities": "capability-acknowledgement-failure.txt",
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
        choices=("terminal", "markdown", "json"),
        default="terminal",
        help="Report format for stdout or --output.",
    )
    diagnose_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")

    demo_parser = subcommands.add_parser("demo", help="Run a bundled deployment failure example.")
    demo_parser.add_argument(
        "--scenario",
        choices=tuple(_DEMO_FILES),
        default="oidc",
        help="Bundled failure scenario to diagnose.",
    )
    demo_parser.add_argument("--format", choices=("terminal", "markdown", "json"), default="terminal")
    demo_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")

    rules_parser = subcommands.add_parser("rules", help="List the currently supported diagnostic rules.")
    rules_parser.add_argument("--format", choices=("terminal", "json"), default="terminal")
    rules_parser.add_argument("--output", type=Path, help="Write the rule catalog to this path instead of stdout.")

    batch_parser = subcommands.add_parser("batch", help="Analyze multiple logs in one run.")
    batch_parser.add_argument(
        "inputs",
        nargs="+",
        help=(
            "One or more log files, directories, or wildcard paths. "
            "Directories are scanned for *.log and *.txt files."
        ),
    )
    batch_parser.add_argument(
        "--format",
        choices=("terminal", "markdown", "json"),
        default="terminal",
        help="Report format for each file or the overall JSON output.",
    )
    batch_parser.add_argument(
        "--output",
        type=Path,
        help="Write the batch report to this path instead of stdout.",
    )
    return parser


def _read_text(path: Path) -> str:
    if path == Path("-"):
        return sys.stdin.read()
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ValueError(f"Could not read {path}: {error}") from error


def _render(text: str, source_name: str, output_format: str) -> str:
    findings = diagnose(text)
    if output_format == "markdown":
        return markdown_report(findings, source_name)
    if output_format == "json":
        return json_report(findings, source_name)
    return terminal_report(findings, source_name) + "\n"


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


def _batch_render(inputs: list[str], output_format: str) -> str:
    if not inputs:
        raise ValueError("No inputs provided for batch mode.")

    text_reports: list[str] = []
    batch_payload: list[dict[str, object]] = []
    for input_value in inputs:
        for file_path in _expand_input_paths(input_value):
            text = _read_text(file_path)
            source = str(file_path)
            report = _render(text, source, output_format)

            if output_format == "json":
                findings = json.loads(report)
                batch_payload.append(
                    {
                        "source": findings["source"],
                        "finding_count": findings["finding_count"],
                        "findings": findings["findings"],
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
        return json.dumps(
            {
                "sam_doctor_version": __version__,
                "batch_count": len(batch_payload),
                "results": batch_payload,
            },
            indent=2,
        ) + "\n"

    return "\n\n".join(text_reports) + ("\n" if text_reports else "")


def _read_demo(scenario: str = "oidc") -> str:
    """Read a packaged example so `sam-doctor demo` works after installation."""

    return files("sam_doctor").joinpath("data", _DEMO_FILES[scenario]).read_text(encoding="utf-8")


def _write_report(path: Path, report: str) -> None:
    try:
        path.write_text(report, encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not write {path}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo":
        report = _render(_read_demo(args.scenario), _DEMO_FILES[args.scenario], args.format)
        if args.output:
            try:
                _write_report(args.output, report)
            except ValueError as error:
                parser.error(str(error))
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
                parser.error(str(error))
            print(f"Wrote {args.format} rule catalog to {args.output}")
        else:
            sys.stdout.write(report)
        return 0

    if args.command == "batch":
        try:
            report = _batch_render(args.inputs, args.format)
        except ValueError as error:
            parser.error(str(error))
            return 1

        if args.output:
            try:
                _write_report(args.output, report)
            except ValueError as error:
                parser.error(str(error))
            print(f"Wrote batch {args.format} report to {args.output}")
        else:
            sys.stdout.write(report)
        return 0

    try:
        text = _read_text(args.input)
    except ValueError as error:
        parser.error(str(error))
        return 1

    source_name = "<stdin>" if args.input == Path("-") else args.input.name
    report = _render(text, source_name, args.format)
    if args.output:
        try:
            _write_report(args.output, report)
        except ValueError as error:
            parser.error(str(error))
        print(f"Wrote {args.format} report to {args.output}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
