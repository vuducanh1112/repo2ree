"""Workspace/REE views and bundle assembly.

Imperative shell: functions perform filesystem I/O through ReeStore and
ReeLayout. No function reads from application settings; callers pass
``storage_root`` explicitly so this module can live in core.

These operations run **inside the workbench** (via the ``repo2ree`` CLI), which
is the single source of truth for REE state. Mutating workspace operations
(acquire, write, patch, upload, remove) are owned by the command-envelope
handlers in ``repo2ree_core.envelope.handlers``; this module provides the
read views (``get_workspace``, ``read_file_bytes``), the sealing operation
(``seal_workspace_ree``), and the sealed-bundle reader
(``build_workspace_ree_archive``) the CLI exposes.

Layered on-disk layout (per REE):
  upstream/        extracted source, treated as read-only
  overlay/         user-added and tool-generated recipe files
  workspace/       materialized view (upstream merged with overlay)
  snapshot.tar.gz  frozen upstream archive
  sealed.zip       immutable sealed archive (written by seal_workspace_ree)
  .workspace.json  session metadata
  manifest.json    sealed REE spec sidecar
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.receipts import build_consistency_report, published_receipts
from repo2ree_core.ree_scripts.reproducer import (
    reproducer_entries,
    runtime_artifact_basename_from_remap,
)
from repo2ree_core.source_repo import derive_source_repo_metadata
from repo2ree_core.storage.layout import (
    ReeLayout,
    normalize_workspace_path,
    validate_relative_path,
)
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.workspace.bundle import (
    REE_ARTIFACTS_PREFIX,
    REE_MANIFEST_ENTRY_PATH,
    REE_OVERLAY_PREFIX,
    REE_RECEIPTS_PREFIX,
    REE_RESULTS_PREFIX,
    REE_SNAPSHOT_ENTRY_PATH,
    REE_WORKSPACE_DIR_ENTRY,
    ArtifactPlan,
    build_zip_bytes,
    plan_artifact_layout,
    rewrite_manifest_for_bundle,
    should_include_snapshot,
)
from repo2ree_core.workspace.inventory import (
    classify_file_kind,
    is_reserved_workspace_filename,
    should_inline_file_content,
)


# Deferred import to break the storage → workspace_ops → manifest → storage cycle.
def _build_manifest_payload(
    intent: Any,
    session: Any,
    *,
    ree_id: str,
    consistency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from repo2ree_core.workspace.manifest import build_manifest_payload

    return build_manifest_payload(intent, session, ree_id=ree_id, consistency=consistency)


def _build_draft_manifest_payload(
    metadata: dict[str, Any],
    *,
    workspace_files: list[dict[str, Any]],
    ree_files: list[dict[str, Any]],
) -> dict[str, Any]:
    from repo2ree_core.workspace.manifest import build_draft_manifest_payload

    return build_draft_manifest_payload(
        metadata,
        workspace_files=workspace_files,
        ree_files=ree_files,
    )


# ================================================
# Internal Helpers
# ================================================


def _layout(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def _store(storage_root: Path, ree_id: str) -> ReeStore:
    return ReeStore(_layout(storage_root, ree_id))


def _validate_user_path(path: str) -> str:
    normalized = normalize_workspace_path(path)
    validate_relative_path(normalized)
    if is_reserved_workspace_filename(PurePosixPath(normalized).name):
        raise ValueError("Invalid workspace path")
    return normalized


def _read_metadata(storage_root: Path, ree_id: str) -> dict[str, Any]:
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    return store.read_metadata_json()


def _list_tree_relpaths(root: Path) -> list[str]:
    """Sorted POSIX relative paths of every file beneath ``root`` (shell)."""
    if not root.is_dir():
        return []
    return sorted(fp.relative_to(root).as_posix() for fp in root.rglob("*") if fp.is_file())


def _build_artifact_plan(layout: ReeLayout, intent: Any, *, include_runtime: bool) -> ArtifactPlan:
    """Snapshot disk state and delegate layout decisions to the pure planner."""
    workspace_files = frozenset(_list_tree_relpaths(layout.workspace))
    on_disk_artifacts = _list_tree_relpaths(layout.artifacts)
    return plan_artifact_layout(
        on_disk_artifact_relpaths=on_disk_artifacts,
        workspace_runtime_path=intent.runtime,
        workspace_sbom_path=intent.sbom,
        workspace_files=workspace_files,
        runtime_included=include_runtime,
    )


def _reproducer_entries(intent: Any, artifact_plan: ArtifactPlan) -> list[tuple[str, bytes]]:
    """Top-level ``run.sh`` + ``REPRODUCING.md`` derived from author intent."""
    return reproducer_entries(
        activation_script=intent.activation.run_script,
        activation_verify_script=intent.activation.verify_script,
        experiments=[(e.name, e.run_script, e.verify_script) for e in intent.experiments],
        runtime_workspace_path=intent.runtime,
        runtime_artifact_basename=runtime_artifact_basename_from_remap(intent.runtime, artifact_plan.manifest_remap),
        origin_url=intent.origin_url or "",
        source_type=intent.source_type or "",
        revision=intent.revision or "",
        swhid=intent.swhid or "",
    )


def _bundle_entry_partition(
    layout: ReeLayout,
    artifact_plan: ArtifactPlan,
    intent: Any,
    *,
    include_snapshot: bool,
    results_included: bool,
) -> tuple[list[tuple[str, bytes]], list[tuple[str, bytes]]]:
    """Read the file-heavy bundle entries, split around the manifest slot (shell).

    Returns ``(head, tail)`` — the entries that precede and follow the manifest
    entry, respectively. The manifest is the only entry that differs between the
    pre-seal digest pass and the final sealed bundle, so callers that build both
    can read every file once here and re-stamp only the manifest between them.
    """
    head: list[tuple[str, bytes]] = list(_reproducer_entries(intent, artifact_plan))
    tail: list[tuple[str, bytes]] = []
    if include_snapshot and layout.snapshot_archive.exists():
        tail.append((REE_SNAPSHOT_ENTRY_PATH, layout.snapshot_archive.read_bytes()))
    tail.append((REE_OVERLAY_PREFIX, b""))
    for rel in _list_tree_relpaths(layout.overlay):
        tail.append((f"{REE_OVERLAY_PREFIX}{rel}", (layout.overlay / rel).read_bytes()))
    tail.append((REE_ARTIFACTS_PREFIX, b""))
    for rel in artifact_plan.on_disk_relpaths:
        tail.append((f"{REE_ARTIFACTS_PREFIX}{rel}", (layout.artifacts / rel).read_bytes()))
    for ws_rel, archive_name in sorted(artifact_plan.workspace_pulls.items()):
        tail.append(
            (
                f"{REE_ARTIFACTS_PREFIX}{archive_name}",
                (layout.workspace / ws_rel).read_bytes(),
            )
        )
    tail.append((REE_RECEIPTS_PREFIX, b""))
    for receipt in published_receipts(layout, intent):
        receipt_path = layout.run_receipt(receipt.run_id)
        if receipt_path.is_file():
            tail.append((f"{REE_RECEIPTS_PREFIX}{receipt_path.name}", receipt_path.read_bytes()))
    # Produced-results baselines, packaged only when the seal opted results into
    # the bundle (a seal-time choice, like source/runtime). Emitted only when a
    # captured store actually has content, so a results-excluded seal — or one
    # with no captured results — is byte-for-byte unchanged (no empty dir entry).
    result_entries: list[tuple[str, bytes]] = []
    if results_included:
        for experiment in getattr(intent, "experiments", []):
            if not experiment.name:
                continue
            results_dir = layout.results_dir(experiment.name)
            for rel in _list_tree_relpaths(results_dir):
                result_entries.append(
                    (f"{REE_RESULTS_PREFIX}{experiment.name}/{rel}", (results_dir / rel).read_bytes())
                )
    if result_entries:
        tail.append((REE_RESULTS_PREFIX, b""))
        tail.extend(result_entries)
    tail.append((REE_WORKSPACE_DIR_ENTRY, b""))
    return head, tail


def _entries_with_manifest(
    head: list[tuple[str, bytes]],
    tail: list[tuple[str, bytes]],
    manifest_bytes: bytes,
) -> list[tuple[str, bytes]]:
    """Splice the manifest entry into its fixed slot between head and tail."""
    return [*head, (REE_MANIFEST_ENTRY_PATH, manifest_bytes), *tail]


def _entries_digest(entries: list[tuple[str, bytes]]) -> str:
    """Content digest over the bundle entry list (paths + bytes), unbuilt.

    Hashing the entries directly gives a stable content address without paying to
    deflate a throwaway ZIP. Path and length are folded in with delimiters so no
    two distinct entry lists can collide by concatenation.
    """
    hasher = hashlib.sha256()
    for archive_path, content in entries:
        hasher.update(archive_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(len(content).to_bytes(8, "big"))
        hasher.update(content)
    return hasher.hexdigest()


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _iter_workspace_files(store: ReeStore):
    """Yield every regular file in the materialized workspace/ subtree."""
    root = store.layout.workspace
    if not root.exists():
        raise FileNotFoundError(f"REE {store.layout.root.name} not found")
    yield from (p for p in sorted(root.rglob("*")) if p.is_file())


def _workspace_files_with_content(storage_root: Path, ree_id: str) -> list[dict[str, Any]]:
    store = _store(storage_root, ree_id)
    root = store.layout.workspace
    # Provenance: files present in overlay/ are user-added or tool-generated
    # recipe files; everything else came from the immutable upstream source.
    # The merged workspace flattens both, so we recover the origin here.
    overlay_rels = {rel.as_posix() for rel in store.overlay.iter_files()}
    entries: list[dict[str, Any]] = []
    for fp in _iter_workspace_files(store):
        rel = fp.relative_to(root).as_posix()
        size = fp.stat().st_size
        entries.append(
            {
                "path": rel,
                "kind": "generated" if rel in overlay_rels else classify_file_kind(rel),
                "size": size,
                "content": (_read_text_if_possible(fp) if should_inline_file_content(rel, size) else None),
            }
        )
    return entries


_REE_SUBTREE_TAGS: dict[str, str] = {
    "upstream": "Upstream",
    "overlay": "Overlay",
    "artifacts": "Artifact",
    "workspace": "Workspace",
}


def _ree_file_tag(rel: str) -> str:
    if rel == "manifest.json":
        return "Manifest"
    if rel.endswith(".zip") or rel.endswith(".tar.gz"):
        return "Archive"
    top, _, _ = rel.partition("/")
    return _REE_SUBTREE_TAGS.get(top, "REE")


def _workspace_ree_files_with_content(storage_root: Path, ree_id: str) -> list[dict[str, Any]]:
    """Enumerate every file under the REE root, mirroring the on-disk layout."""
    layout = _layout(storage_root, ree_id)
    ree_root = layout.root
    if not ree_root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    ree_files: list[dict[str, Any]] = []
    for fp in sorted(ree_root.rglob("*")):
        if not fp.is_file():
            continue
        if is_reserved_workspace_filename(fp.name):
            continue
        rel_path = fp.relative_to(ree_root)
        if any(part.startswith(".upload.") for part in rel_path.parts):
            continue
        rel = rel_path.as_posix()
        size = fp.stat().st_size
        content = _read_text_if_possible(fp) if should_inline_file_content(rel, size) else None
        ree_files.append(
            {
                "path": rel,
                "kind": "ree",
                "tag": _ree_file_tag(rel),
                "size": size,
                "content": content,
            }
        )
    return ree_files


# ================================================
# Public Operations
# ================================================


def get_workspace(storage_root: Path, ree_id: str) -> dict[str, Any]:
    metadata = _read_metadata(storage_root, ree_id)
    intent = ReeIntent.from_metadata(metadata)
    session = ReeSession.from_metadata(metadata)
    detail = dict(metadata)
    files = _workspace_files_with_content(storage_root, ree_id)
    ree_files = _workspace_ree_files_with_content(storage_root, ree_id)
    detail["files"] = files
    detail["reeFiles"] = ree_files
    detail["draftManifest"] = _build_draft_manifest_payload(
        metadata,
        workspace_files=files,
        ree_files=ree_files,
    )
    detail["sourceRepo"] = derive_source_repo_metadata(intent, session, files).model_dump(by_alias=True)
    # Live per-step staleness (recorded receipts vs. the current tree): saving
    # a script flips the derived state on the next fetch — no invalidation
    # events needed.
    detail["consistency"] = build_consistency_report(_layout(storage_root, ree_id), intent, session)
    return detail


def read_file_bytes(storage_root: Path, ree_id: str, path: str) -> bytes:
    normalized = _validate_user_path(path)
    fp = _layout(storage_root, ree_id).workspace_file(normalized)
    if not fp.exists() or not fp.is_file():
        raise FileNotFoundError(path)
    return fp.read_bytes()


def _assemble_bundle(
    layout: ReeLayout,
    intent: Any,
    session: Any,
    *,
    ree_id: str,
) -> tuple[bytes, dict[str, Any]]:
    """Build the ZIP bytes and sidecar manifest from settled intent + session.

    The session must already carry the desired source_included/runtime_included
    (and sealed_at/seal_hash when building the final sealed bundle).
    Returns ``(zip_bytes, sidecar_manifest)``.
    """
    artifact_plan = _build_artifact_plan(layout, intent, include_runtime=session.runtime_included)
    include_snapshot = should_include_snapshot(
        source_included=session.source_included,
        source_snapshot_archive=session.source_snapshot_archive,
    )
    sidecar_manifest, manifest_bytes = _manifest_entry_bytes(intent, session, artifact_plan, ree_id=ree_id)
    head, tail = _bundle_entry_partition(
        layout,
        artifact_plan,
        intent,
        include_snapshot=include_snapshot,
        results_included=session.results_included,
    )
    entries = _entries_with_manifest(head, tail, manifest_bytes)
    return build_zip_bytes(entries), sidecar_manifest


def _manifest_entry_bytes(
    intent: Any,
    session: Any,
    artifact_plan: ArtifactPlan,
    *,
    ree_id: str,
    consistency: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Build the sidecar manifest and its bundle-remapped, serialized bytes.

    Returns ``(sidecar_manifest, manifest_bytes)``. The sidecar is what gets
    persisted alongside the archive; the bytes are what get embedded in it.
    """
    sidecar_manifest = _build_manifest_payload(intent, session, ree_id=ree_id, consistency=consistency)
    bundle_manifest = rewrite_manifest_for_bundle(sidecar_manifest, artifact_plan.manifest_remap)
    manifest_bytes = json.dumps(bundle_manifest, indent=2, sort_keys=True).encode("utf-8")
    return sidecar_manifest, manifest_bytes


