"""Pure planning of the downloadable REE bundle.

The bundle is a ZIP archive containing the manifest plus selected
artifacts (runtime, SBOM, source snapshot). This module decides *what*
should go in: it produces a list of :class:`BundleCandidate` describing
each potential entry and where its bytes come from. The shell is
responsible for the existence checks and the actual byte fetches.

No filesystem I/O happens here.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from repo2ree_core.domain.ree import REE
from repo2ree_core.storage.layout import normalize_workspace_path
from repo2ree_core.workspace.manifest import build_manifest_payload


REE_ROOT_PREFIX = "ree/"
REE_MANIFEST_ENTRY_PATH = f"{REE_ROOT_PREFIX}ree.json"


BundleEntryKind = Literal["manifest", "artifact", "source"]
BundleSourceKind = Literal["inline", "workspace", "ree"]


@dataclass(frozen=True)
class BundleCandidate:
    """A single candidate entry for the bundle ZIP.

    ``source_kind`` says how the bytes will be obtained:

    * ``inline``: the bytes are already in :attr:`inline_content`.
    * ``workspace``: read from the workspace at :attr:`source_path`.
    * ``ree``: read from the REE root at :attr:`source_path`.

    For ``workspace`` and ``ree`` candidates, the shell must verify that
    the file at :attr:`source_path` exists and is a regular file before
    emitting the entry into the archive. Inline candidates are always
    included.
    """

    archive_path: str
    kind: BundleEntryKind
    tag: str
    source_kind: BundleSourceKind
    source_path: str | None = None
    inline_content: str | None = None


def safe_filename(name: str | None, default: str) -> str:
    """Reduce ``name`` to a safe single-component filename."""
    candidate = (name or default).strip().replace("\\", "/").split("/")[-1]
    return candidate or default


def archive_workspace_path(path: str) -> str:
    """Make a workspace-relative path safe for use inside the archive."""
    return normalize_workspace_path(path).replace("..", "_")


def archive_root_file_path(path: str, fallback_name: str) -> str:
    """Compute the archive path for a named artifact at the bundle root."""
    normalized = normalize_workspace_path(path)
    filename = safe_filename(
        Path(normalized).name if normalized else None, fallback_name
    )
    return f"{REE_ROOT_PREFIX}{filename}"


def plan_bundle_entries(
    metadata: Mapping[str, Any],
    ree: REE,
    *,
    ree_id: str,
) -> tuple[dict[str, Any], list[BundleCandidate]]:
    """Compute the manifest and the candidate bundle entries.

    The returned manifest has its named-slot paths normalized. Inline
    candidates (the manifest itself) are always returned; file-backed
    candidates must be filtered by the caller against the actual
    filesystem state.
    """
    manifest, excluded_paths = build_manifest_payload(metadata, ree, ree_id=ree_id)

    candidates: list[BundleCandidate] = [
        BundleCandidate(
            archive_path=REE_MANIFEST_ENTRY_PATH,
            kind="manifest",
            tag="Manifest",
            source_kind="inline",
            inline_content=json.dumps(manifest, indent=2, sort_keys=True),
        )
    ]

    optional_slots = [
        ("runtime", "runtime", "Runtime", bool(manifest.get("runtime_included"))),
        ("sbom", "sbom.json", "SBOM", True),
    ]

    for manifest_key, fallback_name, tag, enabled in optional_slots:
        if not enabled:
            continue
        normalized = normalize_workspace_path(str(manifest.get(manifest_key) or ""))
        if not normalized or normalized not in excluded_paths:
            continue
        candidates.append(
            BundleCandidate(
                archive_path=archive_root_file_path(
                    str(manifest.get(manifest_key) or ""), fallback_name
                ),
                kind="artifact",
                tag=tag,
                source_kind="workspace",
                source_path=normalized,
            )
        )

    if manifest.get("source_included"):
        snapshot_archive_name = normalize_workspace_path(
            str(manifest.get("source_snapshot_archive") or "")
        )
        if snapshot_archive_name:
            candidates.append(
                BundleCandidate(
                    archive_path=(
                        f"{REE_ROOT_PREFIX}{archive_workspace_path(snapshot_archive_name)}"
                    ),
                    kind="source",
                    tag="Source",
                    source_kind="ree",
                    source_path=snapshot_archive_name,
                )
            )

    return manifest, candidates


def build_zip_bytes(entries: Iterable[tuple[str, bytes]]) -> bytes:
    """Pack ``entries`` into a deflate-compressed ZIP and return the bytes.

    ``entries`` is a sequence of ``(archive_path, content_bytes)`` pairs.
    Pure given its inputs: no filesystem access. Duplicate archive paths
    are written in the order given; the consumer decides whether to
    deduplicate beforehand.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_path, content in entries:
            archive.writestr(archive_path, content)
    return buffer.getvalue()
