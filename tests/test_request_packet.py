from __future__ import annotations

from pathlib import Path

import pytest

from sam_doctor.cli import main
from sam_doctor.diagnostics import likely_error_excerpt


def test_likely_error_excerpt_finds_context_around_first_match() -> None:
    text = (
        "Starting deployment\n"
        "Uploading artifacts\n"
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity\n"
        "Rolling back stack\n"
        "Deployment complete"
    )

    excerpt = likely_error_excerpt(text, context=1)

    assert [line_number for line_number, _ in excerpt] == [2, 3, 4]
    assert "AssumeRoleWithWebIdentity" in excerpt[1][1]


def test_likely_error_excerpt_returns_empty_when_nothing_looks_wrong() -> None:
    text = "Starting deployment\nUploading artifacts\nDeployment complete\n"

    assert likely_error_excerpt(text) == ()


def test_likely_error_excerpt_redacts_sensitive_data() -> None:
    text = (
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
        "for arn:aws:iam::123456789012:role/deployer, contact owner@example.com, "
        "key AKIAABCDEFGHIJKLMNOP"
    )

    excerpt = likely_error_excerpt(text)

    (_, line) = excerpt[0]
    assert "123456789012" not in line
    assert "owner@example.com" not in line
    assert "AKIAABCDEFGHIJKLMNOP" not in line
    assert "[REDACTED_ARN]" in line
    assert "[REDACTED_EMAIL]" in line
    assert "[REDACTED_AWS_ACCESS_KEY]" in line


def test_likely_error_excerpt_caps_at_max_lines() -> None:
    text = "\n".join(["denied line"] + [f"noise {i}" for i in range(30)])

    excerpt = likely_error_excerpt(text, context=20, max_lines=5)

    assert len(excerpt) <= 5