def seal_workspace_ree(
    storage_root: Path,
    ree_id: str,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
    sealed_at: str,
) -> dict[str, Any]:
    """Build, hash, and persist the sealed REE archive.

    1. Reads every bundle entry once; hashes the entry list (with seal stamps
       stripped from the manifest) to obtain a stable content digest.
    2. Re-stamps only the manifest with the real seal_hash and builds the ZIP once.
    3. Writes sealed.zip, manifest.json, and updates reeSession in metadata.

    Returns the settled seal facts.
    """
    layout = _layout(storage_root, ree_id)
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    intent = store.read_intent()
    session = store.read_session().with_packaging(
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )

    # Per-step freshness of the recorded run receipts against the tree being
    # sealed. Sealing over stale results proceeds — the staleness is recorded
    # in the manifest (and bundled receipts) so it is diagnosable later.
    consistency = build_consistency_report(layout, intent, session)

    # The artifact plan and all file-heavy entries are identical across the
    # pre-seal digest and the final bundle — only the manifest differs — so read
    # every file exactly once here.
    artifact_plan = _build_artifact_plan(layout, intent, include_runtime=session.runtime_included)
    include_snapshot = should_include_snapshot(
        source_included=session.source_included,
        source_snapshot_archive=session.source_snapshot_archive,
    )
    head, tail = _bundle_entry_partition(
        layout,
        artifact_plan,
        intent,
        include_snapshot=include_snapshot,
        results_included=session.results_included,
    )

    # Pre-pass digest: hash the entry list directly (no throwaway ZIP build).
    # Strip any previously persisted seal stamps so re-sealing produces the
    # same digest when content hasn't changed.
    preseal_session = session.model_copy(update={"sealed_at": None, "seal_hash": None})
    _, preseal_manifest_bytes = _manifest_entry_bytes(
        intent, preseal_session, artifact_plan, ree_id=ree_id, consistency=consistency
    )
    preseal_entries = _entries_with_manifest(head, tail, preseal_manifest_bytes)
    seal_hash = f"sha256:{_entries_digest(preseal_entries)}"

    # Settle all four seal facts into the session.
    session = session.with_seal(
        sealed_at=sealed_at,
        seal_hash=seal_hash,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )

    # Final assembly with the real seal_hash in the manifest; ZIP built once.
    sidecar_manifest, manifest_bytes = _manifest_entry_bytes(
        intent, session, artifact_plan, ree_id=ree_id, consistency=consistency
    )
    zip_bytes = build_zip_bytes(_entries_with_manifest(head, tail, manifest_bytes))

    # Persist everything atomically within the workbench lock (held by caller).
    layout.sealed_archive.write_bytes(zip_bytes)
    store.write_manifest(sidecar_manifest)
    store.write_session(session)

    return {
        "sealedAt": session.sealed_at,
        "sealHash": session.seal_hash,
        "sourceIncluded": session.source_included,
        "runtimeIncluded": session.runtime_included,
        "consistency": consistency,
    }


def build_workspace_ree_archive(storage_root: Path, ree_id: str) -> bytes:
    """Return the sealed archive bytes.

    Raises RuntimeError if the REE has not been sealed yet.
    """
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    if not store.read_session().is_sealed:
        raise RuntimeError("REE is not sealed")
    layout = _layout(storage_root, ree_id)
    if not layout.sealed_archive.exists():
        raise RuntimeError("Sealed archive file not found; please re-seal")
    return layout.sealed_archive.read_bytes()
