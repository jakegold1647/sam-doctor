import base64
import copy
import gzip
import hashlib
import importlib.util
import io
import sys
import tarfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-pypi-release.py"
REPOSITORY = "jakegold1647/sam-doctor"
BASE = f"/repos/{REPOSITORY}"
TAG = "v1.2.3"
VERSION = "1.2.3"
COMMIT = "c" * 40
TRUSTED_COMMIT = "d" * 40
WHEEL_ID = 101
SDIST_ID = 202


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_pypi_release", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()
pytestmark = pytest.mark.skipif(
    VALIDATOR.tomllib is None,
    reason="the release workflow validator runs with Python 3.11 or newer",
)


class FakeGitHubClient:
    def __init__(
        self, responses: dict[str, dict[str, object]], downloads: dict[int, bytes]
    ) -> None:
        self.responses = responses
        self.downloads = downloads
        self.download_calls: list[int] = []

    def get_json(self, path: str) -> Mapping[str, object]:
        try:
            return self.responses[path]
        except KeyError as exc:
            raise VALIDATOR.ValidationError(f"missing fake response for {path}") from exc

    def download_asset(
        self, asset_id: int, destination: Path, expected_size: int
    ) -> tuple[str, int]:
        del expected_size
        self.download_calls.append(asset_id)
        try:
            payload = self.downloads[asset_id]
        except KeyError as exc:
            raise VALIDATOR.ValidationError(
                f"missing fake download for asset {asset_id}"
            ) from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest(), len(payload)


@dataclass
class ReleaseFixture:
    client: FakeGitHubClient
    release: dict[str, object]
    project_contents: dict[str, object]


def _metadata(name: str = "sam-doctor", version: str = VERSION) -> bytes:
    return (
        "Metadata-Version: 2.1\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        "Summary: release validator fixture\n\n"
    ).encode()


def _wheel_bytes(name: str = "sam-doctor", version: str = VERSION) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, mode="w") as archive:
        archive.writestr(
            f"sam_doctor-{VERSION}.dist-info/METADATA", _metadata(name, version)
        )
    return payload.getvalue()


def _sdist_bytes(name: str = "sam-doctor", version: str = VERSION) -> bytes:
    tar_payload = io.BytesIO()
    metadata = _metadata(name, version)
    with tarfile.open(fileobj=tar_payload, mode="w") as archive:
        info = tarfile.TarInfo(f"sam_doctor-{VERSION}/PKG-INFO")
        info.size = len(metadata)
        info.mtime = 0
        archive.addfile(info, io.BytesIO(metadata))
    return gzip.compress(tar_payload.getvalue(), mtime=0)


def _asset(asset_id: int, name: str, payload: bytes) -> dict[str, object]:
    return {
        "id": asset_id,
        "name": name,
        "state": "uploaded",
        "size": len(payload),
        "digest": f"sha256:{hashlib.sha256(payload).hexdigest()}",
    }


def _release_fixture(*, annotated: bool = False) -> ReleaseFixture:
    wheel = _wheel_bytes()
    sdist = _sdist_bytes()
    wheel_name = f"sam_doctor-{VERSION}-py3-none-any.whl"
    sdist_name = f"sam_doctor-{VERSION}.tar.gz"
    release = {
        "tag_name": TAG,
        "draft": False,
        "prerelease": False,
        "published_at": "2026-08-09T12:00:00Z",
        "assets": [
            _asset(WHEEL_ID, wheel_name, wheel),
            _asset(SDIST_ID, sdist_name, sdist),
        ],
    }
    pyproject = b'[project]\nname = "sam-doctor"\nversion = "1.2.3"\n'
    project_contents = {
        "type": "file",
        "encoding": "base64",
        "content": base64.b64encode(pyproject).decode(),
    }
    if annotated:
        outer_tag = "a" * 40
        inner_tag = "b" * 40
        tag_target = {"type": "tag", "sha": outer_tag}
        extra_responses = {
            f"{BASE}/git/tags/{outer_tag}": {
                "object": {"type": "tag", "sha": inner_tag}
            },
            f"{BASE}/git/tags/{inner_tag}": {
                "object": {"type": "commit", "sha": COMMIT}
            },
        }
    else:
        tag_target = {"type": "commit", "sha": COMMIT}
        extra_responses = {}
    responses = {
        f"{BASE}/git/ref/tags/{TAG}": {"object": tag_target},
        f"{BASE}/releases/tags/{TAG}": release,
        f"{BASE}/contents/pyproject.toml?ref={COMMIT}": project_contents,
        **extra_responses,
    }
    return ReleaseFixture(
        client=FakeGitHubClient(
            responses=responses,
            downloads={WHEEL_ID: wheel, SDIST_ID: sdist},
        ),
        release=release,
        project_contents=project_contents,
    )


