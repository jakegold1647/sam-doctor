"""Command-line interface for SAM Doctor."""

from __future__ import annotations

import argparse
from importlib.resources import files
from pathlib import Path
import sys

from . import __version__
from .diagnostics import diagnose, markdown_report, terminal_report


_DEMO_NAME = "oidc-assume-role-failure.txt"


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
    diagnose_parser.add_argument("--format", choices=("terminal", "markdown"), default="terminal")
    diagnose_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")

    demo_parser = subcommands.add_parser("demo", help="Run the bundled OIDC failure example.")
    demo_parser.add_argument("--format", choices=("terminal", "markdown"), default="terminal")
    demo_parser.add_argument("--output", type=Path, help="Write the report to this path instead of stdout.")
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
    return terminal_report(findings, source_name) + "\n"


def _read_demo() -> str:
    """Read the packaged example so `sam-doctor demo` works after installation."""

    return files("sam_doctor").joinpath("data", _DEMO_NAME).read_text(encoding="utf-8")


def _write_report(path: Path, report: str) -> None:
    try:
        path.write_text(report, encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not write {path}: {error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo":
        report = _render(_read_demo(), _DEMO_NAME, args.format)
        if args.output:
            try:
                _write_report(args.output, report)
            except ValueError as error:
                parser.error(str(error))
            print(f"Wrote {args.format} report to {args.output}")
        else:
            sys.stdout.write(report)
        return 0

    try:
        text = _read_text(args.input)
    except ValueError as error:
        parser.error(str(error))

    report = _render(text, args.input.name, args.format)
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
