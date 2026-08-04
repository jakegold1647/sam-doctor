from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_gitignore_keeps_growth_and_outreach_artifacts_out_of_version_control():
    repo_root = Path(__file__).resolve().parents[1]
    ignore_lines = (repo_root / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "notes/" in ignore_lines
    assert "artifacts/" in ignore_lines
    assert "launch/outreach-log-template.csv" in ignore_lines
    assert "launch/DISTRIBUTION-TRACKING.md" in ignore_lines
    assert "launch/LAUNCH-PLAN.md" in ignore_lines
    assert "launch/OUTREACH.md" in ignore_lines


def test_launch_and_outreach_defaults_are_local_only(monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    check_launch = _load_script(
        repo_root / "scripts" / "check-launch.py",
        "check_launch_policy",
    )
    bootstrap = _load_script(
        repo_root / "scripts" / "bootstrap-outreach-log.py",
        "bootstrap_outreach_log_policy",
    )

    monkeypatch.setattr(sys, "argv", ["check-launch.py"])
    parsed = check_launch._parse_args()

    assert parsed.append_csv.startswith("notes/")
    assert parsed.summary.startswith("notes/")
    assert parsed.outreach_log.startswith("notes/")
    assert parsed.outreach_summary.startswith("notes/")

    bootstrap_parsed = bootstrap._parse_args([])
    assert bootstrap_parsed.path == "notes/sam-doctor-outreach-log.csv"
