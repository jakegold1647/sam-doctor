from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("bootstrap_outreach_log", str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _header() -> str:
    return (
        "week,date,contact_channel,problem_area,conversation_stage,next_action,"
        "voluntary_star,outcome,feedback_signal,repeat_contact\n"
    )


def test_bootstrap_creates_tracker_file(tmp_path: Path) -> None:
    module = _load_module(Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-outreach-log.py")
    target = tmp_path / "outreach" / "outreach-log-template.csv"

    created, message = module.bootstrap_log(target)
    assert created
    assert "Created outreach log" in message
    assert target.read_text(encoding="utf-8") == _header()


def test_bootstrap_reports_existing_header(tmp_path: Path) -> None:
    module = _load_module(Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-outreach-log.py")
    target = tmp_path / "outreach-log-template.csv"
    target.write_text(_header(), encoding="utf-8")

    created, message = module.bootstrap_log(target)
    assert not created
    assert "already initialized" in message


def test_bootstrap_rejects_mismatched_tracker(tmp_path: Path) -> None:
    module = _load_module(Path(__file__).resolve().parents[1] / "scripts" / "bootstrap-outreach-log.py")
    target = tmp_path / "outreach-log-template.csv"
    target.write_text("not,a,template\n", encoding="utf-8")

    created, message = module.bootstrap_log(target)
    assert not created
    assert "does not match expected header" in message
