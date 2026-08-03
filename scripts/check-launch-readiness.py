#!/usr/bin/env python3
"""Validate launch and release consistency before publishing a tag."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request
try:
    import tomllib  # type: ignore[unused-ignore]
except ModuleNotFoundError:  # pragma: no cover - Python <3.11
    tomllib = None


EXPECTED_TOPICS = {
    "aws",
    "aws-sam",
    "cloudformation",
    "github-actions",
    "iam",
    "python",
    "serverless",
    "cli",
}
EXPECTED_HOMEPAGE = "https://jakegold1647.github.io/sam-doctor/"


@dataclass
class _CheckResult:
    passed: int = 0
    failed: int = 0

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def report(self, label: str, passed: bool, detail: str) -> None:
        if passed:
            print(f"PASS: {label} - {detail}")
            self.passed += 1
        else:
            print(f"FAIL: {label} - {detail}")
            self.failed += 1


def _normalize_list(values: object) -> set[str]:
    if not isinstance(values, (list, tuple)):
        return set()
    return {str(value).strip().lower() for value in values if isinstance(value, str)}


def _normalize_url(value: object) -> str:
    return str(value or "").strip().rstrip("/")


def _get_json(url: str, token: str | None) -> tuple[Any, int]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "sam-doctor-launch-readiness",
        },
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8")), response.status


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_project_version_from_pyproject(pyproject: str) -> str | None:
    inside_project = False

    for raw_line in pyproject.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            inside_project = line[1:-1].strip() == "project"
            continue

        if not inside_project:
            continue

        if line.startswith("[") and line.endswith("]"):
            break

        if line.startswith("version"):
            key, _, value = line.partition("=")
            if key.strip() == "version":
                cleaned = value.split("#", 1)[0].strip()
                if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
                    return cleaned[1:-1]

    return None


def _version_from_pyproject(root: Path) -> str:
    pyproject = _read_text(root / "pyproject.toml")
    if tomllib is not None:
        data = tomllib.loads(pyproject)
        project = data.get("project", {})
        if "version" in project and isinstance(project["version"], str):
            return project["version"]

    version = _extract_project_version_from_pyproject(pyproject)
    if version is None:
        raise ValueError("Could not parse version from pyproject.toml")
    return version


def _version_from_init(root: Path) -> str:
    contents = _read_text(root / "src" / "sam_doctor" / "__init__.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', contents)
    if not match:
        raise ValueError("Could not parse __version__ from src/sam_doctor/__init__.py")
    return match.group(1)


def _changelog_has_version(root: Path, version: str) -> bool:
    lines = _read_text(root / "CHANGELOG.md").splitlines()
    return any(line.startswith(f"## v{version} - ") for line in lines)


def _release_note_is_appropriate(root: Path, repo: str, version: str, token: str | None) -> tuple[bool, str]:
    release_note = root / "launch" / f"RELEASE-v{version}.md"
    if not release_note.exists():
        return (
            False,
            f"launch/RELEASE-v{version}.md missing",
        )

    if "-" in version:
        return (
            True,
            f"release note exists for prerelease {version} (release-state checks deferred)",
        )

    if not token:
        return (
            True,
            "token unavailable, skipping pre-release validation for launch note release state",
        )

    try:
        payload, _ = _get_json(
            f"https://api.github.com/repos/{repo}/releases/tags/v{version}",
            token,
        )
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return (
                True,
                f"launch/RELEASE-v{version}.md present; release not published yet for this tag",
            )
        return (
            False,
            f"unable to verify release state for v{version} ({error.code} {error.reason})",
        )
    except (OSError, urllib.error.URLError) as error:
        return (
            False,
            f"unable to verify release state for v{version} ({error})",
        )

    if payload.get("draft"):
        return (
            False,
            f"GitHub release v{version} is still a draft; publish it before marketplace checks",
        )

    if payload.get("prerelease"):
        return (
            False,
            f"GitHub release v{version} is marked as prerelease; publish as stable first",
        )

    return (
        True,
        f"launch/RELEASE-v{version}.md present and GitHub release is stable",
    )


def _marketplace_metadata_ok(root: Path) -> bool:
    action_yaml = root / "action.yml"
    if not action_yaml.exists():
        return False
    text = action_yaml.read_text(encoding="utf-8")
    required_tokens = [
        "name:",
        "description:",
        "branding:",
        "runs:",
        "using: composite",
        "log-file:",
    ]
    return all(token in text for token in required_tokens)


def _launch_asset_checks(root: Path) -> tuple[bool, str]:
    index_page = root / "site" / "index.html"
    social_preview = root / "site" / "assets" / "sam-doctor-social-preview.jpg"
    details = (
        f"site/index.html {'present' if index_page.exists() else 'missing'}; "
        f"social preview {'present' if social_preview.exists() else 'missing'}"
    )
    return index_page.exists() and social_preview.exists(), details


def _github_metadata_ok(root: Path, repo: str, token: str | None) -> tuple[bool, str]:
    del root
    if not token:
        return True, "token unavailable, skipping remote launch metadata check"

    try:
        payload, _ = _get_json(f"https://api.github.com/repos/{repo}", token)
    except (OSError, urllib.error.HTTPError, urllib.error.URLError) as error:
        return (
            False,
            f"unable to verify remote launch metadata ({error})",
        )

    homepage_ok = _normalize_url(payload.get("homepage")) == _normalize_url(EXPECTED_HOMEPAGE)
    topics = _normalize_list(payload.get("topics"))
    missing_topics = sorted(EXPECTED_TOPICS - topics)

    if homepage_ok and not missing_topics:
        return (
            True,
            f"homepage and required topics match: {', '.join(sorted(EXPECTED_TOPICS))}",
        )

    details = [f"homepage={payload.get('homepage')!r}", f"topics={', '.join(sorted(topics)) if topics else 'missing'}"]
    if not homepage_ok:
        details.append(f"expected_homepage={EXPECTED_HOMEPAGE}")
    if missing_topics:
        details.append(f"missing_topics={', '.join(missing_topics)}")
    return False, "; ".join(details)


def _is_prerelease(version: str) -> bool:
    return "-" in version


def _run_checks_with_options(
    root: Path, repo: str, token: str | None
) -> _CheckResult:
    result = _CheckResult()
    pyproject_version = _version_from_pyproject(root)
    init_version = _version_from_init(root)
    is_prerelease = _is_prerelease(pyproject_version)

    result.report(
        "version consistency",
        pyproject_version == init_version,
        f"pyproject={pyproject_version}, __init__={init_version}",
    )
    launch_assets_ok, launch_assets_detail = _launch_asset_checks(root)
    result.report("launch assets", launch_assets_ok, launch_assets_detail)

    github_ok, github_detail = _github_metadata_ok(root, repo, token)
    result.report("github launch metadata", github_ok, github_detail)

    if is_prerelease:
        result.report(
            "prerelease release note",
            True,
            "release-note/changelog checks are optional until final stable release",
        )
        result.report(
            "marketplace action metadata",
            _marketplace_metadata_ok(root),
            f"required fields present in {root / 'action.yml'}",
        )
    else:
        release_ok, release_detail = _release_note_is_appropriate(
            root,
            repo,
            pyproject_version,
            token,
        )
        changelog_ok = _changelog_has_version(root, pyproject_version)
        result.report(
            "release note file",
            release_ok,
            release_detail,
        )
        result.report(
            "changelog entry",
            changelog_ok,
            f"CHANGELOG.md contains v{pyproject_version}",
        )
        result.report(
            "marketplace action metadata",
            _marketplace_metadata_ok(root),
            f"required fields present in {root / 'action.yml'}",
        )

    return result


def _run_checks(root: Path) -> _CheckResult:
    token = os.environ.get("GITHUB_TOKEN")
    return _run_checks_with_options(
        root,
        repo="jakegold1647/sam-doctor",
        token=token,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root passed for repeatable checks.",
    )
    parser.add_argument(
        "--repo",
        default="jakegold1647/sam-doctor",
        help="GitHub repository owner/name for remote launch metadata checks.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN", ""),
        help="GitHub API token for remote launch metadata checks.",
    )
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if not root.exists():
        print(f"root does not exist: {root}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"root is not a directory: {root}", file=sys.stderr)
        return 1

    token = args.token or os.environ.get("GITHUB_TOKEN")
    result = _run_checks_with_options(root, repo=args.repo, token=token)
    print(f"checks passed: {result.passed}, checks failed: {result.failed}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
