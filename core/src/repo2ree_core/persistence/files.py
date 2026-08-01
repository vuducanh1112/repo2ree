"""File operations the REE aggregate is built out of: write, fetch, extract, enumerate.

Tar and zip archives can contain entries whose names point outside the
destination directory (``../etc/passwd``, absolute paths, etc.). The
extract helpers filter those entries before extraction so untrusted
archives cannot write outside the destination.

Shell module: performs network and filesystem I/O. Independent of the REE
concept — nothing here knows the on-disk layout — so both the REE flows and
any future archive consumers can share the same operations.
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import uuid4

from repo2ree_core.digests import Digest, HashingWriter

# ================================================
# Durable writes
# ================================================


def staging_path(path: Path) -> Path:
    """A sibling of ``path`` to write before publishing it with :func:`publish_atomic`.

    A sibling rather than a temp directory so the publish is a rename within one
    filesystem, which is what makes it atomic. Unique per call: two writers
    racing on one path must not collide on the staging file and hand each other
    a partial one to publish.
    """
    return path.with_name(f".{path.name}.{uuid4().hex}.tmp")


def publish_atomic(staged: Path, path: Path) -> None:
    """Make already-written bytes visible at ``path`` in one indivisible step.

    For producers that cannot hand over a ``bytes`` — a subprocess writing its
    own output file, a stream too large to buffer. Write to
    :func:`staging_path`, then publish here once the producer has finished
    *successfully*; on any other outcome unlink the staging file instead, and
    whatever was at ``path`` is still there untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Kept as `os.replace` rather than `staged.replace(path)` (PTH105): this call
    # is the atomicity seam, and test_atomic_write patches
    # `repo2ree_core.persistence.files.os.replace` to prove the guarantees this
    # docstring claims. `Path.replace` resolves `os` inside pathlib, where that
    # patch cannot reach, so the rename would silently stop being covered.
    os.replace(staged, path)  # noqa: PTH105


def write_atomic(path: Path, content: bytes) -> None:
    """Replace ``path`` with ``content``, or leave what was there untouched.

    Every durable file this REE writes goes through here: the bytes land on a
    sibling temporary and become visible under the real name in one
    :func:`os.replace`, so a reader sees the previous version or the new one,
    never a prefix of the new one.

    Deliberately *not* durable across power loss — that needs an ``fsync`` of the
    file and its parent on every write. The failure this guards is a killed
    workbench, where the container dies but the volume does not.

    Buffers ``content`` in memory. A caller that cannot hold its output (a
    streamed download, a subprocess writing its own file) uses
    :func:`staging_path` and :func:`publish_atomic` directly.
    """
    temporary = staging_path(path)
    temporary.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_bytes(content)
        publish_atomic(temporary, path)
    except BaseException:
        # Includes cancellation: a killed write must not leave litter beside the
        # file it failed to replace.
        temporary.unlink(missing_ok=True)
        raise


def json_document_bytes(payload: Any) -> bytes:
    """Serialize ``payload`` the way this REE spells a persisted document.

    Indented and key-sorted: these files are read by humans auditing an REE and
    diffed between runs, and sorted keys are what keep a diff about the values
    that changed. Distinct from :func:`repo2ree_core.digests.digest_json`, which
    canonicalizes for *hashing* (compact, no whitespace) — the two must not be
    merged, because changing the persisted spelling here would change every
    digest there.
    """
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def write_json_atomic(path: Path, payload: Any) -> None:
    """Atomically replace ``path`` with ``payload`` as a persisted JSON document."""
    write_atomic(path, json_document_bytes(payload))


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


def pack_directory_tar_gz(source_path: Path, archive_path: Path) -> Digest:
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
    # PT018 is suppressed below: this is one postcondition with one message, the
    # idiom the other leaf primitives use. Splitting it would report three
    # unrelated failures where the code asserts a single property.
    assert result and "/" not in result and "\\" not in result, f"unsafe filename: {result!r}"  # noqa: S101, PT018
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