def test_cli_request_packet_writes_excerpt_for_unmatched_log(tmp_path: Path) -> None:
    log = tmp_path / "unmatched.log"
    log.write_text(
        "\n".join(
            [f"noise line {i}" for i in range(5)]
            + ["Something odd happened that no rule covers: widget-error-9000"]
            + [f"more noise {i}" for i in range(5)]
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(
        ["request-packet", str(log), "--output-dir", str(output_dir), "--context", "1"]
    )

    assert exit_code == 0
    excerpt_path = output_dir / "rule-request.md"
    assert excerpt_path.exists()
    content = excerpt_path.read_text(encoding="utf-8")
    assert "widget-error-9000" in content
    assert "noise line 0" not in content
    assert "more noise 4" not in content
    assert "rule request" in content.lower()


@pytest.mark.parametrize("escape_kind", ("traversal", "absolute"))
def test_request_packet_name_cannot_escape_output_dir(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    escape_kind: str,
) -> None:
    log = tmp_path / "unmatched.log"
    log.write_text("Error: a new deployment failure\n", encoding="utf-8")
    output_dir = tmp_path / "artifacts"
    victim = tmp_path / f"request-{escape_kind}.sentinel"
    sentinel = "do not overwrite\n"
    victim.write_text(sentinel, encoding="utf-8")
    unsafe_name = (
        f"../{victim.name}" if escape_kind == "traversal" else str(victim.resolve())
    )

    exit_code = main(
        [
            "request-packet",
            str(log),
            "--output-dir",
            str(output_dir),
            "--name",
            unsafe_name,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert victim.read_text(encoding="utf-8") == sentinel
    assert captured.err.startswith("usage:")
    assert "--name" in captured.err
    assert "inside --output-dir" in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert list(output_dir.rglob("*")) == []


def test_request_packet_allows_nested_name_inside_output_dir(tmp_path: Path) -> None:
    log = tmp_path / "unmatched.log"
    log.write_text("Error: a new deployment failure\n", encoding="utf-8")
    output_dir = tmp_path / "artifacts"
    nested_dir = output_dir / "nested"
    nested_dir.mkdir(parents=True)

    exit_code = main(
        [
            "request-packet",
            str(log),
            "--output-dir",
            str(output_dir),
            "--name",
            "nested/rule-request.md",
        ]
    )

    assert exit_code == 0
    assert (nested_dir / "rule-request.md").is_file()


@pytest.mark.parametrize("alias_kind", ("literal", "normalized"))
def test_request_packet_output_cannot_alias_file_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    alias_kind: str,
) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    log = output_dir / "input.log"
    sentinel = "Error: a new deployment failure\n"
    log.write_text(sentinel, encoding="utf-8")
    output_name = "input.log" if alias_kind == "literal" else "nested/../input.log"

    exit_code = main(
        [
            "request-packet",
            str(log),
            "--output-dir",
            str(output_dir),
            "--name",
            output_name,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.err.startswith("usage:")
    assert "must not resolve to an output target" in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert log.read_text(encoding="utf-8") == sentinel
    assert {
        path.relative_to(output_dir).as_posix() for path in output_dir.rglob("*")
    } == {"input.log"}


def test_request_packet_output_cannot_alias_file_input_through_existing_symlink(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    log = output_dir / "input.log"
    sentinel = "Error: a new deployment failure\n"
    log.write_text(sentinel, encoding="utf-8")
    alias = output_dir / "input-link.log"
    try:
        alias.symlink_to(log.name)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")

    exit_code = main(
        [
            "request-packet",
            str(log),
            "--output-dir",
            str(output_dir),
            "--name",
            alias.name,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.err.startswith("usage:")
    assert "must not resolve to an output target" in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert log.read_text(encoding="utf-8") == sentinel
    assert alias.is_symlink()
    assert not (output_dir / "rule-request.md").exists()


def test_request_packet_output_cannot_alias_file_input_through_hard_link(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "artifacts"
    output_dir.mkdir()
    log = output_dir / "input.log"
    sentinel = "Error: a new deployment failure\n"
    log.write_text(sentinel, encoding="utf-8")
    alias = output_dir / "input-hard-link.log"
    try:
        alias.hardlink_to(log)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"hard links unavailable: {error}")

    exit_code = main(
        [
            "request-packet",
            str(log),
            "--output-dir",
            str(output_dir),
            "--name",
            alias.name,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "must not resolve to an output target" in captured.err
    assert log.read_text(encoding="utf-8") == sentinel
    assert alias.read_text(encoding="utf-8") == sentinel


def test_request_packet_missing_input_error_precedes_output_alias_check(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "artifacts"
    missing_log = output_dir / "missing.log"

    exit_code = main(
        [
            "request-packet",
            str(missing_log),
            "--output-dir",
            str(output_dir),
            "--name",
            missing_log.name,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Could not read" in captured.err
    assert "must not resolve to an output target" not in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert list(output_dir.rglob("*")) == []


def test_cli_request_packet_reports_no_excerpt_when_nothing_looks_wrong(tmp_path: Path) -> None:
    log = tmp_path / "clean.log"
    log.write_text("Deployment completed with no failures.\n", encoding="utf-8")
    output_dir = tmp_path / "artifacts"

    exit_code = main(["request-packet", str(log), "--output-dir", str(output_dir)])

    assert exit_code == 0
    content = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "No line looked like an error" in content


def test_cli_request_packet_redacts_account_id_and_email(tmp_path: Path) -> None:
    log = tmp_path / "failure.log"
    log.write_text(
        "Not authorized to perform: sts:AssumeRoleWithWebIdentity "
        "for arn:aws:iam::123456789012:role/deployer, contact owner@example.com",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(["request-packet", str(log), "--output-dir", str(output_dir)])

    assert exit_code == 0
    content = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "123456789012" not in content
    assert "owner@example.com" not in content


def test_cli_request_packet_supports_stdin(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "artifacts"
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO("Not authorized to perform: sts:AssumeRoleWithWebIdentity\n"),
    )

    exit_code = main(["request-packet", "-", "--output-dir", str(output_dir)])

    assert exit_code == 0
    content = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "<stdin>" in content


def test_cli_request_packet_empty_stdin_exits_2(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(""))

    exit_code = main(["request-packet", "-", "--output-dir", str(tmp_path / "artifacts")])

    assert exit_code == 2
    assert "empty" in capsys.readouterr().err


def test_rule_request_excerpt_names_the_file_not_the_path(tmp_path: Path) -> None:
    # This artifact exists to be pasted into a public rule request, and a working
    # path usually names the repository - which CONTRIBUTING tells contributors
    # never to post - along with the OS user name. The file name is the part that
    # carries diagnostic meaning.
    private_dir = tmp_path / "acme-private-client" / "infra"
    private_dir.mkdir(parents=True)
    log = private_dir / "deployment.log"
    log.write_text(
        "SomeNovelFailure: the reticulator exploded\nError: deploy failed\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts"

    exit_code = main(
        ["request-packet", str(log), "--output-dir", str(output_dir)]
    )

    assert exit_code == 0
    excerpt = (output_dir / "rule-request.md").read_text(encoding="utf-8")
    assert "- Source: deployment.log" in excerpt
    assert "acme-private-client" not in excerpt
    assert str(private_dir) not in excerpt
