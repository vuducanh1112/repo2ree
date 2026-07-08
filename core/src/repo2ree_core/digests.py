"""Canonical content digests for run receipts and seal-time checks.

Every digest in the receipt/consistency vocabulary is a ``sha256:<hex>``
string — one format from day one, so recorded and current values are always
directly comparable. Digests are recorded as *receipts* (provenance), never
used as cache keys.

Leaf-ish module: imports nothing from ``repo2ree_core`` so storage, envelope,
and workspace layers can all share it without an import cycle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK_SIZE = 1024 * 1024

DIGEST_PREFIX = "sha256:"


def digest_bytes(data: bytes) -> str:
    return DIGEST_PREFIX + hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return DIGEST_PREFIX + hasher.hexdigest()


def digest_file_if_exists(path: Path) -> str | None:
    """Digest of ``path``, or ``None`` when it is not a regular file."""
    if not path.is_file():
        return None
    return digest_file(path)


def digest_json(payload: Any) -> str:
    """Digest of a JSON-serializable value under a canonical serialization.

    Canonical form: sorted keys, no whitespace. Used for spec-shaped inputs
    that live inside the intent rather than as files (e.g. an experiment's
    expected-output spec).
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return digest_bytes(canonical.encode("utf-8"))


def digest_tree(root: Path) -> str:
    """Digest of a directory tree: every file's relative path and content.

    Path and content digest are folded in with delimiters so no two distinct
    trees can collide by concatenation. Empty or absent trees hash to the
    digest of the empty input.
    """
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
    return DIGEST_PREFIX + hasher.hexdigest()


class HashingWriter:
    """Binary writer wrapper that hashes every byte passing through it.

    Lets archive writers produce a content digest of exactly the bytes they
    persisted, without a second read of the file.
    """

    def __init__(self, target: Any):
        self._target = target
        self._hasher = hashlib.sha256()

    def write(self, data: bytes) -> int:
        self._hasher.update(data)
        return self._target.write(data)

    def flush(self) -> None:
        self._target.flush()

    @property
    def digest(self) -> str:
        return DIGEST_PREFIX + self._hasher.hexdigest()
