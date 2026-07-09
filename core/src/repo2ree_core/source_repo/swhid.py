"""Compute Software Heritage persistent identifiers (SWHIDs) for source trees.

A SWHID is a stable, intrinsic name for a software artifact: the same bytes
always yield the same identifier, independent of where the artifact is stored.
We compute the *directory* identifier ``swh:1:dir:<hash>`` for a checked-out
source tree by reproducing git's object hashing — file contents hash as git
blobs, directories as git trees — and the root tree's hash is the directory
SWHID.

The pure hashing core (:func:`content_swhid`, :func:`hash_directory_entries`)
takes bytes and needs no I/O; :func:`directory_swhid` is the shell that walks a
path on disk and feeds that core.

Reference:
https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass
from pathlib import Path

# Git tree-entry modes, rendered the way git serializes them (octal, no leading
# zero on the directory mode).
_MODE_FILE = b"100644"
_MODE_EXEC = b"100755"
_MODE_SYMLINK = b"120000"
_MODE_DIR = b"40000"

# Directories we never descend into when hashing a source checkout, so the
# identifier reflects the source itself rather than VCS bookkeeping.
_EXCLUDED_DIRS = frozenset({".git"})

_SWHID_DIR_PREFIX = "swh:1:dir:"
_SWHID_CNT_PREFIX = "swh:1:cnt:"


# ================================================
# Pure hashing core
# ================================================


@dataclass(frozen=True)
class _TreeEntry:
    """One child of a directory: its git mode, raw name and 20-byte object id."""

    mode: bytes
    name: bytes
    object_id: bytes

    def sort_key(self) -> bytes:
        """Git orders entries by name, treating directories as ``name + "/"``."""
        return self.name + (b"/" if self.mode == _MODE_DIR else b"")


def _git_object_id(object_type: bytes, payload: bytes) -> bytes:
    """SHA-1 of a git object: ``<type> <len>\\0<payload>`` — the raw 20 bytes."""
    header = object_type + b" " + str(len(payload)).encode() + b"\x00"
    object_id = hashlib.sha1(header + payload).digest()  # noqa: S324 - git uses SHA-1 by design

    # ── postcondition ──
    # The raw git object id is always 20 bytes; content_object_id and the tree
    # hasher hand this straight to callers that .hex() it into a 40-char SWHID.
    assert len(object_id) == 20, f"git object id must be 20 bytes, got {len(object_id)}"  # noqa: S101
    # ───────────────────
    return object_id


def content_object_id(data: bytes) -> bytes:
    """Raw 20-byte git blob id of ``data`` (the ``cnt`` object identifier)."""
    return _git_object_id(b"blob", data)


def content_swhid(data: bytes) -> str:
    """``swh:1:cnt:<hash>`` for a file whose bytes are ``data``."""
    swhid = _SWHID_CNT_PREFIX + content_object_id(data).hex()

    # ── postcondition ──
    assert len(swhid) == len(_SWHID_CNT_PREFIX) + 40, f"malformed content SWHID: {swhid}"  # noqa: S101
    # ───────────────────
    return swhid


def hash_directory_entries(entries: list[_TreeEntry]) -> bytes:
    """Raw 20-byte git tree id for ``entries`` (one directory level)."""
    ordered = sorted(entries, key=_TreeEntry.sort_key)
    payload = b"".join(entry.mode + b" " + entry.name + b"\x00" + entry.object_id for entry in ordered)
    return _git_object_id(b"tree", payload)


# ================================================
# Filesystem shell
# ================================================


def _entry_for(path: Path) -> _TreeEntry | None:
    """Build the tree entry for ``path``, or ``None`` to skip it.

    Symlinks hash as a blob of their (unresolved) target, matching git; the
    executable bit on a regular file selects the ``100755`` mode. Anything that
    is neither a regular file, symlink nor directory (sockets, fifos, …) is
    skipped, as is any excluded directory name.
    """
    name = path.name.encode()
    if path.is_symlink():
        target = path.readlink()
        return _TreeEntry(_MODE_SYMLINK, name, content_object_id(str(target).encode()))
    if path.is_dir():
        if path.name in _EXCLUDED_DIRS:
            return None
        return _TreeEntry(_MODE_DIR, name, _directory_object_id(path))
    if path.is_file():
        mode = _MODE_EXEC if path.stat().st_mode & stat.S_IXUSR else _MODE_FILE
        return _TreeEntry(mode, name, content_object_id(path.read_bytes()))
    return None


def _directory_object_id(directory: Path) -> bytes:
    """Raw 20-byte git tree id for the on-disk ``directory`` and its descendants."""
    entries = [entry for child in directory.iterdir() if (entry := _entry_for(child)) is not None]
    return hash_directory_entries(entries)


def directory_swhid(directory: Path | str) -> str:
    """``swh:1:dir:<hash>`` for the source tree rooted at ``directory``.

    Excludes ``.git`` so the identifier names the source, not its VCS history.
    Raises ``NotADirectoryError`` if ``directory`` is not an existing directory.
    """
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    swhid = _SWHID_DIR_PREFIX + _directory_object_id(root).hex()

    # ── postcondition ──
    assert len(swhid) == len(_SWHID_DIR_PREFIX) + 40, f"malformed directory SWHID: {swhid}"  # noqa: S101
    # ───────────────────
    return swhid
