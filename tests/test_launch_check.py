import importlib.util
import sys
from pathlib import Path


def _load_script(root: Path):
    script_path = root / "scripts" / "check-launch.py"
    spec = importlib.util.spec_from_file_location("check_launch", str(script_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load check-launch.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_launch_check_main_passes_with_default_helpers(tmp_path, monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    monkeypatch.setattr(script, "run_launch_readiness", lambda *_args, **_kwargs: (True, 4, 0))
    monkeypatch.setattr(script, "run_distribution", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(script, "run_outreach", lambda *_args, **_kwargs: True)

    previous_argv = sys.argv
    try:
        sys.argv = ["check-launch.py", "--repo-root", str(tmp_path), "--skip-distribution", "--skip-outreach"]
        assert script.main() == 0
    finally:
        sys.argv = previous_argv


def test_launch_check_main_fails_when_launch_readiness_fails(tmp_path, monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    monkeypatch.setattr(script, "run_launch_readiness", lambda *_args, **_kwargs: (False, 3, 1))
    monkeypatch.setattr(script, "run_distribution", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(script, "run_outreach", lambda *_args, **_kwargs: True)

    previous_argv = sys.argv
    try:
        sys.argv = ["check-launch.py", "--repo-root", str(tmp_path), "--skip-distribution", "--skip-outreach"]
        assert script.main() == 1
    finally:
        sys.argv = previous_argv


def test_launch_check_distribution_isolation_no_network(tmp_path, monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    class FakeModule:
        def _collect_snapshot(self, *_args, **_kwargs):
            return {
                "repo": "sam-doctor",
                "timestamp": "2026-08-03T00:00:00Z",
                "repo_stars": 0,
                "forks": 0,
                "open_issues": 0,
                "watchers": 0,
                "releases": 1,
                "discussions_ping": 0,
                "pypi_status": {"ok": True, "details": "200"},
                "marketplace_status": {"ok": True, "details": "200"},
                "site_status": {"ok": True, "details": "200"},
            }

        def _read_last_csv_row(self, *_args, **_kwargs):
            return None

    fake_module = FakeModule()
    fake_module.json = __import__("json")
    fake_module._ensure_parent_directory = lambda *args, **kwargs: None
    fake_module._append_csv = lambda *args, **kwargs: None
    fake_module._write_summary = lambda *args, **kwargs: None
    fake_module._trend_text = lambda *_args, **_kwargs: "stars=+1"
    calls = {"repo": None}

    original_collect = fake_module._collect_snapshot

    def collect_snapshot(repo: str, *_args, **_kwargs):
        calls["repo"] = repo
        return original_collect()

    fake_module._collect_snapshot = collect_snapshot  # type: ignore[assignment]

    loader = lambda _path: fake_module
    assert script.run_distribution(
        tmp_path,
        "jakegold1647/custom-repo",
        "abc",
        output_format="json",
        loader=loader,
    )
    assert calls["repo"] == "jakegold1647/custom-repo"


def test_run_outreach_writes_summary_when_log_missing(tmp_path, monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    class FakeOutreachModule:
        def __init__(self) -> None:
            self.summary_written = ""

        def empty_summary(self):
            return {
                "rows": 0,
                "voluntary_stars": 0,
                "positive_outcome_count": 0,
                "repeat_contacts": 0,
                "stars_without_feedback": 0,
                "top_channels": [],
                "top_outcomes": [],
                "top_problem_areas": [],
                "top_stages": [],
                "ethical_signal": "no_data",
            }

        def _write_summary(self, summary, path):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(
                f"ethical_signal: {summary['ethical_signal']}\n",
                encoding="utf-8",
            )
            self.summary_written = path

    fake_module = FakeOutreachModule()

    assert script.run_outreach(
        tmp_path,
        str(tmp_path / "missing.csv"),
        strict=False,
        summary=str(tmp_path / "artifacts" / "outreach-summary.md"),
        loader=lambda _path: fake_module,
    )
    assert fake_module.summary_written != ""
    assert Path(fake_module.summary_written).exists()
