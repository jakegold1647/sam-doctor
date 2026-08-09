#!/usr/bin/env python3
"""Rewrite a source archive with stable tar and gzip metadata."""

from __future__ import annotations

import argparse
import gzip
import os
import tarfile
import tempfile
from pathlib import Path


def _source_date_epoch() -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "")
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer") from error
    if value < 0:
        raise ValueError("SOURCE_DATE_EPOCH must be a non-negative integer")
    return value


def _normalized_member(member: tarfile.TarInfo, epoch: int) -> tarfile.TarInfo:
    member.mtime = epoch
    member.uid = 0
    member.gid = 0
    member.uname = ""
    member.gname = ""
    member.pax_headers = {}
    if member.isdir():
        member.mode = 0o755
    elif member.isfile():
        member.mode = 0o755 if member.mode & 0o111 else 0o644
    elif member.issym():
        member.mode = 0o777
    return member


def normalize_archive(path: Path, epoch: int) -> None:
    if path.suffixes[-2:] != [".tar", ".gz"]:
        raise ValueError(f"Expected a .tar.gz source archive: {path}")

    temporary_path: Path | None = None
    try:
        with tarfile.open(path, mode="r:gz") as source:
            members = sorted(source.getmembers(), key=lambda member: member.name)
            with tempfile.NamedTemporaryFile(
                dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)

            with (
                temporary_path.open("wb") as raw,
                gzip.GzipFile(
                    fileobj=raw, mode="wb", filename="", mtime=epoch
                ) as compressed,
                tarfile.open(
                    fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT
                ) as destination,
            ):
                for original in members:
                    member = _normalized_member(original, epoch)
                    if member.isfile():
                        payload = source.extractfile(original)
                        if payload is None:
                            raise ValueError(
                                f"Could not read source archive member: {member.name}"
                            )
                        with payload:
                            destination.addfile(member, payload)
                    else:
                        destination.addfile(member)

        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize one source archive for reproducible release bytes."
    )
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        normalize_archive(args.archive, _source_date_epoch())
    except (OSError, tarfile.TarError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
