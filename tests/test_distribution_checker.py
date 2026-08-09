import importlib.util
import sys
from pathlib import Path

import pytest


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


def _alias_path(tmp_path: Path, source: Path, alias_kind: str) -> Path:
    if alias_kind == "literal":
        return source
    if alias_kind == "normalized":
        return tmp_path / "unused" / ".." / source.name

    alias = tmp_path / f"{alias_kind}-{source.name}"
    try:
        if alias_kind == "hardlink":
            alias.hardlink_to(source)
        else:
            alias.symlink_to(source.name)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"{alias_kind} aliases unavailable: {error}")
    return alias


@pytest.mark.parametrize(
    ("first_option", "second_option"),
    (
        ("--output", "--append-csv"),
        ("--output", "--summary"),
        ("--summary", "--append-csv"),
    ),
)
@pytest.mark.parametrize("alias_kind", ("literal", "normalized", "hardlink", "symlink"))
def test_distribution_outputs_must_be_distinct_before_collection(
    tmp_path: Path,
    capsys,
    first_option: str,
    second_option: str,
    alias_kind: str,
) -> None:
    mod = _load_distribution_script()
    first = tmp_path / "tracking.csv"
    sentinel = "existing tracking data\n"
    first.write_text(sentinel, encoding="utf-8")
    second = _alias_path(tmp_path, first, alias_kind)

    argv_backup = sys.argv
    try:
        sys.argv = [
            "check-distribution.py",
            "--output-format",
            "json",
            first_option,
            str(first),
            second_option,
            str(second),
        ]
        assert mod.main() == 2
    finally:
        sys.argv = argv_backup

    assert "must resolve to distinct files" in capsys.readouterr().err
    assert first.read_text(encoding="utf-8") == sentinel


def test_distribution_rejects_hard_link_output_before_collection(
    tmp_path: Path, capsys
) -> None:
    mod = _load_distribution_script()
    victim = tmp_path / "victim.json"
    sentinel = "keep this unrelated file\n"
    victim.write_text(sentinel, encoding="utf-8")
    output = tmp_path / "snapshot.json"
    try:
        output.hardlink_to(victim)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"hard links unavailable: {error}")

    argv_backup = sys.argv
    try:
        sys.argv = [
            "check-distribution.py",
            "--output-format",
            "json",
            "--output",
            str(output),
        ]
        assert mod.main() == 2
    finally:
        sys.argv = argv_backup

    assert "must not be a hard link" in capsys.readouterr().err
    assert victim.read_text(encoding="utf-8") == sentinel


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
            "homepage": "https://sam-doctor.jacobgoldstein.dev/",
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


def test_strict_distribution_violations_surface_expected_failures():
    mod = _load_distribution_script()
    snapshot = {
        "pypi_status": {"ok": True, "details": "200"},
        "marketplace_status": {"ok": False, "details": "503", "pre_release_listed": False},
        "site_status": {"ok": False, "details": "404"},
        "launch_readiness": {
            "homepage_ok": False,
            "topics_ok": False,
            "missing_topics": ["python", "cli"],
            "topics_count": 3,
        },
    }

    violations = mod._strict_distribution_violations(snapshot)
    assert "GitHub Marketplace listing is not reachable" in violations
    assert "Project website is not reachable" in violations
    assert "Repository homepage is missing or not set to the public site URL" in violations
    assert "Required repository topics are missing: python, cli" in violations


def test_strict_distribution_passes_on_healthy_distribution_snapshot():
    mod = _load_distribution_script()
    snapshot = {
        "pypi_status": {"ok": True, "details": "200"},
        "marketplace_status": {"ok": True, "details": "200", "pre_release_listed": False},
        "site_status": {"ok": True, "details": "200"},
        "launch_readiness": {
            "homepage_ok": True,
            "topics_ok": True,
            "missing_topics": [],
            "topics_count": 8,
        },
    }

    assert mod._strict_distribution_violations(snapshot) == []
