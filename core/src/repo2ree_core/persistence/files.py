from __future__ import annotations

import json
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from repo2ree_core.digests import HashingWriter
from repo2ree_ree.digest import Digest


def staging_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.{uuid4().hex}.tmp")


def publish_atomic(staged: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged, path)  # noqa: PTH105


def write_atomic(path: Path, content: bytes) -> None:
    temporary = staging_path(path)
    temporary.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_bytes(content)
        publish_atomic(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def json_document_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def write_json_atomic(path: Path, payload: Any) -> None:
    write_atomic(path, json_document_bytes(payload))


def safe_extract_tar(archive: Path, destination: Path) -> None:
    dest_root = destination.resolve()

    def _is_safe(member: tarfile.TarInfo) -> bool:
        member_path = destination / member.name
        try:
            member_path.resolve().relative_to(dest_root)
        except ValueError:
            return False
        return True

    with tarfile.open(archive, mode="r:*") as tar:
        safe_members = [member for member in tar.getmembers() if _is_safe(member)]
        tar.extractall(destination, members=safe_members, filter="data")


def safe_extract_zip(archive: Path, destination: Path) -> None:
    dest_root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            extracted_path = (destination / member.filename).resolve()
            try:
                extracted_path.relative_to(dest_root)
            except ValueError:
                continue
            zf.extract(member, destination)


def pack_directory_tar_gz(source_path: Path, archive_path: Path, *, left_out: frozenset[str] = frozenset()) -> Digest:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("wb") as raw:
        writer = HashingWriter(raw)
        with tarfile.open(fileobj=writer, mode="w:gz") as tar:  # type: ignore[call-overload]
            for item in sorted(source_path.iterdir(), key=lambda path: path.name):
                if item.name not in left_out:
                    tar.add(item, arcname=item.name)
    return writer.digest


def list_tree_relpaths(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(fp.relative_to(root).as_posix() for fp in root.rglob("*") if fp.is_file())
