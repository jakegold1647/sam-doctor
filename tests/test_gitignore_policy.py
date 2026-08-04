from pathlib import Path


def test_gitignore_blocks_growth_and_launch_notes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    text = (repo_root / ".gitignore").read_text(encoding="utf-8")

    required_entries = [
        "notes/",
        "artifacts/",
        "launch/outreach-log-template.csv",
        "launch/DISTRIBUTION-TRACKING.md",
        "launch/LAUNCH-PLAN.md",
        "launch/OUTREACH.md",
    ]

    for entry in required_entries:
        assert (
            entry in text
        ), f".gitignore should include {entry} to keep operational notes out of git."
