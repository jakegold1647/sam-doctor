#!/usr/bin/env python3
"""Create a reproducible evidence packet for safe sharing and researcher use."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run SAM Doctor on a log and generate a minimal reproducible packet "
            "for sharing with peers."
        ),
    )
    parser.add_argument(
        "log_file",
        type=Path,
        help="Path to deployment log (or '-' to read from stdin).",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Directory for generated packet files.",
    )
    parser.add_argument(
        "--markdown-name",
        default="diagnosis.md",
        help="Markdown report filename.",
    )
    parser.add_argument(
        "--json-name",
        default="diagnosis.json",
        help="JSON report filename.",
    )
    parser.add_argument(
        "--notes-name",
        default="researcher-notes.md",
        help="Template notes filename.",
    )
    parser.add_argument(
        "--scenario",
        default="Deployment failure triage",
        help="Short scenario label to include in the notes file.",
    )
    return parser


def _run_diagnose(
    python_exe: str,
    repository_root: Path,
    log_file: Path,
    output_format: str,
    output_file: Path,
) -> None:
    env = os.environ.copy()
    src_dir = repository_root / "src"
    if src_dir.exists():
        python_path = str(src_dir)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = python_path + (os.pathsep + existing if existing else "")

    result = subprocess.run(
        [
            python_exe,
            "-m",
            "sam_doctor.cli",
            "diagnose",
            str(log_file),
            "--format",
            output_format,
            "--output",
            str(output_file),
        ],
        check=True,
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _write_notes(
    notes_path: Path,
    scenario: str,
    markdown_path: Path,
    json_path: Path,
    command: str,
) -> None:
    finding_count = "unknown"
    top_finding = "No finding payload parsed"

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        findings = payload.get("findings", [])
        finding_count = str(payload.get("finding_count", 0))
        if findings:
            top_finding = findings[0].get("title", findings[0].get("explanation", top_finding))
    except (OSError, json.JSONDecodeError):
        top_finding = "Unavailable (invalid JSON payload)"

    notes_path.write_text(
        "\n".join(
            [
                "# Researcher evidence packet",
                f"- Generated: {datetime.now(timezone.utc).isoformat()}",
                f"- Scenario: {scenario}",
                f"- Command: {command}",
                f"- Markdown report: {markdown_path}",
                f"- JSON report: {json_path}",
                f"- Finding count: {finding_count}",
                f"- Top finding: {top_finding}",
                "",
                "Use only the packet files to discuss this case; do not share full raw logs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = output_dir / args.markdown_name
    json_path = output_dir / args.json_name
    notes_path = output_dir / args.notes_name

    python_exe = sys.executable
    log_path = args.log_file.resolve()

    _run_diagnose(python_exe, repo_root, log_path, "markdown", markdown_path)
    _run_diagnose(python_exe, repo_root, log_path, "json", json_path)

    command = (
        f"python -m sam_doctor.cli diagnose {log_path} "
        f"--format markdown --output {markdown_path.name} && "
        f"python -m sam_doctor.cli diagnose {log_path} --format json --output {json_path.name}"
    )
    _write_notes(notes_path, args.scenario, markdown_path, json_path, command)

    print("Evidence packet generated:")
    print(f"- {markdown_path}")
    print(f"- {json_path}")
    print(f"- {notes_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
