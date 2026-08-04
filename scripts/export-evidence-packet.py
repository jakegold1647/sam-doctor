#!/usr/bin/env python3
"""Compatibility wrapper for repository-context packet generation."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a reproducible evidence packet. New users should prefer "
            "`sam-doctor packet`."
        ),
    )
    parser.add_argument("log_file", help="Path to deployment log, or '-' for stdin.")
    parser.add_argument("--output-dir", default="artifacts", help="Directory for generated packet files.")
    parser.add_argument(
        "--markdown-name",
        default="diagnosis.md",
        help="Markdown report filename.",
    )
    parser.add_argument("--json-name", default="diagnosis.json", help="JSON report filename.")
    parser.add_argument("--notes-name", default="researcher-notes.md", help="Template notes filename.")
    parser.add_argument(
        "--scenario",
        default="Deployment failure triage",
        help="Short scenario label to include in the notes file.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    src_dir = root / "src"
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing if existing else "")

    input_text = None
    if args.log_file == "-":
        stdin_text = sys.stdin.read()
        if not stdin_text:
            raise ValueError("stdin input was empty; provide an error excerpt.")
        input_text = stdin_text

    command = [
        sys.executable,
        "-m",
        "sam_doctor.cli",
        "packet",
        args.log_file,
        "--output-dir",
        args.output_dir,
        "--markdown-name",
        args.markdown_name,
        "--json-name",
        args.json_name,
        "--notes-name",
        args.notes_name,
        "--scenario",
        args.scenario,
    ]
    subprocess.run(
        command,
        input=input_text,
        text=True,
        env=env,
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
