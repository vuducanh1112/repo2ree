"""Executor-side command preparation for the receipt journal.

``ReceiptJournal`` (storage) lives in ``repo2ree_core.storage.receipt_journal``.
This module owns the executor-specific knowledge of *which* command args to
elide and enforces the invariant that ``action_digest`` is computed over the
unredacted command before any elision happens.

Use ``prepare_command`` at every journaling call site — it returns the digest
and the stored form together so the two operations cannot be inverted.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from repo2ree_core.storage.layout import ReeLayout
from repo2ree_protocol.receipt import compute_action_digest


# ================================================
# Redaction
# ================================================


# Known large or ephemeral fields elided from stored receipts.  Replay
# verification is unaffected because action_digest is computed over the
# *unredacted* command inside prepare_command.  This list covers currently
# known cases; the stored command should not be treated as sanitised for all
# audiences.
_ELIDED_ARG_FIELDS: frozenset[str] = frozenset(
    {
        "content",  # file bodies — large, already stored in overlay/
        "upload_token",  # ephemeral staging token — no provenance value
    }
)


def redact_command(command_dict: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the command with known large/ephemeral args elided.

    Elided fields are replaced with ``{"__elided__": True, "sha256": ...,
    "bytes": ...}`` stubs.

    Prefer ``prepare_command`` at call sites — it computes the digest and
    returns the redacted form together so the ordering cannot be inverted.
    """
    args = command_dict.get("args")
    if not isinstance(args, dict):
        return command_dict
    redacted = dict(args)
    for field in _ELIDED_ARG_FIELDS:
        value = redacted.get(field)
        if isinstance(value, str):
            raw = value.encode("utf-8")
            redacted[field] = {
                "__elided__": True,
                "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
    return {**command_dict, "args": redacted}


def prepare_command(command_dict: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Return ``(action_digest, redacted_command)`` for a raw command dict.

    The digest is always computed over the unredacted form; the redacted form
    is what gets written to the journal.  Bundling both operations here means
    callers cannot accidentally compute the digest over already-elided data.
    """
    digest = compute_action_digest(command_dict)
    return digest, redact_command(command_dict)


# ================================================
# REE state snapshotting
# ================================================

# Format version prefix — bump when the canonical encoding changes so that
# old and new digests are never silently compared as equal.
_DIGEST_SCHEME = "reetree-v1"


def snapshot_ree_digest(layout: ReeLayout) -> str:
    """Canonical digest of the full REE source state.

    Covers all three sources of truth:

    * **upstream** — sha256 of ``snapshot.tar.gz`` (the frozen source archive).
      None when no source has been acquired yet.
    * **overlay** — canonical tree hash of ``overlay/``: file mode, content,
      symlink targets, and empty directories; encoded as a sorted JSON array
      so the result is unambiguous for any path content.
    * **intent** — sha256 of the canonical JSON of ``reeIntent`` from
      ``.workspace.json``.  Intent controls dockerfile choice, expected
      outputs, and include toggles, so it is an input even for ops that do
      not touch the file tree.

    Always returns a string.  Two receipts with the same digest operated on
    identical REE state.
    """
    state = json.dumps(
        {
            "upstream": _upstream_digest(layout),
            "overlay": _tree_digest(layout.overlay),
            "intent": _intent_digest(layout),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{_DIGEST_SCHEME}:" + hashlib.sha256(state.encode()).hexdigest()


def _upstream_digest(layout: ReeLayout) -> str | None:
    """sha256 of snapshot.tar.gz — the canonical upstream reference.

    Hashing the archive is cheaper and equivalent to walking upstream/:
    the archive is the immutable source of truth; upstream/ is derived from it.
    Returns None when no source has been acquired yet.
    """
    snapshot = layout.snapshot_archive
    if not snapshot.exists():
        return None
    return "sha256:" + hashlib.sha256(snapshot.read_bytes()).hexdigest()


def _tree_digest(root: Path) -> str:
    """Canonical sha256 over all entries under root.

    Each entry carries type (``f`` file, ``l`` symlink, ``d`` directory),
    full permission bits, relative path, and a content hash.  Entries are
    sorted by path and encoded as a JSON array — the encoding is unambiguous
    for any path content (no delimiter injection).

    Returns the sha256 of ``"[]"`` when root does not exist (empty tree).
    """
    entries: list[dict[str, str]] = []
    if root.exists():
        for path in sorted(root.rglob("*"), key=lambda p: str(p.relative_to(root))):
            rel = str(path.relative_to(root))
            if path.is_symlink():
                target_hash = hashlib.sha256(
                    os.readlink(str(path)).encode()
                ).hexdigest()
                entries.append({"t": "l", "p": rel, "h": target_hash})
            elif path.is_file():
                mode = oct(path.stat().st_mode & 0o777)[2:]
                content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append({"t": "f", "m": mode, "p": rel, "h": content_hash})
            elif path.is_dir():
                mode = oct(path.stat().st_mode & 0o777)[2:]
                entries.append({"t": "d", "m": mode, "p": rel})
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _intent_digest(layout: ReeLayout) -> str | None:
    """sha256 of the canonical JSON of reeIntent from .workspace.json.

    Returns None when the metadata file does not exist (REE not yet initialised).
    """
    metadata_path = layout.metadata
    if not metadata_path.exists():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    intent = metadata.get("reeIntent") or {}
    canonical = json.dumps(intent, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


# ================================================
# Output elision
# ================================================


# String output values larger than this are elided in the stored receipt.
# Outputs have no fixed schema so elision is size-based rather than field-based.
_OUTPUT_ELIDE_THRESHOLD_BYTES: int = 4096


def elide_large_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of outputs with large string values replaced by elision stubs.

    Applied to ``ActionReceipt.outputs`` before journal write.  The same stub
    shape used for command arg elision is reused so consumers have one format
    to handle.
    """
    result: dict[str, Any] = {}
    for key, value in outputs.items():
        if isinstance(value, str):
            raw = value.encode("utf-8")
            if len(raw) > _OUTPUT_ELIDE_THRESHOLD_BYTES:
                result[key] = {
                    "__elided__": True,
                    "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                }
                continue
        result[key] = value
    return result
