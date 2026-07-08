"""Archive packing and safe extraction.

Tar and zip archives can contain entries whose names point outside the
destination directory (``../etc/passwd``, absolute paths, etc.). The
extract helpers filter those entries before extraction so untrusted
archives cannot write outside the destination.

Shell module: performs filesystem I/O. Independent of the REE concept so
both the REE flows and any future archive consumers can share the same
operations.
"""

from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from repo2ree_core.digests import HashingWriter


def safe_extract_tar(archive: Path, destination: Path) -> None:
    """Extract ``archive`` into ``destination``, skipping unsafe members.

    A member is unsafe if its resolved path falls outside ``destination``.
    Symlinks within the archive are extracted as-is and resolved relative
    to ``destination`` at access time, so the same path check applies.
    """
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
    """Extract ``archive`` into ``destination``, skipping unsafe members."""
    dest_root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            extracted_path = (destination / member.filename).resolve()
            try:
                extracted_path.relative_to(dest_root)
            except ValueError:
                continue
            zf.extract(member, destination)


def pack_directory_tar_gz(source_path: Path, archive_path: Path) -> str:
    """Write a gzip tar containing every top-level entry of ``source_path``.

    Each top-level entry is added under its own name (so the archive does
    not include the ``source_path`` directory itself). Entries are added
    in name-sorted order at the top level; recursive descent follows the
    default :mod:`tarfile` behavior.

    Returns the ``sha256:<hex>`` digest of the written archive, hashed while
    the stream is written so the digest is of exactly the persisted bytes.
    """
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("wb") as raw:
        writer = HashingWriter(raw)
        with tarfile.open(fileobj=writer, mode="w:gz") as tar:  # type: ignore[call-overload]
            for item in sorted(source_path.iterdir(), key=lambda path: path.name):
                tar.add(item, arcname=item.name)
    return writer.digest
