from pathlib import Path
import importlib.util
import sys


def _load_distribution_script():
    spec = importlib.util.spec_from_file_location(
        "distribution_check_script",
        str(Path(__file__).resolve().parents[1] / "scripts" / "check-distribution.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load distribution checker module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_to_int_handles_non_numeric_values():
    mod = _load_distribution_script()

    assert mod._to_int("7") == 7
    assert mod._to_int("invalid", default=-1) == -1
    assert mod._to_int(None, default=0) == 0


def test_delta_uses_previous_row_when_present():
    mod = _load_distribution_script()

    current = {
        "repo_stars": "12",
        "forks": "3",
        "open_issues": "4",
        "watchers": 6,
        "releases": 9,
    }
    previous = {
        "repo_stars": "10",
        "forks": "1",
        "open_issues": "2",
        "watchers": "4",
        "releases": "8",
    }

    assert mod._delta(current["repo_stars"], previous, "repo_stars") == 2
    assert mod._delta(current["forks"], previous, "forks") == 2
    assert mod._delta(current["open_issues"], previous, "open_issues") == 2
    assert mod._delta(current["watchers"], previous, "watchers") == 2
    assert mod._delta(current["releases"], previous, "releases") == 1


def test_trend_text_is_ascii_and_baseline_or_deltaed():
    mod = _load_distribution_script()

    snapshot = {
        "repo_stars": "11",
        "forks": "9",
        "open_issues": "3",
        "watchers": "5",
        "releases": 14,
    }

    assert mod._trend_text(snapshot, None) == "baseline: no previous row for comparison"

    previous = {
        "repo_stars": "10",
        "forks": "9",
        "open_issues": "5",
        "watchers": "2",
        "releases": 13,
    }

    trend = mod._trend_text(snapshot, previous)
    assert trend == "stars=+1, forks=+0, open_issues=-2, watchers=+3, releases=+1"
    assert "Î" not in trend
    assert "Δ" not in trend


def test_launch_readiness_checks_homepage_and_topics():
    mod = _load_distribution_script()

    setup = mod._evaluate_launch_readiness(
        {
            "homepage": "https://jakegold1647.github.io/sam-doctor/",
            "topics": [
                "aws",
                "aws-sam",
                "cloudformation",
                "github-actions",
                "iam",
                "python",
                "serverless",
                "cli",
            ],
        }
    )

    assert setup["homepage_ok"] is True
    assert setup["topics_ok"] is True
    assert setup["topics_count"] == 8
    assert setup["missing_topics"] == []


def test_launch_readiness_flags_partial_config():
    mod = _load_distribution_script()

    setup = mod._evaluate_launch_readiness(
        {
            "homepage": "https://example.com/custom-home",
            "topics": ["aws", "cli"],
        }
    )

    assert setup["homepage_ok"] is False
    assert setup["topics_ok"] is False
    assert "python" in set(setup["missing_topics"])


def test_summary_lines_includes_launch_setup():
    mod = _load_distribution_script()

    snapshot = {
        "timestamp": "2026-08-03T00:00:00Z",
        "repo": "jakegold1647/sam-doctor",
        "repo_stars": 0,
        "forks": 0,
        "open_issues": 0,
        "watchers": 0,
        "releases": 7,
        "discussions_ping": 0,
        "pypi_status": {"ok": False, "details": "404 Not Found"},
        "marketplace_status": {"ok": True, "details": "200"},
        "site_status": {"ok": True, "details": "200"},
        "launch_readiness": {
            "homepage_ok": True,
            "topics_ok": False,
            "topics_count": 5,
            "missing_topics": ["python"],
        },
    }

    lines = mod._summary_lines(snapshot, None)
    assert any(line.startswith("- launch-setup: partial") for line in lines)
    assert any("marketplace_pre_release_listed" in line for line in lines)
    assert any("launch_setup_topics_count" in line for line in lines)


def test_summary_lines_no_launch_readiness_does_not_crash():
    mod = _load_distribution_script()

    snapshot = {
        "timestamp": "2026-08-03T00:00:00Z",
        "repo": "jakegold1647/sam-doctor",
        "repo_stars": 1,
        "forks": 0,
        "open_issues": 0,
        "watchers": 0,
        "releases": 7,
        "discussions_ping": 0,
        "pypi_status": {"ok": True, "details": "200"},
        "marketplace_status": {"ok": True, "details": "200"},
        "site_status": {"ok": True, "details": "200"},
    }

    lines = mod._summary_lines(snapshot, None)
    assert any(line.startswith("# SAM Doctor launch status") for line in lines)
    assert any("launch_setup_missing_topics" in line for line in lines)


def test_marketplace_pre_release_marker_is_detected(monkeypatch):
    mod = _load_distribution_script()

    class DummyResponse:
        def __init__(self, body: str, status: int = 200):
            self._body = body
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._body.encode("utf-8")

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda _request, timeout=20: DummyResponse("<html>Latest pre-release</html>"))
    listing = mod._marketplace_pre_release_status("https://github.com/marketplace/actions/sam-doctor-aws-deployment-diagnostics")

    assert listing["ok"] is True
    assert listing["pre_release_listed"] is True
