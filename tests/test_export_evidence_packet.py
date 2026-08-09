from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import child_env

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


def test_packet_notes_redact_identifiers_in_source_path(tmp_path: Path) -> None:
    log = tmp_path / "deploy-123456789012-owner@example.com.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(["packet", str(log), "--output-dir", str(output_dir)])

    assert exit_code == 0
    notes = (output_dir / "researcher-notes.md").read_text(encoding="utf-8")
    assert "123456789012" not in notes
    assert "owner@example.com" not in notes
    assert "[REDACTED_ACCOUNT_ID]" in notes


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
    env = child_env()

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


def test_packet_calls_an_empty_log_empty(tmp_path: Path) -> None:
    """The packet is the artifact people hand to a colleague or a ticket.

    Labelling an empty log 'no supported pattern found' there sends the reader
    looking for a missing rule instead of the step that never wrote the log.
    """
    log = tmp_path / "deployment.log"
    log.write_text("", encoding="utf-8")
    out_dir = tmp_path / "artifacts"

    assert main(["packet", str(log), "--output-dir", str(out_dir)]) == 0
    rendered = (out_dir / "diagnosis.md").read_text(encoding="utf-8")
    assert "Nothing to diagnose" in rendered
    assert "No supported pattern found" not in rendered


def test_packet_keeps_unmatched_wording_for_a_real_log(tmp_path: Path) -> None:
    from sam_doctor.cli import main

    log = tmp_path / "deployment.log"
    log.write_text("A failure no rule covers\n", encoding="utf-8")
    out_dir = tmp_path / "artifacts"

    assert main(["packet", str(log), "--output-dir", str(out_dir)]) == 0
    rendered = (out_dir / "diagnosis.md").read_text(encoding="utf-8")
    assert "No supported pattern found" in rendered
    assert "Nothing to diagnose" not in rendered


def test_packet_notes_name_the_file_not_the_path(tmp_path: Path) -> None:
    # The packet's own notes say to discuss the case using these files, so they
    # are a sharing artifact: the directory a log happened to sit in should not
    # travel with them.
    private_dir = tmp_path / "acme-private-client" / "infra"
    private_dir.mkdir(parents=True)
    log = private_dir / "deployment.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(["packet", str(log), "--output-dir", str(output_dir)])

    assert exit_code == 0
    notes = (output_dir / "researcher-notes.md").read_text(encoding="utf-8")
    assert "- Source: deployment.log" in notes
    assert "acme-private-client" not in notes


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export-evidence-packet.py"


def _run_wrapper(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=child_env(),
        check=False,
    )


def test_the_wrapper_passes_the_cli_exit_code_through(tmp_path: Path) -> None:
    # docs/cli-exit-and-action-exit-codes.md: 2 is a precondition failure, 1 means
    # findings were found. check=True collapsed the difference - a missing file
    # became CalledProcessError and exit 1, so a workflow branching on the code
    # read "your deployment has problems" from "your path is wrong".
    result = _run_wrapper(
        str(tmp_path / "does-not-exist.log"), "--output-dir", str(tmp_path / "out")
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    # The CLI's own message has to survive rather than be buried in a traceback.
    assert "Could not read" in result.stdout + result.stderr


def test_empty_stdin_is_a_precondition_failure_not_a_crash(tmp_path: Path) -> None:
    result = _run_wrapper("-", "--output-dir", str(tmp_path / "out"), stdin="")

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "stdin input was empty" in result.stderr


def test_a_successful_wrapper_run_still_exits_zero_and_writes_the_packet(
    tmp_path: Path,
) -> None:
    log = tmp_path / "failure.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8"
    )
    output_dir = tmp_path / "artifacts"

    result = _run_wrapper(str(log), "--output-dir", str(output_dir))

    assert result.returncode == 0, result.stderr
    assert (output_dir / "diagnosis.json").is_file()
    assert (output_dir / "diagnosis.md").is_file()
    assert (output_dir / "researcher-notes.md").is_file()


def test_an_uncreatable_output_dir_is_a_precondition_failure(tmp_path: Path) -> None:
    # docs/cli-exit-and-action-exit-codes.md promises exit 2 on a read/write
    # failure. mkdir was called bare while reads and writes both translated
    # OSError, so this raised a traceback and exit 1 - the code that means a fail
    # gate was hit. A read-only checkout or a full disk lands here.
    log = tmp_path / "failure.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity", encoding="utf-8"
    )
    blocked = tmp_path / "already-a-file"
    blocked.write_text("not a directory", encoding="utf-8")

    for command in ("packet", "request-packet"):
        exit_code = main([command, str(log), "--output-dir", str(blocked / "out")])
        assert exit_code == 2, f"{command} returned {exit_code}"


def test_init_reports_an_uncreatable_workflow_directory(tmp_path: Path) -> None:
    blocked = tmp_path / "already-a-file"
    blocked.write_text("not a directory", encoding="utf-8")

    exit_code = main(["init", "--workflow-file", str(blocked / "wf" / "sam-doctor.yml")])

    assert exit_code == 2
