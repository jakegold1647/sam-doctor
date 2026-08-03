from pathlib import Path


def test_action_wrapper_script_has_posix_newlines():
    script = Path("scripts") / "run-github-action.sh"
    assert script.exists(), "run-github-action.sh should exist"
    content = script.read_bytes()
    assert b"\r\n" not in content
    assert content.startswith(b"#!/usr/bin/env bash")
