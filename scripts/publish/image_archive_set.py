#!/usr/bin/env python3
"""Seal and verify a revision-bound set of image archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

ARCHIVES = (
    "repo2ree-gui-local.tar",
    "repo2ree-backend-local.tar",
    "repo2ree-provider-docker-local.tar",
)
MANIFEST = "IMAGE_CANDIDATE_MANIFEST.json"
REVISION = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def atomic_write(path: Path, contents: str) -> None:
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as pending:
        pending.write(contents)
        pending_path = Path(pending.name)
    pending_path.replace(path)


def seal(directory: Path, revision: str) -> None:
    if not directory.is_dir():
        raise RuntimeError(f"archive directory does not exist: {directory}")
    if not REVISION.fullmatch(revision):
        raise RuntimeError(f"invalid image candidate revision: {revision}")
    missing = [name for name in ARCHIVES if not (directory / name).is_file()]
    if missing:
        raise RuntimeError(f"image archive set is incomplete; missing: {' '.join(missing)}")
    document = {
        "schema": 1,
        "revision": revision,
        "archives": {name: file_digest(directory / name) for name in ARCHIVES},
    }
    atomic_write(directory / MANIFEST, json.dumps(document, indent=2, sort_keys=True) + "\n")
    atomic_write(directory / "IMAGE_CANDIDATE_REV", f"{revision}\n")


def verify(directory: Path) -> str:
    manifest_path = directory / MANIFEST
    if not manifest_path.is_file():
        raise RuntimeError(f"no sealed image archive manifest in {directory} — rebuild with 'just archive-images'")
    try:
        document = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(f"invalid image archive manifest: {manifest_path}") from error
    if not isinstance(document, dict):
        raise RuntimeError(f"invalid image archive manifest: {manifest_path}")
    revision = document.get("revision")
    archives = document.get("archives")
    if document.get("schema") != 1 or not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise RuntimeError(f"invalid image archive manifest metadata: {manifest_path}")
    if not isinstance(archives, dict) or set(archives) != set(ARCHIVES):
        raise RuntimeError(f"incomplete image archive manifest: {manifest_path}")
    stamp = directory / "IMAGE_CANDIDATE_REV"
    if not stamp.is_file() or stamp.read_text().strip() != revision:
        raise RuntimeError(f"image archive revision stamp does not match its manifest: {directory}")
    for name in ARCHIVES:
        expected = archives[name]
        path = directory / name
        if not isinstance(expected, str) or not DIGEST.fullmatch(expected) or not path.is_file():
            raise RuntimeError(f"invalid image archive entry: {name}")
        actual = file_digest(path)
        if actual != expected:
            raise RuntimeError(f"image archive digest mismatch for {name}: {actual}, expected {expected}")
    return revision


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    seal_parser = commands.add_parser("seal")
    seal_parser.add_argument("directory", type=Path)
    seal_parser.add_argument("revision")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "seal":
            seal(args.directory, args.revision)
        else:
            verify(args.directory)
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
