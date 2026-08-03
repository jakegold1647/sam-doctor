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
