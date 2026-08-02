"""Assembling an REE into its bundle archive, and sealing that archive.

Imperative shell: reads the REE tree through :class:`ReeLayout` /
:class:`ReeDirectory` and writes ``sealed.zip`` and ``manifest.json``. Layout
decisions belong to the pure planner in ``bundle.plan``; this module supplies
the bytes and persists the result.

Sealing is what makes an REE citable: the archive is hashed, the hash is
stamped into the manifest, and the same bytes are handed back on every
subsequent download. An *unsealed* REE can still be bundled — a draft bundle,
same layout, no seal stamps — so work in progress can move between workbenches.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from repo2ree_core.authoring.script_generation.reproducer import (
    reproducer_entries,
    runtime_artifact_basename_from_remap,
)
from repo2ree_core.bundle.manifest import build_manifest_payload
from repo2ree_core.bundle.plan import (
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
from repo2ree_core.domain.primitives import Digest, UtcInstant
from repo2ree_core.domain.ree.state import is_sealed, select_packaging
from repo2ree_core.domain.ree.transitions import prepare_seal, record_seal
from repo2ree_core.evidence.consistency import ConsistencyReport, build_consistency_report
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import list_tree_relpaths, write_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.receipts import author_receipt_path, published_receipts
from repo2ree_core.persistence.repository import directory_for, layout_for, load_ree


class SealOutputs(BaseModel):
    """The settled seal facts reported by :func:`seal_ree`."""

    model_config = ConfigDict(extra="forbid")

    sealed_at: UtcInstant | None
    seal_hash: Digest | None
    source_included: bool
    runtime_included: bool
    consistency: ConsistencyReport


# ================================================
# Entry Assembly
# ================================================


def _build_artifact_plan(layout: ReeLayout, intent: Any, *, include_runtime: bool) -> ArtifactPlan:
    """Snapshot disk state and delegate layout decisions to the pure planner."""
    workspace_files = frozenset(list_tree_relpaths(layout.workspace))
    on_disk_artifacts = list_tree_relpaths(layout.artifacts)
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
    tail.extend(
        (f"{REE_OVERLAY_PREFIX}{rel}", (layout.overlay / rel).read_bytes())
        for rel in list_tree_relpaths(layout.overlay)
    )
    tail.append((REE_ARTIFACTS_PREFIX, b""))
    tail.extend(
        (f"{REE_ARTIFACTS_PREFIX}{rel}", (layout.artifacts / rel).read_bytes())
        for rel in artifact_plan.on_disk_relpaths
    )
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
            result_entries.extend(
                (f"{REE_RESULTS_PREFIX}{experiment.name}/{rel}", (results_dir / rel).read_bytes())
                for rel in list_tree_relpaths(results_dir)
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


def _manifest_entry_bytes(
    intent: Any,
    state: Any,
    artifact_plan: ArtifactPlan,
    *,
    ree_id: str,
    consistency: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bytes]:
    """Build the REE-root manifest and its bundle-remapped, serialized bytes.

    Returns ``(ree_manifest, manifest_bytes)``. The first is what gets persisted
    alongside the archive; the bytes are what get embedded in it.
    """
    ree_manifest = build_manifest_payload(intent, state, ree_id=ree_id, consistency=consistency)
    bundle_manifest = rewrite_manifest_for_bundle(ree_manifest, artifact_plan.manifest_remap)
    manifest_bytes = json.dumps(bundle_manifest, indent=2, sort_keys=True).encode("utf-8")
    return ree_manifest, manifest_bytes


def _assemble_bundle(
    layout: ReeLayout,
    intent: Any,
    state: Any,
    *,
    ree_id: str,
) -> tuple[bytes, dict[str, Any]]:
    """Build the ZIP bytes and REE-root manifest from settled intent + state.

    The state must already carry the desired source_included/runtime_included
    (and sealed_at/seal_hash when building the final sealed bundle).
    Returns ``(zip_bytes, ree_manifest)``.
    """
    artifact_plan = _build_artifact_plan(layout, intent, include_runtime=state.runtime_included)
    include_snapshot = should_include_snapshot(
        source_included=state.source_included,
        source_snapshot_archive=state.source_snapshot_archive,
    )
    ree_manifest, manifest_bytes = _manifest_entry_bytes(intent, state, artifact_plan, ree_id=ree_id)
    head, tail = _bundle_entry_partition(
        layout,
        artifact_plan,
        intent,
        include_snapshot=include_snapshot,
        results_included=state.results_included,
    )
    entries = _entries_with_manifest(head, tail, manifest_bytes)
    return build_zip_bytes(entries), ree_manifest


# ================================================
# Public Operations
# ================================================


def seal_ree(
    storage_root: Path,
    ree_id: str,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
    sealed_at: UtcInstant,
) -> SealOutputs:
    """Build, hash, and persist the sealed REE archive.

    1. Reads every bundle entry once; hashes the entry list (with seal stamps
       stripped from the manifest) to obtain a stable content digest.
    2. Re-stamps only the manifest with the real seal_hash and builds the ZIP once.
    3. Writes sealed.zip, manifest.json, and updates the state in the record.

    Returns the settled seal facts.
    """
    layout = layout_for(storage_root, ree_id)
    store = directory_for(storage_root, ree_id)
    if not store.record_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    ree = load_ree(layout, store)
    intent = ree.authored.intent
    state = prepare_seal(
        ree,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    ).evidence.state

    # Per-step freshness of the recorded run receipts against the tree being
    # sealed. Sealing over stale results proceeds — the staleness is recorded
    # in the manifest (and bundled receipts) so it is diagnosable later.
    consistency_report = build_consistency_report(layout, intent, state)
    consistency = consistency_report.model_dump(mode="json")

    # The artifact plan and all file-heavy entries are identical across the
    # pre-seal digest and the final bundle — only the manifest differs — so read
    # every file exactly once here.
    artifact_plan = _build_artifact_plan(layout, intent, include_runtime=state.runtime_included)
    include_snapshot = should_include_snapshot(
        source_included=state.source_included,
        source_snapshot_archive=state.source_snapshot_archive,
    )
    head, tail = _bundle_entry_partition(
        layout,
        artifact_plan,
        intent,
        include_snapshot=include_snapshot,
        results_included=state.results_included,
    )

    # Pre-pass digest: hash the entry list directly (no throwaway ZIP build).
    # Strip any previously persisted seal stamps so re-sealing produces the
    # same digest when content hasn't changed.
    preseal_state = state.model_copy(update={"sealed_at": None, "seal_hash": None})
    _, preseal_manifest_bytes = _manifest_entry_bytes(
        intent, preseal_state, artifact_plan, ree_id=ree_id, consistency=consistency
    )
    preseal_entries = _entries_with_manifest(head, tail, preseal_manifest_bytes)
    seal_hash = Digest(f"sha256:{_entries_digest(preseal_entries)}")

    # Settle all four seal facts into the state.
    state = record_seal(
        ree,
        sealed_at=sealed_at,
        seal_hash=seal_hash,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    ).evidence.state

    # Final assembly with the real seal_hash in the manifest; ZIP built once.
    ree_manifest, manifest_bytes = _manifest_entry_bytes(
        intent, state, artifact_plan, ree_id=ree_id, consistency=consistency
    )
    zip_bytes = build_zip_bytes(_entries_with_manifest(head, tail, manifest_bytes))

    # Three writes, serialized against other writers by the workbench lock the
    # caller holds, and each individually atomic against this process dying
    # between them. The archive goes first: it is the only one of the three that
    # nothing recomputes, so a crash after it leaves a bundle no state claims
    # (recoverable — seal again), while a crash before it would leave a state
    # claiming a seal_hash for an archive that was never written.
    write_atomic(layout.sealed_archive, zip_bytes)
    store.write_manifest(ree_manifest)
    store.write_state(state)

    return SealOutputs(
        sealed_at=state.sealed_at,
        seal_hash=state.seal_hash,
        source_included=state.source_included,
        runtime_included=state.runtime_included,
        consistency=consistency_report,
    )


def build_ree_archive(storage_root: Path, ree_id: str) -> bytes:
    """Return the REE's downloadable bundle bytes.

    A sealed REE hands back the immutable ``sealed.zip`` it was sealed into —
    the bytes the seal hash covers. An unsealed REE is assembled on demand
    into a *draft* bundle: the same layout, carrying everything it currently
    has (source, runtime, results), but with no seal stamps in its manifest.
    Draft bundles exist so work in progress can be handed to another workbench
    (see ``load_ree_bundle``); only a sealed bundle is a citable artifact.
    """
    store: ReeDirectory = directory_for(storage_root, ree_id)
    if not store.record_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    layout = layout_for(storage_root, ree_id)
    state = store.read_state()
    if not is_sealed(state):
        zip_bytes, _ = _assemble_bundle(
            layout,
            store.read_intent(),
            select_packaging(state, source_included=True, runtime_included=True, results_included=True),
            ree_id=ree_id,
        )
        return zip_bytes
    if not layout.sealed_archive.exists():
        raise RuntimeError("Sealed archive file not found; please re-seal")
    return layout.sealed_archive.read_bytes()
