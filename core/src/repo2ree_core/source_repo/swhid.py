from __future__ import annotations

import hashlib
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.persistence.lfs import LfsPointer

_MODE_FILE = b"100644"
_MODE_EXEC = b"100755"
_MODE_SYMLINK = b"120000"
_MODE_DIR = b"40000"

_EXCLUDED_DIRS = frozenset({".git"})

_SWHID_DIR_PREFIX = "swh:1:dir:"
_SWHID_CNT_PREFIX = "swh:1:cnt:"


@dataclass(frozen=True)
class _TreeEntry:
    mode: bytes
    name: bytes
    object_id: bytes

    def sort_key(self) -> bytes:
        return self.name + (b"/" if self.mode == _MODE_DIR else b"")


def _git_object_id(object_type: bytes, payload: bytes) -> bytes:
    header = object_type + b" " + str(len(payload)).encode() + b"\x00"
    object_id = hashlib.sha1(header + payload).digest()  # noqa: S324

    assert len(object_id) == 20, f"git object id must be 20 bytes, got {len(object_id)}"  # noqa: S101
    return object_id


def content_object_id(data: bytes) -> bytes:
    return _git_object_id(b"blob", data)


def content_swhid(data: bytes) -> str:
    swhid = _SWHID_CNT_PREFIX + content_object_id(data).hex()

    assert len(swhid) == len(_SWHID_CNT_PREFIX) + 40, f"malformed content SWHID: {swhid}"  # noqa: S101
    return swhid


def hash_directory_entries(entries: list[_TreeEntry]) -> bytes:
    ordered = sorted(entries, key=_TreeEntry.sort_key)
    payload = b"".join(entry.mode + b" " + entry.name + b"\x00" + entry.object_id for entry in ordered)
    return _git_object_id(b"tree", payload)


class LfsPayloadError(ValueError):
    pass


@dataclass
class _Walk:
    root: Path
    lfs: Mapping[str, LfsPointer]
    seen: set[str]

    def entry_for(self, path: Path) -> _TreeEntry | None:
        name = path.name.encode()
        if path.is_symlink():
            target = path.readlink()
            return _TreeEntry(_MODE_SYMLINK, name, content_object_id(str(target).encode()))
        if path.is_dir():
            if path.name in _EXCLUDED_DIRS:
                return None
            return _TreeEntry(_MODE_DIR, name, self.directory_object_id(path))
        if path.is_file():
            mode = _MODE_EXEC if path.stat().st_mode & stat.S_IXUSR else _MODE_FILE
            relative = path.relative_to(self.root).as_posix()
            if (pointer := self.lfs.get(relative)) is not None:
                self.seen.add(relative)
                return _TreeEntry(mode, name, content_object_id(_payload_as_pointer(path, relative, pointer)))
            return _TreeEntry(mode, name, content_object_id(path.read_bytes()))
        return None

    def directory_object_id(self, directory: Path) -> bytes:
        entries = [entry for child in directory.iterdir() if (entry := self.entry_for(child)) is not None]
        return hash_directory_entries(entries)


def _payload_as_pointer(path: Path, relative: str, pointer: LfsPointer) -> bytes:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
            size += len(chunk)
    if (digest.hexdigest(), size) != (pointer.oid, pointer.size):
        if path.stat().st_size < 1024 and LfsPointer.parse(path.read_bytes()) == pointer:
            raise LfsPayloadError(f"{relative} is still its LFS pointer: its content did not arrive")
        raise LfsPayloadError(f"{relative} is not the content its LFS pointer names (sha256:{pointer.oid})")
    return pointer.encode()


def directory_swhid(directory: Path | str, *, lfs: Mapping[str, LfsPointer] | None = None) -> str:
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    walk = _Walk(root, lfs or {}, set())
    swhid = _SWHID_DIR_PREFIX + walk.directory_object_id(root).hex()
    if missing := sorted(set(walk.lfs) - walk.seen):
        raise LfsPayloadError(f"{len(missing)} LFS files are missing, the first {missing[0]}")

    assert len(swhid) == len(_SWHID_DIR_PREFIX) + 40, f"malformed directory SWHID: {swhid}"  # noqa: S101
    return swhid
