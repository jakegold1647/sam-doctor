import importlib.util
import sys
from pathlib import Path



def _load_script(root: Path):
    script_path = root / "scripts" / "check-outreach.py"
    spec = importlib.util.spec_from_file_location("check_outreach", str(script_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load check-outreach.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_outreach_script_is_missing_when_path_is_invalid(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    # load with temporary cwd to keep path-independent.
    script_path = tmp_path / "missing.csv"
    argv_backup = sys.argv
    try:
        sys.argv = ["check-outreach.py", str(script_path)]
        assert module.main() == 1
    finally:
        sys.argv = argv_backup


def test_outreach_summary_parses_examples(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-log.csv"
    sample.write_text(
        (
            "week,date,contact_channel,problem_area,conversation_stage,next_action,"
            "voluntary_star,outcome,feedback_signal,repeat_contact\n"
            "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,"
            "share report,1,accepted helpful report,asked for follow-up,no\n"
            "2026-W31,2026-08-02,LinkedIn,CloudFormation,feedback requested,"
            "send summary,0,declined,no follow-up signal,no\n"
            "2026-W31,2026-08-03,Slack,API Gateway,waiting for reply,"
            "send safe steps,0,scheduled follow-up,pending,yes\n"
        ),
        encoding="utf-8",
    )

    summary = module.summarize(sample)
    assert summary["rows"] == 3
    assert summary["voluntary_stars"] == 1
    assert summary["repeat_contacts"] == 1
    assert summary["stars_without_feedback"] == 0
    assert summary["rows_with_feedback"] == 3
    assert summary["ethical_signal"] in {"strong", "mixed", "watch"}
    assert summary["ethical_signal_strength"] == 100.0
    assert len(summary["top_stages"]) == 3
    assert len(summary["top_problem_areas"]) == 3
    assert isinstance(summary["top_channels"], list)
    assert summary["top_outcomes"][0][0] in {"accepted helpful report", "declined", "scheduled follow-up"}
    assert summary["organic_growth_score"] > 0.0


def test_outreach_highlights_stars_without_feedback(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-echo.csv"
    sample.write_text(
        (
            "week,date,contact_channel,problem_area,conversation_stage,next_action,"
            "voluntary_star,outcome,feedback_signal,repeat_contact\n"
            "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,"
            "share report,1,accepted helpful report,,no\n"
            "2026-W31,2026-08-02,LinkedIn,CloudFormation,feedback requested,"
            "send summary,0,declined,asked for follow-up check,no\n"
        ),
        encoding="utf-8",
    )

    summary = module.summarize(sample)
    assert summary["voluntary_stars"] == 1
    assert summary["stars_without_feedback"] == 1
    assert summary["ethical_signal"] == "mixed"
    assert summary["ethical_signal_strength"] == 0.0
    assert summary["rows_with_feedback"] == 1


def test_outreach_main_writes_summary_file(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-log.csv"
    sample.write_text(
        (
            "week,date,contact_channel,problem_area,conversation_stage,next_action,"
            "voluntary_star,outcome,feedback_signal,repeat_contact\n"
            "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,"
            "share diagnostic report,1,accepted helpful report,asked for follow-up,no\n"
            "2026-W31,2026-08-02,LinkedIn,CloudFormation,feedback requested,"
            "send summary,0,declined,no follow-up signal,no\n"
            "2026-W31,2026-08-03,Slack,API Gateway,waiting for reply,"
            "send safe steps,0,scheduled follow-up,pending,yes\n"
        ),
        encoding="utf-8",
    )
    summary_path = tmp_path / "artifacts" / "outreach-summary.md"

    argv_backup = sys.argv
    try:
        sys.argv = [
            "check-outreach.py",
            str(sample),
            "--summary",
            str(summary_path),
        ]
        assert module.main() == 0
    finally:
        sys.argv = argv_backup

    assert summary_path.exists()
    rendered = summary_path.read_text(encoding="utf-8")
    assert rendered.startswith("# SAM Doctor ethical outreach status")
    assert "ethical_signal" in rendered
    assert "recommendation" in rendered
    assert "next_growth_actions" in rendered
    assert "organic_growth_score" in rendered


def test_growth_score_prefers_feedback_and_follow_through() -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)

    score = module._growth_score(
        voluntary_stars=4,
        stars_with_feedback=2,
        repeat_contacts=1,
        rows_with_feedback=3,
        rows=5,
    )

    assert score == 47.5


def test_summary_reports_organic_growth_score(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    log = tmp_path / "outreach.csv"
    log.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,"
        "voluntary_star,outcome,feedback_signal,repeat_contact\n"
        "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,share report,"
        "1,accepted helpful report,asked for follow-up,no\n"
        "2026-W31,2026-08-02,LinkedIn,CloudFormation,pilot follow-up,share update,"
        "0,ignored,did not reply,no\n",
        encoding="utf-8",
    )

    summary = module.summarize(log)
    assert summary["rows"] == 2
    assert summary["voluntary_stars"] == 1
    assert summary["stars_without_feedback"] == 0
    assert summary["ethical_signal"] == "strong"
    assert summary["organic_growth_score"] == module._growth_score(
        voluntary_stars=1,
        stars_with_feedback=1,
        repeat_contacts=0,
        rows_with_feedback=1,
        rows=2,
    )


def test_summary_marks_stars_without_feedback_as_mixed(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    log = tmp_path / "outreach-mixed.csv"
    log.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,"
        "voluntary_star,outcome,feedback_signal,repeat_contact\n"
        "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,share report,"
        "1,accepted helpful report,,no\n",
        encoding="utf-8",
    )

    summary = module.summarize(log)
    assert summary["ethical_signal"] == "mixed"
    assert summary["stars_without_feedback"] == 1
    actions = module._next_growth_actions(summary)
    assert any("Follow up with each volunteer" in action for action in actions)


def test_outreach_main_handles_header_only_template(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-template.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,"
        "voluntary_star,outcome,feedback_signal,repeat_contact\n",
        encoding="utf-8",
    )

    argv_backup = sys.argv
    try:
        sys.argv = ["check-outreach.py", str(sample)]
        assert module.main() == 0
    finally:
        sys.argv = argv_backup


def test_outreach_main_strict_fails_when_signal_is_mixed(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-mixed.csv"
    sample.write_text(
        (
            "week,date,contact_channel,problem_area,conversation_stage,next_action,"
            "voluntary_star,outcome,feedback_signal,repeat_contact\n"
            "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,"
            "share report,1,accepted helpful report,,no\n"
        ),
        encoding="utf-8",
    )

    argv_backup = sys.argv
    try:
        sys.argv = [
            "check-outreach.py",
            str(sample),
            "--strict",
        ]
        assert module.main() == 1
    finally:
        sys.argv = argv_backup


def test_outreach_main_strict_passes_when_signal_is_strong(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-strong.csv"
    sample.write_text(
        (
            "week,date,contact_channel,problem_area,conversation_stage,next_action,"
            "voluntary_star,outcome,feedback_signal,repeat_contact\n"
            "2026-W31,2026-08-01,GitHub Issue,OIDC,interview completed,"
            "share report,1,accepted helpful report,asked for follow-up,no\n"
        ),
        encoding="utf-8",
    )

    argv_backup = sys.argv
    try:
        sys.argv = [
            "check-outreach.py",
            str(sample),
            "--strict",
        ]
        assert module.main() == 0
    finally:
        sys.argv = argv_backup


def test_outreach_next_growth_actions_are_included_for_blank_sample(tmp_path: Path) -> None:
    module = _load_script(Path(__file__).resolve().parent.parent)
    sample = tmp_path / "outreach-empty.csv"
    sample.write_text(
        "week,date,contact_channel,problem_area,conversation_stage,next_action,"
        "voluntary_star,outcome,feedback_signal,repeat_contact\n",
        encoding="utf-8",
    )
    summary = module.summarize(sample)
    actions = module._next_growth_actions(summary)
    assert isinstance(actions, list)
    assert actions
    assert any("seed the outreach tracker" in action.lower() for action in actions)
