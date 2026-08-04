from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sam_doctor.cli import main


def test_export_evidence_packet_generates_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "export-evidence-packet.py"
    log = tmp_path / "failure.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )

    output_dir = tmp_path / "artifacts"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            str(log),
            "--output-dir",
            str(output_dir),
            "--scenario",
            "OIDC triage",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Evidence packet generated:" in result.stdout
    markdown = output_dir / "diagnosis.md"
    json_report = output_dir / "diagnosis.json"
    notes = output_dir / "researcher-notes.md"

    assert markdown.exists()
    assert json_report.exists()
    assert notes.exists()

    payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert payload["finding_count"] == 1
    assert "OIDC triage" in notes.read_text(encoding="utf-8")


def test_export_evidence_packet_supports_stdin_marker(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "export-evidence-packet.py"
    output_dir = tmp_path / "artifacts"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "-",
            "--output-dir",
            str(output_dir),
            "--scenario",
            "piped input",
        ],
        input="Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        text=True,
        check=True,
        capture_output=True,
    )

    assert "Evidence packet generated:" in result.stdout
    json_report = output_dir / "diagnosis.json"
    payload = json.loads(json_report.read_text(encoding="utf-8"))
    assert payload["finding_count"] == 1


def test_cli_packet_generates_default_artifacts(tmp_path: Path) -> None:
    log = tmp_path / "failure.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    assert (
        main(
            [
                "packet",
                str(log),
                "--output-dir",
                str(output_dir),
                "--scenario",
                "CLI triage",
            ]
        )
        == 0
    )

    assert (output_dir / "diagnosis.md").exists()
    assert (output_dir / "diagnosis.json").exists()
    assert (output_dir / "researcher-notes.md").exists()
    report = json.loads((output_dir / "diagnosis.json").read_text(encoding="utf-8"))
    assert report["finding_count"] == 1


def test_cli_packet_supports_stdin(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sam_doctor.cli",
            "packet",
            "-",
            "--output-dir",
            str(output_dir),
        ],
        input="Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    assert "Evidence packet generated:" in result.stdout
    assert output_dir.exists()

    report = json.loads((output_dir / "diagnosis.json").read_text(encoding="utf-8"))
    assert report["finding_count"] == 1
