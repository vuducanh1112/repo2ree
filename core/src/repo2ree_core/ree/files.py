"""File operations the REE aggregate is built out of: fetch, extract, enumerate.

Tar and zip archives can contain entries whose names point outside the
destination directory (``../etc/passwd``, absolute paths, etc.). The
extract helpers filter those entries before extraction so untrusted
archives cannot write outside the destination.

Shell module: performs network and filesystem I/O. Independent of the REE
concept — nothing here knows the on-disk layout — so both the REE flows and
any future archive consumers can share the same operations.
"""

from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from repo2ree_core.digests import HashingWriter


def download_or_copy(origin_url: str, destination: Path) -> Path:
    """Place the bytes referenced by ``origin_url`` at ``destination``.

    Supports ``http`` and ``https`` URLs (streamed download) and local
    filesystem paths (copied with metadata preserved). Raises
    :class:`FileNotFoundError` if the source is neither reachable nor a
    local path that exists.
    """
    parsed = urlparse(origin_url)
    if parsed.scheme in {"http", "https"}:
        # urlopen is stdlib — requests is not available in the workbench image.
        # Scheme is validated on the line above, so only http/https reach here.
        with urlopen(origin_url) as response, destination.open("wb") as target:  # noqa: S310
            shutil.copyfileobj(response, target)
        return destination

    local_path = Path(origin_url)
    if local_path.exists():
        shutil.copy2(local_path, destination)
        return destination

    raise FileNotFoundError(f"Source not found: {origin_url}")


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


def safe_filename(name: str | None, default: str) -> str:
    """Reduce ``name`` to a safe single-component filename."""
    candidate = (name or default).strip().replace("\\", "/").split("/")[-1]
    result = candidate or default

    # ── postcondition ──
    # Single-component: no path separators survive, so the result can never be
    # used to traverse out of the directory it names a file in.
    assert result and "/" not in result and "\\" not in result, f"unsafe filename: {result!r}"  # noqa: S101
    # ───────────────────
    return result


def list_tree_relpaths(root: Path) -> list[str]:
    """Sorted POSIX relative paths of every file beneath ``root``.

    A missing directory reads as empty rather than raising: callers enumerate
    REE subtrees that legitimately do not exist yet (no artifacts built, no
    results captured), and an absent subtree contributes no files.
    """
    if not root.is_dir():
        return []
    return sorted(fp.relative_to(root).as_posix() for fp in root.rglob("*") if fp.is_file())
