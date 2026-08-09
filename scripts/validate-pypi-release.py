"""Fail-closed validation for SAM Doctor PyPI release artifacts.

The release workflow runs ``validate`` before entering the protected PyPI
environment, then runs ``recheck`` after approval.  Both modes resolve the
stable tag, inspect the GitHub release, download its immutable asset IDs, and
verify the bytes and package metadata without executing release content.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - workflow runners use Python 3.11+
    tomllib = None  # type: ignore[assignment]


API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
PROJECT_NAME = "sam-doctor"
DIST_NAME = "sam_doctor"
MAX_JSON_BYTES = 10 * 1024 * 1024
MAX_ASSET_BYTES = 100 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
MAX_TAG_PEELS = 5

STABLE_TAG_RE = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ValidationError(RuntimeError):
    """A release failed a deterministic publishing invariant."""


@dataclass(frozen=True)
class ReleaseAsset:
    """Immutable identity and expected bytes for one release artifact."""

    asset_id: int
    name: str
    digest: str
    size: int


@dataclass(frozen=True)
class ReleaseSnapshot:
    """All release state that must remain unchanged through approval."""

    repository: str
    tag: str
    version: str
    tag_commit: str
    wheel: ReleaseAsset
    sdist: ReleaseAsset


class GitHubClient:
    """Small stdlib-only client for the GitHub endpoints used here."""

    def __init__(self, repository: str, token: str) -> None:
        _validate_repository(repository)
        if not token:
            raise ValidationError("GITHUB_TOKEN is required")
        self.repository = repository
        self._token = token
        self._opener = urllib.request.build_opener()

    def _request(self, path: str, accept: str) -> Any:
        request = urllib.request.Request(
            f"{API_ROOT}{path}",
            headers={
                "Accept": accept,
                "User-Agent": "sam-doctor-release-validator",
                "X-GitHub-Api-Version": API_VERSION,
            },
        )
        # urllib does not copy unredirected headers to a redirect request.
        # Asset downloads therefore do not expose the repository token to
        # GitHub's signed object-storage redirect target.
        request.add_unredirected_header("Authorization", f"Bearer {self._token}")
        try:
            return self._opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            raise ValidationError(
                f"GitHub API returned HTTP {exc.code} for {path}"
            ) from exc
        except urllib.error.URLError as exc:
            raise ValidationError(f"GitHub API request failed for {path}") from exc

    def get_json(self, path: str) -> Mapping[str, Any]:
        with self._request(path, "application/vnd.github+json") as response:
            payload = response.read(MAX_JSON_BYTES + 1)
        if len(payload) > MAX_JSON_BYTES:
            raise ValidationError(f"GitHub API response was too large for {path}")
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError(f"GitHub API returned invalid JSON for {path}") from exc
        if not isinstance(decoded, dict):
            raise ValidationError(f"GitHub API returned a non-object for {path}")
        return decoded

    def download_asset(
        self, asset_id: int, destination: Path, expected_size: int
    ) -> tuple[str, int]:
        path = f"/repos/{self.repository}/releases/assets/{asset_id}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        byte_count = 0
        temporary_name: str | None = None

        try:
            with self._request(
                path, "application/octet-stream"
            ) as response, tempfile.NamedTemporaryFile(
                mode="wb", dir=destination.parent, delete=False
            ) as temporary:
                temporary_name = temporary.name
                while chunk := response.read(1024 * 1024):
                    byte_count += len(chunk)
                    if byte_count > expected_size or byte_count > MAX_ASSET_BYTES:
                        raise ValidationError(
                            f"asset {asset_id} exceeded its declared size"
                        )
                    digest.update(chunk)
                    temporary.write(chunk)

            if byte_count != expected_size:
                raise ValidationError(
                    f"asset {asset_id} size changed: expected {expected_size}, "
                    f"downloaded {byte_count}"
                )
            os.replace(temporary_name, destination)
            temporary_name = None
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

        return digest.hexdigest(), byte_count


def _validate_repository(repository: str) -> None:
    if REPOSITORY_RE.fullmatch(repository) is None:
        raise ValidationError("repository must have the form owner/name")


def _version_from_tag(tag: str) -> str:
    match = STABLE_TAG_RE.fullmatch(tag)
    if match is None:
        raise ValidationError(
            "release tag must be a stable vMAJOR.MINOR.PATCH tag without "
            "prerelease text or leading zeroes"
        )
    return tag[1:]


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA_RE.fullmatch(value) is None:
        raise ValidationError(f"{label} must be a 40-character lowercase commit SHA")
    return value


def _repo_path(repository: str, suffix: str) -> str:
    owner, name = repository.split("/", 1)
    return (
        f"/repos/{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(name, safe='')}{suffix}"
    )


def _resolve_tag_commit(client: GitHubClient, repository: str, tag: str) -> str:
    encoded_tag = urllib.parse.quote(tag, safe="")
    reference = client.get_json(
        _repo_path(repository, f"/git/ref/tags/{encoded_tag}")
    )
    target = reference.get("object")
    if not isinstance(target, dict):
        raise ValidationError("tag reference did not contain an object")

    seen: set[str] = set()
    for _ in range(MAX_TAG_PEELS + 1):
        object_type = target.get("type")
        sha = _require_sha(target.get("sha"), "tag target")
        if object_type == "commit":
            return sha
        if object_type != "tag":
            raise ValidationError(f"tag resolved to unsupported object type {object_type!r}")
        if sha in seen:
            raise ValidationError("annotated tag chain contains a cycle")
        seen.add(sha)
        tag_object = client.get_json(_repo_path(repository, f"/git/tags/{sha}"))
        target = tag_object.get("object")
        if not isinstance(target, dict):
            raise ValidationError("annotated tag did not contain a target object")

    raise ValidationError(f"annotated tag chain exceeded {MAX_TAG_PEELS} objects")


def _validate_release_record(
    client: GitHubClient, repository: str, tag: str
) -> Mapping[str, Any]:
    encoded_tag = urllib.parse.quote(tag, safe="")
    release = client.get_json(_repo_path(repository, f"/releases/tags/{encoded_tag}"))
    if release.get("tag_name") != tag:
        raise ValidationError("GitHub release tag does not exactly match the requested tag")
    if release.get("draft") is not False:
        raise ValidationError("GitHub release must not be a draft")
    if release.get("prerelease") is not False:
        raise ValidationError("GitHub release must not be a prerelease")
    if not isinstance(release.get("published_at"), str) or not release["published_at"]:
        raise ValidationError("GitHub release must have a publication timestamp")
    return release


def _project_metadata(
    client: GitHubClient, repository: str, commit: str
) -> tuple[str, str]:
    if tomllib is None:
        raise ValidationError("release validation requires Python 3.11 or newer")
    contents = client.get_json(
        _repo_path(repository, f"/contents/pyproject.toml?ref={commit}")
    )
    if contents.get("type") != "file" or contents.get("encoding") != "base64":
        raise ValidationError("pyproject.toml response was not a base64 file")
    encoded = contents.get("content")
    if not isinstance(encoded, str):
        raise ValidationError("pyproject.toml response did not contain file content")
    try:
        raw = base64.b64decode(encoded, validate=False)
        parsed = tomllib.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("pyproject.toml at the tag commit was invalid") from exc
    project = parsed.get("project")
    if not isinstance(project, dict):
        raise ValidationError("pyproject.toml did not contain a project table")
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValidationError("pyproject.toml project name and version must be strings")
    return name, version


def _parse_asset(raw: object, expected_name: str) -> ReleaseAsset:
    if not isinstance(raw, dict):
        raise ValidationError("GitHub release contained an invalid asset record")
    if raw.get("name") != expected_name:
        raise ValidationError(f"expected release asset {expected_name!r}")
    asset_id = raw.get("id")
    size = raw.get("size")
    digest = raw.get("digest")
    if isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id <= 0:
        raise ValidationError(f"release asset {expected_name!r} has an invalid ID")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValidationError(f"release asset {expected_name!r} must not be empty")
    if size > MAX_ASSET_BYTES:
        raise ValidationError(f"release asset {expected_name!r} is unexpectedly large")
    if raw.get("state") != "uploaded":
        raise ValidationError(f"release asset {expected_name!r} is not fully uploaded")
    if not isinstance(digest, str) or DIGEST_RE.fullmatch(digest) is None:
        raise ValidationError(
            f"release asset {expected_name!r} needs a lowercase SHA-256 digest"
        )
    return ReleaseAsset(asset_id=asset_id, name=expected_name, digest=digest, size=size)


def _release_assets(
    release: Mapping[str, Any], version: str
) -> tuple[ReleaseAsset, ReleaseAsset]:
    wheel_name = f"{DIST_NAME}-{version}-py3-none-any.whl"
    sdist_name = f"{DIST_NAME}-{version}.tar.gz"
    raw_assets = release.get("assets")
    if not isinstance(raw_assets, list) or len(raw_assets) != 2:
        raise ValidationError(
            "GitHub release must contain exactly the expected wheel and source archive"
        )
    by_name: dict[str, object] = {}
    for raw in raw_assets:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
            raise ValidationError("GitHub release contained an invalid asset name")
        name = raw["name"]
        if name in by_name:
            raise ValidationError(f"GitHub release contains duplicate asset {name!r}")
        by_name[name] = raw
    if set(by_name) != {wheel_name, sdist_name}:
        raise ValidationError(
            "GitHub release must contain exactly the expected wheel and source archive"
        )
    return (
        _parse_asset(by_name[wheel_name], wheel_name),
        _parse_asset(by_name[sdist_name], sdist_name),
    )


def _read_package_metadata(payload: bytes, source: str) -> None:
    message = BytesParser(policy=policy.default).parsebytes(payload)
    for header, expected in (("Name", PROJECT_NAME), ("Version", source)):
        values = message.get_all(header, [])
        if len(values) != 1 or str(values[0]) != expected:
            raise ValidationError(
                f"package metadata must contain exactly one {header}: {expected} header"
            )


def _verify_wheel(path: Path, version: str) -> None:
    metadata_name = f"{DIST_NAME}-{version}.dist-info/METADATA"
    try:
        with zipfile.ZipFile(path) as wheel:
            if wheel.namelist().count(metadata_name) != 1:
                raise ValidationError(
                    f"wheel must contain exactly one {metadata_name} file"
                )
            metadata_info = wheel.getinfo(metadata_name)
            if metadata_info.file_size > MAX_METADATA_BYTES:
                raise ValidationError("wheel metadata is unexpectedly large")
            metadata = wheel.read(metadata_info)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise ValidationError("wheel is not a readable ZIP archive") from exc
    _read_package_metadata(metadata, version)


def _verify_sdist(path: Path, version: str) -> None:
    metadata_name = f"{DIST_NAME}-{version}/PKG-INFO"
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            matching = [member for member in archive if member.name == metadata_name]
            if len(matching) != 1 or not matching[0].isfile():
                raise ValidationError(
                    f"source archive must contain exactly one regular {metadata_name} file"
                )
            if matching[0].size > MAX_METADATA_BYTES:
                raise ValidationError("source archive metadata is unexpectedly large")
            extracted = archive.extractfile(matching[0])
            if extracted is None:
                raise ValidationError("source archive metadata could not be read")
            metadata = extracted.read(MAX_METADATA_BYTES + 1)
    except (OSError, tarfile.TarError) as exc:
        raise ValidationError("source archive is not a readable gzip tar archive") from exc
    if len(metadata) > MAX_METADATA_BYTES:
        raise ValidationError("source archive metadata is unexpectedly large")
    _read_package_metadata(metadata, version)


def _download_and_verify(
    client: GitHubClient, snapshot: ReleaseSnapshot, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for asset, verifier in (
        (snapshot.wheel, _verify_wheel),
        (snapshot.sdist, _verify_sdist),
    ):
        destination = output_dir / asset.name
        downloaded_digest, downloaded_size = client.download_asset(
            asset.asset_id, destination, asset.size
        )
        if downloaded_size != asset.size:
            raise ValidationError(f"downloaded size changed for {asset.name!r}")
        if f"sha256:{downloaded_digest}" != asset.digest:
            raise ValidationError(f"SHA-256 digest changed for {asset.name!r}")
        verifier(destination, snapshot.version)


def inspect_release(
    client: GitHubClient, repository: str, tag: str
) -> ReleaseSnapshot:
    """Resolve and validate all remote metadata without trusting tag contents."""

    _validate_repository(repository)
    version = _version_from_tag(tag)
    tag_commit = _resolve_tag_commit(client, repository, tag)
    release = _validate_release_record(client, repository, tag)
    project_name, project_version = _project_metadata(client, repository, tag_commit)
    if project_name != PROJECT_NAME:
        raise ValidationError(
            f"tagged project name is {project_name!r}, expected {PROJECT_NAME!r}"
        )
    if project_version != version:
        raise ValidationError(
            f"tag {tag!r} names version {version!r}, but pyproject.toml contains "
            f"{project_version!r}"
        )
    wheel, sdist = _release_assets(release, version)
    return ReleaseSnapshot(
        repository=repository,
        tag=tag,
        version=version,
        tag_commit=tag_commit,
        wheel=wheel,
        sdist=sdist,
    )


def validate_release(
    client: GitHubClient,
    repository: str,
    tag: str,
    output_dir: Path,
) -> ReleaseSnapshot:
    """Validate and download a stable release before environment approval."""

    snapshot = inspect_release(client, repository, tag)
    _download_and_verify(client, snapshot, output_dir)
    return snapshot


def recheck_release(
    client: GitHubClient,
    expected: ReleaseSnapshot,
    output_dir: Path,
) -> ReleaseSnapshot:
    """Re-resolve the release and re-download the same assets after approval."""

    current = inspect_release(client, expected.repository, expected.tag)
    if current != expected:
        raise ValidationError(
            "release tag, commit, asset IDs, sizes, names, or digests changed "
            "while publication awaited approval"
        )
    _download_and_verify(client, current, output_dir)
    return current


def _asset_from_arguments(
    kind: str, asset_id: int, name: str, digest: str, size: int
) -> ReleaseAsset:
    if kind not in {"wheel", "sdist"}:  # pragma: no cover - internal invariant
        raise AssertionError(kind)
    if isinstance(asset_id, bool) or asset_id <= 0:
        raise ValidationError(f"expected {kind} asset ID is invalid")
    if not name or Path(name).name != name:
        raise ValidationError(f"expected {kind} asset name is invalid")
    if DIGEST_RE.fullmatch(digest) is None:
        raise ValidationError(f"expected {kind} digest is invalid")
    if size <= 0 or size > MAX_ASSET_BYTES:
        raise ValidationError(f"expected {kind} size is invalid")
    return ReleaseAsset(asset_id=asset_id, name=name, digest=digest, size=size)


def _write_github_outputs(
    path: Path, snapshot: ReleaseSnapshot, trusted_commit: str, validator_path: Path
) -> None:
    trusted_commit = _require_sha(trusted_commit, "trusted default-branch commit")
    validator_digest = hashlib.sha256(validator_path.read_bytes()).hexdigest()
    outputs = {
        "tag": snapshot.tag,
        "version": snapshot.version,
        "tag_commit": snapshot.tag_commit,
        "trusted_commit": trusted_commit,
        "validator_sha256": validator_digest,
        "wheel_asset_id": str(snapshot.wheel.asset_id),
        "wheel_name": snapshot.wheel.name,
        "wheel_digest": snapshot.wheel.digest,
        "wheel_size": str(snapshot.wheel.size),
        "sdist_asset_id": str(snapshot.sdist.asset_id),
        "sdist_name": snapshot.sdist.name,
        "sdist_digest": snapshot.sdist.digest,
        "sdist_size": str(snapshot.sdist.size),
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def _token_from_environment() -> str:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="validate a stable release before environment approval"
    )
    validate.add_argument("--repository", required=True)
    validate.add_argument("--tag", required=True)
    validate.add_argument("--trusted-commit", required=True)
    validate.add_argument("--output-dir", required=True, type=Path)
    validate.add_argument("--github-output", required=True, type=Path)

    recheck = subparsers.add_parser(
        "recheck", help="recheck immutable release state after environment approval"
    )
    recheck.add_argument("--repository", required=True)
    recheck.add_argument("--tag", required=True)
    recheck.add_argument("--version", required=True)
    recheck.add_argument("--tag-commit", required=True)
    recheck.add_argument("--wheel-asset-id", required=True, type=int)
    recheck.add_argument("--wheel-name", required=True)
    recheck.add_argument("--wheel-digest", required=True)
    recheck.add_argument("--wheel-size", required=True, type=int)
    recheck.add_argument("--sdist-asset-id", required=True, type=int)
    recheck.add_argument("--sdist-name", required=True)
    recheck.add_argument("--sdist-digest", required=True)
    recheck.add_argument("--sdist-size", required=True, type=int)
    recheck.add_argument("--output-dir", required=True, type=Path)
    return parser


def _expected_snapshot(arguments: argparse.Namespace) -> ReleaseSnapshot:
    _validate_repository(arguments.repository)
    version = _version_from_tag(arguments.tag)
    if arguments.version != version:
        raise ValidationError("expected version does not match the stable tag")
    tag_commit = _require_sha(arguments.tag_commit, "expected tag commit")
    wheel = _asset_from_arguments(
        "wheel",
        arguments.wheel_asset_id,
        arguments.wheel_name,
        arguments.wheel_digest,
        arguments.wheel_size,
    )
    sdist = _asset_from_arguments(
        "sdist",
        arguments.sdist_asset_id,
        arguments.sdist_name,
        arguments.sdist_digest,
        arguments.sdist_size,
    )
    expected_names = {
        f"{DIST_NAME}-{version}-py3-none-any.whl",
        f"{DIST_NAME}-{version}.tar.gz",
    }
    if {wheel.name, sdist.name} != expected_names:
        raise ValidationError("expected asset names do not match the stable version")
    return ReleaseSnapshot(
        repository=arguments.repository,
        tag=arguments.tag,
        version=version,
        tag_commit=tag_commit,
        wheel=wheel,
        sdist=sdist,
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        client = GitHubClient(arguments.repository, _token_from_environment())
        if arguments.command == "validate":
            _require_sha(arguments.trusted_commit, "trusted default-branch commit")
            snapshot = validate_release(
                client, arguments.repository, arguments.tag, arguments.output_dir
            )
            _write_github_outputs(
                arguments.github_output,
                snapshot,
                arguments.trusted_commit,
                Path(__file__),
            )
        else:
            expected = _expected_snapshot(arguments)
            recheck_release(client, expected, arguments.output_dir)
    except (OSError, ValidationError) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
