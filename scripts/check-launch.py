#!/usr/bin/env python3
"""Run launch-readiness, distribution, and outreach checks in one command."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _ensure_distinct_paths(named_paths: dict[str, str]) -> None:
    """Fail before writing when two declared files are path or inode aliases."""

    paths = [(name, Path(value)) for name, value in named_paths.items() if value]
    for index, (first_name, first_path) in enumerate(paths):
        for second_name, second_path in paths[index + 1 :]:
            try:
                aliases = first_path.resolve() == second_path.resolve()
                if not aliases and first_path.exists() and second_path.exists():
                    aliases = first_path.samefile(second_path)
            except (OSError, RuntimeError) as error:
                raise ValueError(f"Could not compare output paths: {error}") from error
            if aliases:
                raise ValueError(
                    f"{first_name} and {second_name} must resolve to distinct files."
                )


def _load_script(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_launch_readiness_module(repo_root: Path):
    return _load_script(repo_root / "scripts" / "check-launch-readiness.py")


def _load_distribution_module(repo_root: Path):
    return _load_script(repo_root / "scripts" / "check-distribution.py")


def _load_outreach_module(repo_root: Path):
    return _load_script(repo_root / "scripts" / "check-outreach.py")


def run_launch_readiness(
    repo_root: Path,
    repo: str,
    token: str | None,
    check_release_state: bool = True,
    loader: Callable[[Path], Any] = _load_launch_readiness_module,
) -> tuple[bool, int, int]:
    module = loader(repo_root)
    run_checks = getattr(module, "_run_checks_with_options", None)
    if callable(run_checks):
        result = run_checks(
            repo_root,
            repo=repo,
            token=token,
            check_release_state=check_release_state,
        )
    else:
        result = module._run_checks(repo_root)
    return bool(result.ok), int(result.passed), int(result.failed)


def run_distribution(
    repo_root: Path,
    repo: str,
    token: str | None,
    output_format: str = "text",
    output: str = "",
    append_csv: str = "",
    summary: str = "",
    print_trend: bool = False,
    strict: bool = False,
    loader: Callable[[Path], Any] = _load_distribution_module,
) -> bool:
    try:
        _ensure_distinct_paths(
            {
                "--output": output if output_format == "json" else "",
                "--append-csv": append_csv,
                "--summary": summary,
            }
        )
    except ValueError as error:
        print(f"distribution output error: {error}", file=sys.stderr)
        return False

    module = loader(repo_root)
    try:
        snapshot = module._collect_snapshot(repo, token)
    except RuntimeError as error:
        print(f"distribution snapshot unavailable: {error}")
        return False

    previous = None
    if print_trend or summary:
        if append_csv:
            previous = module._read_last_csv_row(append_csv)
        elif summary:
            previous_path = Path(summary).resolve().parent / "distribution.csv"
            previous = module._read_last_csv_row(previous_path.as_posix())

    if output_format == "json":
        print(module.json.dumps(snapshot, indent=2, sort_keys=True))
        if output:
            module._ensure_parent_directory(output)
            with open(output, "w", encoding="utf-8") as stream:
                module.json.dump(snapshot, stream, indent=2, sort_keys=True)
    if append_csv:
        module._append_csv(snapshot, append_csv)
    if summary:
        module._ensure_parent_directory(summary)
        module._write_summary(snapshot, previous, summary)
    if print_trend:
        if previous is None:
            print("trend: no previous snapshot yet, establishing baseline")
        else:
            print(f"trend: {module._trend_text(snapshot, previous)}")

    if strict:
        strict_check = getattr(module, "_strict_distribution_violations", None)
        if callable(strict_check):
            violations = strict_check(snapshot)
            if violations:
                print("distribution strict check: FAIL")
                for violation in violations:
                    print(f"- {violation}")
                return False

    if output_format != "json":
        print(f"sam-doctor distribution snapshot for {snapshot['repo']}")
        print(f"repo_stars: {snapshot['repo_stars']}")
        print(f"forks: {snapshot['forks']}")
        print(f"open_issues: {snapshot['open_issues']}")
        print(f"watchers: {snapshot['watchers']}")
        print(f"releases: {snapshot['releases']}")
        print(f"discussions_ping: {snapshot['discussions_ping']}")
        pypi_status = snapshot["pypi_status"]
        marketplace_status = snapshot["marketplace_status"]
        site_status = snapshot["site_status"]
        print(f"pypi_status: 200={pypi_status['ok']} ({pypi_status['details']})")
        print(
            "marketplace_status: 200="
            f"{marketplace_status['ok']} ({marketplace_status['details']})"
        )
        print(f"site_status: 200={site_status['ok']} ({site_status['details']})")

    return True


def run_outreach(
    repo_root: Path,
    outreach_log: str,
    strict: bool = False,
    summary: str = "",
    min_feedback_ratio: float = 100.0,
    loader: Callable[[Path], Any] = _load_outreach_module,
) -> bool:
    try:
        _ensure_distinct_paths(
            {"outreach log": outreach_log, "outreach summary": summary}
        )
    except ValueError as error:
        print(f"outreach output error: {error}", file=sys.stderr)
        return False

    module = loader(repo_root)
    path = Path(outreach_log)
    if not path.exists():
        print(f"outreach log not found: {path}")
        print(
            f"Create a local tracker with: python scripts/bootstrap-outreach-log.py {path}"
        )
        if summary:
            module._write_summary(module.empty_summary(), summary)
        return not strict

    outreach_summary = module.summarize(path)
    module._print_summary(outreach_summary)
    if summary:
        module._write_summary(outreach_summary, summary)

    if strict:
        passes_strict = getattr(module, "_passes_strict_ethical_policy", None)
        if callable(passes_strict):
            strict_ok, strict_reason = passes_strict(outreach_summary, min_feedback_ratio)
            if not strict_ok:
                print(strict_reason)
                recommendation = getattr(module, "_ethical_recommendation", None)
                if callable(recommendation):
                    print(f"recommendation: {recommendation(outreach_summary)}")
                return False
        else:
            if outreach_summary["ethical_signal"] != "strong":
                print(f"ethical_signal is {outreach_summary['ethical_signal']}, not strong")
                return False

            feedback_ratio = float(outreach_summary["star_feedback_ratio"])
            if feedback_ratio < min_feedback_ratio:
                print(
                    f"ethical star feedback ratio is {feedback_ratio:.1f}%, "
                    f"below strict threshold {min_feedback_ratio:.1f}%"
                )
                return False
    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run launch checks for a publish attempt.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root to validate.",
    )
    parser.add_argument(
        "--repo",
        default="jakegold1647/sam-doctor",
        help="GitHub repository owner/name for distribution check.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub token for distribution/check calls.",
    )
    parser.add_argument(
        "--check-launch-token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub token for launch metadata checks.",
    )
    parser.add_argument(
        "--skip-release-state",
        action="store_true",
        help="Skip the remote stable/prerelease state check (use for scheduled monitoring).",
    )
    parser.add_argument(
        "--launch-repo",
        default="jakegold1647/sam-doctor",
        help="GitHub repository owner/name for launch metadata checks.",
    )
    parser.add_argument("--skip-distribution", action="store_true", help="Skip distribution snapshot.")
    parser.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
        help="Distribution output format.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for distribution JSON.",
    )
    parser.add_argument(
        "--append-csv",
        default="notes/distribution.csv",
        help="Append distribution rows to CSV path (local, outside repo by default).",
    )
    parser.add_argument(
        "--summary",
        default="notes/distribution-summary.md",
        help="Write distribution summary file (local, outside repo by default).",
    )
    parser.add_argument(
        "--print-trend",
        action="store_true",
        help="Print distribution trend lines.",
    )
    parser.add_argument(
        "--strict-distribution",
        action="store_true",
        help="Fail launch check when distribution channels or launch setup signals are not ready.",
    )
    parser.add_argument(
        "--outreach-log",
        default="notes/sam-doctor-outreach-log.csv",
        help=(
            "Outreach log CSV for ethical check "
            "(local working copy only; default path is outside the repository)."
        ),
    )
    parser.add_argument(
        "--outreach-summary",
        default="notes/sam-doctor-outreach-summary.md",
        help=(
            "Optional output path for outreach summary markdown "
            "(local working copy only; default is outside the repository)."
        ),
    )
    parser.add_argument(
        "--skip-outreach",
        action="store_true",
        help="Skip outreach signal check.",
    )
    parser.add_argument(
        "--strict-ethical",
        action="store_true",
        help="Fail if outreach ethical signal is not strong.",
    )
    parser.add_argument(
        "--strict-distribution-during-release",
        action="store_true",
        help=(
            "Apply distribution strict checks after release channels are expected to be "
            "live (PyPI/sources, Marketplace listing, site/docs readiness)."
        ),
    )
    parser.add_argument(
        "--min-feedback-ratio",
        type=float,
        default=100.0,
        help="Strict outreach minimum star feedback ratio when --strict-ethical is used.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo_root)
    ok = True

    active_paths: dict[str, str] = {}
    if not args.skip_distribution:
        active_paths.update(
            {
                "--output": args.output if args.output_format == "json" else "",
                "--append-csv": args.append_csv,
                "--summary": args.summary,
            }
        )
    if not args.skip_outreach:
        active_paths.update(
            {
                "--outreach-log": args.outreach_log,
                "--outreach-summary": args.outreach_summary,
            }
        )
    try:
        _ensure_distinct_paths(active_paths)
    except ValueError as error:
        print(f"launch output error: {error}", file=sys.stderr)
        return 2

    launch_token = args.check_launch_token or args.token or None
    launch_ok, launch_passed, launch_failed = run_launch_readiness(
        repo_root,
        repo=args.launch_repo,
        token=launch_token,
        check_release_state=not args.skip_release_state,
    )
    if not launch_ok:
        ok = False
    print(f"launch-readiness checks: {launch_passed} passed, {launch_failed} failed")

    if not args.skip_distribution:
        token = args.token or None
        strict_distribution = args.strict_distribution or args.strict_distribution_during_release
        distribution_ok = run_distribution(
            repo_root,
            repo=args.repo,
            token=token,
            output_format=args.output_format,
            output=args.output,
            append_csv=args.append_csv,
            summary=args.summary,
            print_trend=args.print_trend,
            strict=strict_distribution,
        )
        if not distribution_ok:
            ok = False

    if (
        not args.skip_outreach
        and not run_outreach(
            repo_root,
            args.outreach_log,
            strict=args.strict_ethical,
            summary=args.outreach_summary,
            min_feedback_ratio=args.min_feedback_ratio,
        )
    ):
        ok = False

    if ok:
        print("launch check: PASS")
        return 0
    print("launch check: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
