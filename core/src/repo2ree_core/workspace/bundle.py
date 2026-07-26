"""Pure helpers for the downloadable REE bundle ZIP.

The bundle mirrors the on-disk REE layout under a ``ree/`` prefix, plus two
top-level files that make the download self-reproducing without repo2ree:

    run.sh                one-click reproducer (see ``ree_scripts.reproducer``)
    REPRODUCING.md        human instructions for the reproducer
    ree/ree.json          manifest
    ree/snapshot.tar.gz   frozen source archive (when available)
    ree/overlay/...       user recipe files (empty dir entry if none)
    ree/artifacts/...     build outputs (runtime, sbom, ...)
    ree/results/<name>/   author result baselines for sealed experiments (opt-in)
    ree/workspace/        empty placeholder — materialized by run.sh on extract

``upstream/`` is intentionally omitted: its contents are already in
``snapshot.tar.gz``. This module is the functional core for the bundle —
it contains layout constants, the ZIP writer, and pure mapping helpers.
All filesystem I/O lives in the shell (``repo2ree_core.storage.workspace_ops``).
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from repo2ree_core.storage.layout import (
    ARTIFACTS_DIRNAME,
    AUTHOR_RECEIPTS_DIRNAME,
    OVERLAY_DIRNAME,
    RECEIPTS_DIRNAME,
    RESULTS_DIRNAME,
    SNAPSHOT_FILENAME,
    WORKSPACE_DIRNAME,
    normalize_workspace_path,
)

# ================================================
# Constants
# ================================================


# Bundle layout is derived from the on-disk layout so the two stay in sync.
# The published manifest entry name (``ree.json``) is bundle-only — the on-disk
# sidecar is ``manifest.json`` — so it lives here rather than in layout.py.
REE_ROOT_PREFIX = "ree/"
_BUNDLE_MANIFEST_FILENAME = "ree.json"
REE_MANIFEST_ENTRY_PATH = f"{REE_ROOT_PREFIX}{_BUNDLE_MANIFEST_FILENAME}"
REE_SNAPSHOT_ENTRY_PATH = f"{REE_ROOT_PREFIX}{SNAPSHOT_FILENAME}"
REE_OVERLAY_PREFIX = f"{REE_ROOT_PREFIX}{OVERLAY_DIRNAME}/"
REE_ARTIFACTS_PREFIX = f"{REE_ROOT_PREFIX}{ARTIFACTS_DIRNAME}/"
# Produced-results store: author baselines packaged when the seal opts results
# into the bundle (``results_included``). Present only when results are included
# and captured; sits outside ``workspace/`` for reviewer diffing.
REE_RESULTS_PREFIX = f"{REE_ROOT_PREFIX}{RESULTS_DIRNAME}/"
REE_WORKSPACE_DIR_ENTRY = f"{REE_ROOT_PREFIX}{WORKSPACE_DIRNAME}/"
# Receipts get their own bundle directory (rather than mirroring ``runs/``)
# because only the receipt record is published — NDJSON logs stay out.
REE_RECEIPTS_PREFIX = f"{REE_ROOT_PREFIX}{RECEIPTS_DIRNAME}/"
REE_AUTHOR_RECEIPTS_PREFIX = f"{REE_RECEIPTS_PREFIX}{AUTHOR_RECEIPTS_DIRNAME}/"

_EPOCH_DATE_TIME = (1980, 1, 1, 0, 0, 0)


# ================================================
# Helpers
# ================================================


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


def should_include_snapshot(*, source_included: bool, source_snapshot_archive: str | None) -> bool:
    """Whether the bundle should publish the source snapshot entry."""
    return bool(source_included and normalize_workspace_path(source_snapshot_archive or ""))


def build_zip_bytes(entries: Iterable[tuple[str, bytes]]) -> bytes:
    """Pack ``entries`` into a deflate-compressed ZIP and return the bytes.

    ``entries`` is a sequence of ``(archive_path, content_bytes)`` pairs. An
    entry whose ``archive_path`` ends with ``/`` is written as an empty
    directory. Entries receive a fixed epoch timestamp so the output is
    byte-identical for identical inputs (enabling content-addressed seal hashes).
    Shell scripts (``*.sh``) are marked executable so the materialized workspace
    and the bundled ``run.sh`` are directly runnable after extraction. Pure
    given its inputs: no filesystem access.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_path, content in entries:
            info = zipfile.ZipInfo(filename=archive_path, date_time=_EPOCH_DATE_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = _unix_mode_attr(archive_path)
            archive.writestr(info, content)
    return buffer.getvalue()


def _unix_mode_attr(archive_path: str) -> int:
    """Unix permission bits for a ZIP entry, as the high 16 bits of external_attr."""
    if archive_path.endswith("/"):
        mode = 0o40755  # directory
    elif archive_path.endswith(".sh"):
        mode = 0o100755  # executable script
    else:
        mode = 0o100644  # regular file
    return mode << 16


@dataclass(frozen=True)
class ArtifactPlan:
    """Pure description of how ``ree/artifacts/`` should be populated.

    ``on_disk_relpaths`` are paths (relative to the on-disk ``artifacts/``
    directory) that should be included verbatim — every REE-produced artifact
    (the SBOM, the reproducibility report) is already one of these.
    ``workspace_pulls`` maps ``{workspace_relpath: archive_basename}`` for the
    runtime, the one artifact an author's own build script writes into
    ``workspace/`` and that packaging therefore has to lift into
    ``artifacts/<basename>``. ``manifest_remap`` maps the original manifest path
    string to the ``artifacts/<basename>`` path used in the bundled manifest.
    """

    on_disk_relpaths: tuple[str, ...]
    workspace_pulls: Mapping[str, str]
    manifest_remap: Mapping[str, str]


def plan_artifact_layout(
    *,
    on_disk_artifact_relpaths: Sequence[str],
    workspace_runtime_path: str | None,
    workspace_files: frozenset[str],
    runtime_included: bool,
) -> ArtifactPlan:
    """Decide how the bundle's ``artifacts/`` directory is populated.

    Pure: only path arithmetic and set operations. ``workspace_files`` is the
    set of relative paths the shell observed in ``workspace/``; the planner
    uses it to skip a runtime reference that has no backing file. On-disk
    artifacts always win over the workspace pull with the same final archive
    path, so a runtime already staged at ``artifacts/runtime.tar.gz`` (as a
    loaded bundle leaves it) is never shadowed.
    """
    on_disk_targets = set(on_disk_artifact_relpaths)
    workspace_pulls: dict[str, str] = {}
    manifest_remap: dict[str, str] = {}
    ws_path = workspace_runtime_path if runtime_included else ""
    normalized = normalize_workspace_path(ws_path or "")
    if (
        normalized
        and ".." not in PurePosixPath(normalized).parts
        and normalized in workspace_files
        and PurePosixPath(normalized).name not in on_disk_targets
    ):
        basename = PurePosixPath(normalized).name
        workspace_pulls[normalized] = basename
        manifest_remap[normalized] = f"{ARTIFACTS_DIRNAME}/{basename}"
    return ArtifactPlan(
        on_disk_relpaths=tuple(sorted(on_disk_artifact_relpaths)),
        workspace_pulls=workspace_pulls,
        manifest_remap=manifest_remap,
    )


def rewrite_manifest_for_bundle(manifest: Mapping[str, Any], remap: Mapping[str, str]) -> dict[str, Any]:
    """Return a copy of ``manifest`` with the ``runtime`` path remapped.

    The ``sbom`` path needs no remapping: it is authored REE-root-relative
    (``artifacts/sbom.json``) and the bundle carries it at exactly that path.
    """
    rewritten = dict(manifest)
    original = rewritten.get("runtime")
    if isinstance(original, str) and original in remap:
        rewritten["runtime"] = remap[original]
    return rewritten
