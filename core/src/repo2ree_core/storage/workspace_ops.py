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
import shutil
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.receipts import (
    ConsistencyReport,
    author_receipt_path,
    build_author_receipt_set,
    build_consistency_report,
    load_author_receipts,
    published_receipts,
)
from repo2ree_core.ree_scripts.reproducer import (
    reproducer_entries,
    runtime_artifact_basename_from_remap,
)
from repo2ree_core.ree_steps import build_ree_step_states
from repo2ree_core.source_repo import derive_source_repo_metadata
from repo2ree_core.storage.layout import (
    ReeLayout,
    normalize_workspace_path,
    validate_relative_path,
)
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import utc_now
from repo2ree_core.workspace.bundle import (
    REE_ARTIFACTS_PREFIX,
    REE_AUTHOR_RECEIPTS_PREFIX,
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
    ReeFile,
    WorkspaceFile,
    classify_file_kind,
    is_reserved_workspace_filename,
    should_inline_file_content,
)
from repo2ree_core.workspace.model import WorkspaceMetadata


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


def _split_manifest_payload(payload: dict[str, Any]) -> tuple[Any, Any]:
    from repo2ree_core.workspace.manifest import split_manifest_payload

    return split_manifest_payload(payload)


def _build_draft_manifest_payload(
    metadata: WorkspaceMetadata,
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


def _read_metadata(storage_root: Path, ree_id: str) -> WorkspaceMetadata:
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    return store.read_metadata()


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
    tail.append((REE_AUTHOR_RECEIPTS_PREFIX, b""))
    for receipt in published_receipts(layout, intent):
        receipt_path = author_receipt_path(layout, receipt)
        if receipt_path.is_file():
            relative = receipt_path.relative_to(layout.author_receipts).as_posix()
            tail.append((f"{REE_AUTHOR_RECEIPTS_PREFIX}{relative}", receipt_path.read_bytes()))
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


def _iter_workspace_files(store: ReeStore) -> Iterator[Path]:
    """Yield every regular file in the materialized workspace/ subtree."""
    root = store.layout.workspace
    if not root.exists():
        raise FileNotFoundError(f"REE {store.layout.root.name} not found")
    yield from (p for p in sorted(root.rglob("*")) if p.is_file())


def _workspace_files_with_content(
    storage_root: Path,
    ree_id: str,
    *,
    include_content: bool = True,
) -> list[dict[str, Any]]:
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
        entry = WorkspaceFile(
            path=rel,
            kind="generated" if rel in overlay_rels else classify_file_kind(rel),
            size=size,
            content=(_read_text_if_possible(fp) if should_inline_file_content(rel, size) else None)
            if include_content
            else None,
        )
        entries.append(entry.model_dump())
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


def _workspace_ree_files_with_content(
    storage_root: Path,
    ree_id: str,
    *,
    include_content: bool = True,
) -> list[dict[str, Any]]:
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
        entry = ReeFile(
            path=rel,
            tag=_ree_file_tag(rel),
            size=size,
            content=(_read_text_if_possible(fp) if should_inline_file_content(rel, size) else None)
            if include_content
            else None,
        )
        ree_files.append(entry.model_dump())
    return ree_files


# ================================================
# Public Operations
# ================================================


def get_workspace(storage_root: Path, ree_id: str, *, include_content: bool = True) -> dict[str, Any]:
    metadata = _read_metadata(storage_root, ree_id)
    intent = metadata.ree_intent
    session = metadata.ree_session
    detail: dict[str, Any] = metadata.model_dump()
    files = _workspace_files_with_content(storage_root, ree_id, include_content=include_content)
    ree_files = _workspace_ree_files_with_content(storage_root, ree_id, include_content=include_content)
    detail["files"] = files
    detail["ree_files"] = ree_files
    detail["draft_manifest"] = _build_draft_manifest_payload(
        metadata,
        workspace_files=files,
        ree_files=ree_files,
    )
    detail["source_repo"] = derive_source_repo_metadata(intent, session, files).model_dump()
    # Live per-step staleness (recorded receipts vs. the current tree): saving
    # a script flips the derived state on the next fetch — no invalidation
    # events needed.
    layout = _layout(storage_root, ree_id)
    consistency = build_consistency_report(layout, intent, session)
    detail["consistency"] = consistency.model_dump()
    detail["author_receipts"] = build_author_receipt_set(layout, intent, session).model_dump()
    # Operational overlay — done / ready / blocked per authoring step. Completion
    # is "a successful run is recorded" (the receipt-step keys), matching the
    # frontend badges and the scorecard; staleness stays on the consistency
    # report above. Evaluate records no receipt, so its report artifact is the
    # signal the receipt keys can't carry.
    completed_run_steps = set(load_author_receipts(layout))
    detail["ree_steps"] = [
        state.model_dump()
        for state in build_ree_step_states(
            intent,
            session,
            completed_run_steps=completed_run_steps,
            evaluate_report_present=(layout.artifacts / "reproducibility-report.json").is_file(),
        )
    ]
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


class SealOutputs(BaseModel):
    """The settled seal facts reported by :func:`seal_workspace_ree`."""

    model_config = ConfigDict(extra="forbid")

    sealed_at: str | None
    seal_hash: str | None
    source_included: bool
    runtime_included: bool
    consistency: ConsistencyReport


def reset_source_state(*, layout: ReeLayout, store: ReeStore) -> None:
    """Clear source-derived state while preserving REE identity metadata.

    Upload staging and run logs are intentionally left alone: staging is the
    handoff into the source pipeline, and logs are operational history.
    """
    for subtree in (store.upstream, store.overlay, store.artifacts, store.workspace):
        subtree.clear()
        subtree.ensure_root()
    store.ensure_reserved_overlay_scripts()
    shutil.rmtree(layout.author_receipts, ignore_errors=True)
    layout.author_receipts.mkdir(parents=True, exist_ok=True)

    for path in (
        layout.snapshot_archive,
        layout.acquire_script,
        layout.materialize_script,
        layout.manifest,
        layout.sealed_archive,
    ):
        path.unlink(missing_ok=True)

    meta = store.read_metadata()
    cleared_intent = ReeIntent(
        name=meta.ree_intent.name,
        catalog_metadata=meta.ree_intent.catalog_metadata,
    )
    updated = meta.model_copy(
        update={
            "ree_intent": cleared_intent,
            "ree_session": ReeSession(),
            "status": "draft",
            "updated_at": utc_now(),
            "external_ref": None,
        }
    )
    store.write_metadata(updated)


def seal_workspace_ree(
    storage_root: Path,
    ree_id: str,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
    sealed_at: str,
) -> SealOutputs:
    """Build, hash, and persist the sealed REE archive.

    1. Reads every bundle entry once; hashes the entry list (with seal stamps
       stripped from the manifest) to obtain a stable content digest.
    2. Re-stamps only the manifest with the real seal_hash and builds the ZIP once.
    3. Writes sealed.zip, manifest.json, and updates the session in metadata.

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
    consistency_report = build_consistency_report(layout, intent, session)
    consistency = consistency_report.model_dump()

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

    return SealOutputs(
        sealed_at=session.sealed_at,
        seal_hash=session.seal_hash,
        source_included=session.source_included,
        runtime_included=session.runtime_included,
        consistency=consistency_report,
    )


def build_workspace_ree_archive(storage_root: Path, ree_id: str) -> bytes:
    """Return the REE's downloadable bundle bytes.

    A sealed REE hands back the immutable ``sealed.zip`` it was sealed into —
    the bytes the seal hash covers. An unsealed REE is assembled on demand
    into a *draft* bundle: the same layout, carrying everything it currently
    has (source, runtime, results), but with no seal stamps in its manifest.
    Draft bundles exist so work in progress can be handed to another workbench
    (see ``load_ree_bundle``); only a sealed bundle is a citable artifact.
    """
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    layout = _layout(storage_root, ree_id)
    session = store.read_session()
    if not session.is_sealed:
        zip_bytes, _ = _assemble_bundle(
            layout,
            store.read_intent(),
            session.with_packaging(source_included=True, runtime_included=True, results_included=True),
            ree_id=ree_id,
        )
        return zip_bytes
    if not layout.sealed_archive.exists():
        raise RuntimeError("Sealed archive file not found; please re-seal")
    return layout.sealed_archive.read_bytes()


class BundleLoadOutputs(BaseModel):
    """What loading a bundle put into the REE."""

    model_config = ConfigDict(extra="forbid")

    name: str
    sealed: bool
    seal_hash: str | None
    source_restored: bool
    overlay_files: int
    artifact_files: int
    author_receipts: int


def restore_ree_bundle(
    storage_root: Path,
    ree_id: str,
    *,
    bundle_root: Path,
    archive_path: Path,
) -> BundleLoadOutputs:
    """Replace this REE's contents with an extracted bundle's (shell).

    The inverse of :func:`seal_workspace_ree` / :func:`build_workspace_ree_archive`:
    ``bundle_root`` is the already-extracted (and path-checked) bundle tree, so
    every path read here is trusted; ``archive_path`` is the ZIP it came from.
    Everything the bundle publishes is restored to the on-disk home it was
    packaged from — snapshot, overlay, artifacts,
    results, and the selected author receipts — while ``upstream/`` and
    ``workspace/`` stay empty: they are derived, and the caller rebuilds them
    from the restored snapshot.

    Artifacts land under ``artifacts/`` (where the seal reads them), not in the
    workspace: a loaded REE carries the author's built outputs as *evidence*,
    and a reviewer's own build writes its own. A bundle with no snapshot leaves
    the source facts cleared — the origin is still on the intent, so the source
    can be acquired (or reviewed) from it.
    """
    store = _store(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    manifest_path = bundle_root / REE_MANIFEST_ENTRY_PATH
    if not manifest_path.is_file():
        raise ValueError(f"not an REE bundle: missing {REE_MANIFEST_ENTRY_PATH}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    intent, session = _split_manifest_payload(manifest)

    layout = _layout(storage_root, ree_id)
    store.ensure_dirs()
    # A load is a whole-REE replacement, so it starts from the same cleared
    # state a source change does, plus the derived caches and produced results
    # that only a full replacement invalidates.
    reset_source_state(layout=layout, store=store)
    shutil.rmtree(layout.results, ignore_errors=True)
    for stale in (layout.digest_cache, layout.materialize_marker):
        stale.unlink(missing_ok=True)

    source_restored = _restore_file(bundle_root / REE_SNAPSHOT_ENTRY_PATH, layout.snapshot_archive)
    overlay_files = _restore_tree(bundle_root / REE_OVERLAY_PREFIX, layout.overlay)
    artifact_files = _restore_tree(bundle_root / REE_ARTIFACTS_PREFIX, layout.artifacts)
    _restore_tree(bundle_root / REE_RESULTS_PREFIX, layout.results)
    author_receipts = _restore_tree(bundle_root / REE_AUTHOR_RECEIPTS_PREFIX, layout.author_receipts)

    if not source_restored:
        session = session.without_source()
    store.write_intent(intent)
    store.write_session(session)
    if session.is_sealed:
        # The uploaded bytes *are* the sealed archive the seal hash covers, so
        # the loaded REE can hand back the identical download.
        shutil.copyfile(archive_path, layout.sealed_archive)
        store.write_manifest(manifest)

    return BundleLoadOutputs(
        name=intent.name,
        sealed=session.is_sealed,
        seal_hash=session.seal_hash,
        source_restored=source_restored,
        overlay_files=overlay_files,
        artifact_files=artifact_files,
        author_receipts=author_receipts,
    )


def _restore_file(source: Path, target: Path) -> bool:
    """Copy a single bundle entry into place. False when the bundle omits it."""
    if not source.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def _restore_tree(source: Path, target: Path) -> int:
    """Copy a bundle subtree into place, returning how many files it held."""
    if not source.is_dir():
        return 0
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    return len(_list_tree_relpaths(source))
