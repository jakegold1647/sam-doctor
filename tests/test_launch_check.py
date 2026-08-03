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


def test_run_outreach_strict_fails_when_log_missing(tmp_path) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    class FakeOutreachModule:
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
                f"ethical_signal: {summary['ethical_signal']}",
                encoding="utf-8",
            )

    fake_module = FakeOutreachModule()

    assert not script.run_outreach(
        tmp_path,
        str(tmp_path / "missing.csv"),
        strict=True,
        summary=str(tmp_path / "artifacts" / "outreach-summary.md"),
        loader=lambda _path: fake_module,
    )


def test_run_outreach_strict_allows_no_data_only_when_flagged(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = _load_script(root)
    sample = tmp_path / "empty-log.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,"
        "voluntary_star,outcome,feedback_signal,repeat_contact\n",
        encoding="utf-8",
    )

    assert not script.run_outreach(
        root,
        str(sample),
        strict=True,
        min_feedback_ratio=100.0,
    )
    assert script.run_outreach(
        root,
        str(sample),
        strict=True,
        min_feedback_ratio=100.0,
        allow_no_data=True,
    )


def test_run_outreach_strict_fails_when_feedback_ratio_is_low(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = _load_script(root)
    sample = tmp_path / "outreach-low-feedback.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,voluntary_star,outcome,feedback_signal,repeat_contact\n"
        "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,share report,1,accepted helpful report,,no\n",
        encoding="utf-8",
    )

    assert not script.run_outreach(
        root,
        str(sample),
        strict=True,
        min_feedback_ratio=100.0,
    )


def test_run_outreach_strict_passes_when_feedback_ratio_is_high_enough(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    script = _load_script(root)
    sample = tmp_path / "outreach-good-feedback.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,voluntary_star,outcome,feedback_signal,repeat_contact\n"
        "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,share report,1,accepted helpful report,asked for follow-up,no\n",
        encoding="utf-8",
    )

    assert script.run_outreach(
        root,
        str(sample),
        strict=True,
        min_feedback_ratio=100.0,
    )


def test_run_outreach_uses_strict_policy_from_module(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[1]
    script = _load_script(root)

    sample = tmp_path / "outreach-mixed.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,voluntary_star,outcome,feedback_signal,repeat_contact\n"
        "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,share report,1,accepted helpful report,,no\n",
        encoding="utf-8",
    )

    calls = {"called": False}

    class FakeOutreachModule:
        def summarize(self, *_args, **_kwargs):
            return {
                "ethical_signal": "mixed",
                "star_feedback_ratio": 0.0,
            }

        def _print_summary(self, *_args, **_kwargs):
            pass

        def _write_summary(self, *_args, **_kwargs):
            pass

        def _passes_strict_ethical_policy(self, summary, min_feedback_ratio):
            calls["called"] = True
            assert summary["ethical_signal"] == "mixed"
            assert min_feedback_ratio == 100.0
            return False, "blocked: mixed signal"

    assert not script.run_outreach(
        root,
        str(sample),
        strict=True,
        min_feedback_ratio=100.0,
        loader=lambda _path: FakeOutreachModule(),
    )
    assert calls["called"]


def test_run_outreach_prints_policy_recommendation_when_available(tmp_path) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])
    sample = tmp_path / "outreach-mixed.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,voluntary_star,outcome,feedback_signal,repeat_contact\n"
        "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,share report,1,accepted helpful report,,no\n",
        encoding="utf-8",
    )

    calls = {"policy": False, "recommendation": False}

    class FakeOutreachModule:
        def summarize(self, *_args, **_kwargs):
            return {
                "ethical_signal": "mixed",
                "star_feedback_ratio": 0.0,
            }

        def _print_summary(self, *_args, **_kwargs):
            pass

        def _write_summary(self, *_args, **_kwargs):
            pass

        def _passes_strict_ethical_policy(self, summary, min_feedback_ratio):
            calls["policy"] = True
            return False, "blocked"

        def _ethical_recommendation(self, summary):
            calls["recommendation"] = True
            return f"fix summary for {summary['ethical_signal']}"

    assert not script.run_outreach(
        tmp_path,
        str(sample),
        strict=True,
        min_feedback_ratio=100.0,
        loader=lambda _path: FakeOutreachModule(),
    )
    assert calls["policy"] and calls["recommendation"]


def test_check_launch_strict_distribution_during_release_forces_distribution_strictness(monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    monkeypatch.setattr(script, "run_launch_readiness", lambda *_args, **_kwargs: (True, 6, 0))
    strict_values: list[bool] = []

    def fake_distribution(*_args, strict: bool = False, **_kwargs):
        strict_values.append(strict)
        return True

    monkeypatch.setattr(script, "run_distribution", fake_distribution)
    monkeypatch.setattr(script, "run_outreach", lambda *_args, **_kwargs: True)

    previous_argv = sys.argv
    try:
        sys.argv = [
            "check-launch.py",
            "--repo-root",
            str(Path(__file__).resolve().parents[1]),
            "--skip-outreach",
            "--strict-distribution-during-release",
        ]
        assert script.main() == 0
    finally:
        sys.argv = previous_argv

    assert strict_values == [True]


def test_check_launch_parse_args_defaults_github_token(monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    monkeypatch.setenv("GITHUB_TOKEN", "env-token-xyz")
    previous_argv = sys.argv
    try:
        sys.argv = ["check-launch.py", "--repo-root", str(Path(__file__).resolve().parents[1]), "--skip-distribution", "--skip-outreach"]
        args = script._parse_args()
        assert args.token == "env-token-xyz"
        assert args.check_launch_token == "env-token-xyz"
    finally:
        sys.argv = previous_argv


def test_check_launch_parse_args_includes_strict_no_data_flags(monkeypatch) -> None:
    script = _load_script(Path(__file__).resolve().parents[1])

    previous_argv = sys.argv
    try:
        sys.argv = [
            "check-launch.py",
            "--skip-distribution",
            "--skip-outreach",
            "--strict-ethical",
            "--allow-no-data-in-strict",
            "--min-feedback-ratio",
            "92.5",
        ]
        args = script._parse_args()
        assert args.strict_ethical is True
        assert args.allow_no_data_in_strict is True
        assert args.min_feedback_ratio == 92.5
    finally:
        sys.argv = previous_argv