def _replace_asset_payload(
    fixture: ReleaseFixture, asset_index: int, payload: bytes
) -> None:
    raw_asset = fixture.release["assets"][asset_index]
    raw_asset["size"] = len(payload)
    raw_asset["digest"] = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    fixture.client.downloads[raw_asset["id"]] = payload


def test_accepts_lightweight_stable_tag_and_verifies_both_packages(
    tmp_path: Path,
) -> None:
    fixture = _release_fixture()

    snapshot = VALIDATOR.validate_release(
        fixture.client, REPOSITORY, TAG, tmp_path / "dist"
    )

    assert snapshot.tag_commit == COMMIT
    assert snapshot.version == VERSION
    assert fixture.client.download_calls == [WHEEL_ID, SDIST_ID]
    assert sorted(path.name for path in (tmp_path / "dist").iterdir()) == [
        f"sam_doctor-{VERSION}-py3-none-any.whl",
        f"sam_doctor-{VERSION}.tar.gz",
    ]


def test_accepts_and_fully_peels_annotated_stable_tag(tmp_path: Path) -> None:
    fixture = _release_fixture(annotated=True)

    snapshot = VALIDATOR.validate_release(
        fixture.client, REPOSITORY, TAG, tmp_path / "dist"
    )

    assert snapshot.tag_commit == COMMIT


@pytest.mark.parametrize(
    "tag",
    [
        "main",
        "c" * 40,
        "1.2.3",
        "v01.2.3",
        "v1.02.3",
        "v1.2.03",
        "v1.2.3-rc1",
        "v1.2",
        "v1.2.3\nmalicious=true",
    ],
)
def test_rejects_noncanonical_or_unstable_tags(tag: str) -> None:
    with pytest.raises(VALIDATOR.ValidationError, match="stable vMAJOR"):
        VALIDATOR._version_from_tag(tag)


