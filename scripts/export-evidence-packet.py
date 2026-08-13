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
    # The child's exit code is the answer, passed through unchanged. With
    # check=True this raised CalledProcessError instead: the CLI's own clear
    # message ("Could not read ...") ended up buried under a Python traceback,
    # and its exit 2 for a missing file was reported as exit 1 - which in this
    # project's contract means findings were found. A wrapper that exists for
    # compatibility has to preserve the contract it is wrapping.
    #
    # stdin is inherited rather than decoded and forwarded as text. That lets
    # the CLI inspect a byte-order mark before Python's text decoder can replace
    # bytes or insert NULs into a UTF-16 log.
    completed = subprocess.run(
        command,
        env=env,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
