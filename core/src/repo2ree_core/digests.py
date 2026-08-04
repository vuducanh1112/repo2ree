"""Canonical content digests for run receipts and seal-time checks.

Every digest in the receipt and audit vocabulary is a ``sha256:<hex>``
string — one format from day one, so recorded and current values are always
directly comparable. Digests are recorded as *receipts* (provenance), never
used as cache keys.

Leaf-ish module: imports nothing from ``repo2ree_core`` so ree, operations,
and workspace layers can all share it without an import cycle.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import IO, Any, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

_CHUNK_SIZE = 1024 * 1024

DIGEST_PREFIX = "sha256:"


# A canonical digest is ``sha256:`` followed by 64 lowercase hex chars. The
# whole receipt and audit vocabulary relies on this one shape being comparable
# across recorded and current values, so every producer asserts it on the way out.
_DIGEST_LEN = len(DIGEST_PREFIX) + 64


class Digest(str):
    """Nominal SHA-256 digest retaining its scalar JSON representation."""

    def __new__(cls, value: str) -> Self:
        text = str(value)
        if not text.startswith(DIGEST_PREFIX) or not text.removeprefix(DIGEST_PREFIX):
            raise ValueError("Digest must use the sha256:<value> form")
        return str.__new__(cls, text)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )


def _is_canonical_digest(digest: str) -> bool:
    return digest.startswith(DIGEST_PREFIX) and len(digest) == _DIGEST_LEN


def digest_bytes(data: bytes) -> Digest:
    digest = Digest(DIGEST_PREFIX + hashlib.sha256(data).hexdigest())

    # ── postcondition ──
    assert _is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    # ───────────────────
    return digest


def short_hash(data: bytes, *, length: int = 12) -> str:
    """A truncated hex hash for identifiers, not provenance.

    Deliberately not a canonical digest: it labels a value (a candidate id, a
    config fingerprint) so equal inputs get equal labels. Never record one in a
    receipt — those must stay comparable, which is what :func:`digest_bytes` is
    for.
    """
    return hashlib.sha256(data).hexdigest()[:length]


def digest_file(path: Path) -> Digest:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            hasher.update(chunk)
    digest = Digest(DIGEST_PREFIX + hasher.hexdigest())

    # ── postcondition ──
    assert _is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    # ───────────────────
    return digest


def digest_file_if_exists(path: Path) -> Digest | None:
    """Digest of ``path``, or ``None`` when it is not a regular file."""
    if not path.is_file():
        return None
    return digest_file(path)


def digest_json(payload: Any) -> Digest:
    """Digest of a JSON-serializable value under a canonical serialization.

    Canonical form: sorted keys, no whitespace. Used for spec-shaped inputs
    that live inside the manifest rather than as files (e.g. an experiment's
    expected-output spec).
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return digest_bytes(canonical.encode("utf-8"))


def digest_tree(root: Path) -> Digest:
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
    digest = Digest(DIGEST_PREFIX + hasher.hexdigest())

    # ── postcondition ──
    assert _is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    # ───────────────────
    return digest


def digest_output_paths(base: Path, output_paths: list[str]) -> Digest | None:
    """Digest of an experiment's declared outputs, resolved under ``base``.

    ``None`` when the experiment declares no outputs (nothing to bind); a
    declared-but-absent path contributes nothing. Each declared path is folded
    in under its declared relative form (files directly, directories by their
    contained files) so the digest is stable regardless of iteration order and
    directly comparable between capture time (over the workspace) and seal time.
    """
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

    # ── postcondition ──
    assert _is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
    # ───────────────────
    return digest


class HashingWriter:
    """Binary writer wrapper that hashes every byte passing through it.

    Lets archive writers produce a content digest of exactly the bytes they
    persisted, without a second read of the file.
    """

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

        # ── postcondition ──
        assert _is_canonical_digest(digest), f"non-canonical digest: {digest}"  # noqa: S101
        # ───────────────────
        return digest