def test_rejects_missing_tag_reference(tmp_path: Path) -> None:
    fixture = _release_fixture()
    del fixture.client.responses[f"{BASE}/git/ref/tags/{TAG}"]

    with pytest.raises(VALIDATOR.ValidationError, match="missing fake response"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tag_name", "v1.2.4", "does not exactly match"),
        ("draft", True, "must not be a draft"),
        ("prerelease", True, "must not be a prerelease"),
        ("published_at", None, "publication timestamp"),
        ("published_at", "", "publication timestamp"),
    ],
)
def test_rejects_invalid_release_state(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    fixture = _release_fixture()
    fixture.release[field] = value

    with pytest.raises(VALIDATOR.ValidationError, match=message):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_rejects_tag_and_pyproject_version_mismatch(tmp_path: Path) -> None:
    fixture = _release_fixture()
    mismatched = b'[project]\nname = "sam-doctor"\nversion = "1.2.4"\n'
    fixture.project_contents["content"] = base64.b64encode(mismatched).decode()

    with pytest.raises(VALIDATOR.ValidationError, match="pyproject.toml contains"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_rejects_wrong_tagged_project_name(tmp_path: Path) -> None:
    fixture = _release_fixture()
    mismatched = b'[project]\nname = "other"\nversion = "1.2.3"\n'
    fixture.project_contents["content"] = base64.b64encode(mismatched).decode()

    with pytest.raises(VALIDATOR.ValidationError, match="tagged project name"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


@pytest.mark.parametrize("layout", ["missing", "duplicate", "renamed", "extra"])
def test_requires_exactly_the_two_canonical_assets(
    tmp_path: Path, layout: str
) -> None:
    fixture = _release_fixture()
    assets = fixture.release["assets"]
    if layout == "missing":
        del assets[1]
    elif layout == "duplicate":
        assets[1]["name"] = assets[0]["name"]
    elif layout == "renamed":
        assets[1]["name"] = "renamed.tar.gz"
    else:
        assets.append(copy.deepcopy(assets[1]))
        assets[2]["id"] = 303

    with pytest.raises(VALIDATOR.ValidationError, match="asset|wheel and source"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", 0, "invalid ID"),
        ("id", True, "invalid ID"),
        ("size", 0, "must not be empty"),
        ("state", "new", "not fully uploaded"),
        ("digest", None, "SHA-256 digest"),
        ("digest", "sha256:" + "A" * 64, "SHA-256 digest"),
    ],
)
def test_rejects_unusable_asset_identity_or_digest(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    fixture = _release_fixture()
    fixture.release["assets"][0][field] = value

    with pytest.raises(VALIDATOR.ValidationError, match=message):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_rejects_download_whose_digest_differs_from_github_record(
    tmp_path: Path,
) -> None:
    fixture = _release_fixture()
    corrupted = bytearray(fixture.client.downloads[WHEEL_ID])
    corrupted[-1] ^= 1
    fixture.client.downloads[WHEEL_ID] = bytes(corrupted)

    with pytest.raises(VALIDATOR.ValidationError, match="SHA-256 digest changed"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_rejects_download_whose_size_differs_from_github_record(
    tmp_path: Path,
) -> None:
    fixture = _release_fixture()
    fixture.client.downloads[WHEEL_ID] += b"x"

    with pytest.raises(VALIDATOR.ValidationError, match="downloaded size changed"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_rejects_wheel_with_wrong_embedded_project_name(tmp_path: Path) -> None:
    fixture = _release_fixture()
    _replace_asset_payload(fixture, 0, _wheel_bytes(name="other"))

    with pytest.raises(VALIDATOR.ValidationError, match="Name: sam-doctor"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_rejects_sdist_with_wrong_embedded_version(tmp_path: Path) -> None:
    fixture = _release_fixture()
    _replace_asset_payload(fixture, 1, _sdist_bytes(version="1.2.4"))

    with pytest.raises(VALIDATOR.ValidationError, match="Version: 1.2.3"):
        VALIDATOR.validate_release(
            fixture.client, REPOSITORY, TAG, tmp_path / "dist"
        )


def test_recheck_redownloads_the_same_asset_ids_and_bytes(tmp_path: Path) -> None:
    fixture = _release_fixture()
    expected = VALIDATOR.validate_release(
        fixture.client, REPOSITORY, TAG, tmp_path / "before"
    )

    current = VALIDATOR.recheck_release(
        fixture.client, expected, tmp_path / "after"
    )

    assert current == expected
    assert fixture.client.download_calls == [
        WHEEL_ID,
        SDIST_ID,
        WHEEL_ID,
        SDIST_ID,
    ]


def test_recheck_rejects_tag_move_while_approval_is_pending(tmp_path: Path) -> None:
    fixture = _release_fixture()
    expected = VALIDATOR.validate_release(
        fixture.client, REPOSITORY, TAG, tmp_path / "before"
    )
    moved_commit = "e" * 40
    fixture.client.responses[f"{BASE}/git/ref/tags/{TAG}"]["object"][
        "sha"
    ] = moved_commit
    fixture.client.responses[
        f"{BASE}/contents/pyproject.toml?ref={moved_commit}"
    ] = fixture.project_contents

    with pytest.raises(VALIDATOR.ValidationError, match="changed while publication"):
        VALIDATOR.recheck_release(fixture.client, expected, tmp_path / "after")


def test_recheck_rejects_asset_id_replacement_during_approval(
    tmp_path: Path,
) -> None:
    fixture = _release_fixture()
    expected = VALIDATOR.validate_release(
        fixture.client, REPOSITORY, TAG, tmp_path / "before"
    )
    fixture.release["assets"][0]["id"] = 303
    fixture.client.downloads[303] = fixture.client.downloads[WHEEL_ID]

    with pytest.raises(VALIDATOR.ValidationError, match="changed while publication"):
        VALIDATOR.recheck_release(fixture.client, expected, tmp_path / "after")
    assert fixture.client.download_calls == [WHEEL_ID, SDIST_ID]


def test_github_outputs_capture_only_validated_immutable_values(
    tmp_path: Path,
) -> None:
    fixture = _release_fixture()
    snapshot = VALIDATOR.validate_release(
        fixture.client, REPOSITORY, TAG, tmp_path / "dist"
    )
    output = tmp_path / "github-output"

    VALIDATOR._write_github_outputs(output, snapshot, TRUSTED_COMMIT, SCRIPT)

    parsed = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines()
    )
    assert parsed["tag"] == TAG
    assert parsed["tag_commit"] == COMMIT
    assert parsed["trusted_commit"] == TRUSTED_COMMIT
    assert parsed["wheel_asset_id"] == str(WHEEL_ID)
    assert parsed["sdist_asset_id"] == str(SDIST_ID)
    assert parsed["wheel_digest"].startswith("sha256:")
    assert parsed["sdist_digest"].startswith("sha256:")
    assert parsed["validator_sha256"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
