from __future__ import annotations

import hashlib
from pathlib import Path
from typing import IO

from repo2ree_ree.digest import DIGEST_PREFIX, Digest, is_canonical_digest

_CHUNK_SIZE = 1024 * 1024


def short_hash(data: bytes, *, length: int = 12) -> str:
    return hashlib.sha256(data).hexdigest()[:length]


def digest_file(path: Path) -> Digest:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            hasher.update(chunk)
    digest = Digest(DIGEST_PREFIX + hasher.hexdigest())

    assert is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    return digest


def digest_file_if_exists(path: Path) -> Digest | None:
    if not path.is_file():
        return None
    return digest_file(path)


def digest_tree(root: Path) -> Digest:
    hasher = hashlib.sha256()
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(digest_file(path).encode("ascii"))
            hasher.update(b"\0")
    digest = Digest(DIGEST_PREFIX + hasher.hexdigest())

    assert is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    return digest


def digest_output_paths(base: Path, output_paths: list[str]) -> Digest | None:
    if not output_paths:
        return None
    hasher = hashlib.sha256()
    for rel in sorted(set(output_paths)):
        target = base / rel
        if target.is_file():
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(digest_file(target).encode("ascii"))
            hasher.update(b"\0")
        elif target.is_dir():
            for path in sorted(target.rglob("*")):
                if not path.is_file():
                    continue
                sub = f"{rel}/{path.relative_to(target).as_posix()}"
                hasher.update(sub.encode("utf-8"))
                hasher.update(b"\0")
                hasher.update(digest_file(path).encode("ascii"))
                hasher.update(b"\0")
    digest = Digest(DIGEST_PREFIX + hasher.hexdigest())

    assert is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    return digest


class HashingWriter:
    def __init__(self, target: IO[bytes]):
        self._target = target
        self._hasher = hashlib.sha256()

    def write(self, data: bytes) -> int:
        self._hasher.update(data)
        return self._target.write(data)

    def flush(self) -> None:
        self._target.flush()

    @property
    def digest(self) -> Digest:
        digest = Digest(DIGEST_PREFIX + self._hasher.hexdigest())

        assert is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
        return digest
