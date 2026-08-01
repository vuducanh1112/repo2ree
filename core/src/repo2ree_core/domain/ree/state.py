from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.primitives import Digest, GitRevision, ReePath, UtcInstant

# ================================================
# Types
# ================================================

SourceAcquiredBy = Literal["", "download", "upload"]


# ================================================
# Data Models
# ================================================


class ReeLifecycleState(BaseModel):
    """Durable lifecycle facts produced while authoring and publishing an REE.

    This replaces the ambiguous ``ReeSession`` name: the values survive
    processes and workbench sessions and are part of the persisted REE record.
    Mutations remain pure and are applied by the persistence boundary.
    """

    model_config = ConfigDict(extra="forbid")

    dependency_level: int = 0
    environment_level: int = 0
    machine_level: int = 0
    # Machine-produced summary of the dependencies detected during evaluation;
    # settled alongside the reproducibility levels, never author-declared.
    detected_dependencies: str | None = None
    sealed_at: UtcInstant | None = None
    seal_hash: Digest | None = None
    source_available: bool = False
    source_acquired_by: SourceAcquiredBy = ""
    source_resolved_commit: GitRevision | None = None
    uploaded_archive: ReePath | None = None
    source_snapshot_archive: ReePath | None = None
    source_snapshot_captured_at: UtcInstant | None = None
    # Content digest of the snapshot archive, recorded while it is written.
    # The chain root of every step's input slice (see ``repo2ree_core.evidence.consistency``).
    source_snapshot_digest: Digest | None = None
    # Packaging facts settled at bundle time and recorded in the published
    # manifest. Unset while authoring (inclusion is a download-time choice);
    # populated when reconstructing a state from an uploaded manifest.
    source_included: bool = False
    runtime_included: bool = False
    results_included: bool = False


def record_source(
    state: ReeLifecycleState,
    *,
    acquired_by: SourceAcquiredBy,
    archive_name: ReePath | None = None,
    snapshot_archive: ReePath | None = None,
    snapshot_captured_at: UtcInstant | None = None,
    resolved_commit: GitRevision | None = None,
) -> ReeLifecycleState:
    return state.model_copy(
        update={
            "source_available": True,
            "source_acquired_by": acquired_by,
            "source_resolved_commit": resolved_commit or None,
            "uploaded_archive": archive_name or state.uploaded_archive,
            "source_snapshot_archive": snapshot_archive or state.source_snapshot_archive or None,
            "source_snapshot_captured_at": snapshot_captured_at or state.source_snapshot_captured_at,
        }
    )


def remove_source(state: ReeLifecycleState) -> ReeLifecycleState:
    """Drop every source fact while preserving unrelated machine facts."""
    return state.model_copy(
        update={
            "source_available": False,
            "source_acquired_by": "",
            "source_resolved_commit": None,
            "uploaded_archive": None,
            "source_snapshot_archive": None,
            "source_snapshot_captured_at": None,
            "source_snapshot_digest": None,
            "source_included": False,
        }
    )


def record_snapshot_digest(state: ReeLifecycleState, digest: Digest | None) -> ReeLifecycleState:
    return state.model_copy(update={"source_snapshot_digest": digest or None})


def record_evaluation(
    state: ReeLifecycleState,
    *,
    dependency_level: int,
    environment_level: int,
    machine_level: int,
    detected_dependencies: str,
) -> ReeLifecycleState:
    return state.model_copy(
        update={
            "dependency_level": dependency_level,
            "environment_level": environment_level,
            "machine_level": machine_level,
            "detected_dependencies": detected_dependencies,
        }
    )


def is_sealed(state: ReeLifecycleState) -> bool:
    return bool(state.sealed_at and state.seal_hash)


def select_packaging(
    state: ReeLifecycleState,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> ReeLifecycleState:
    return state.model_copy(
        update={
            "source_included": source_included,
            "runtime_included": runtime_included,
            "results_included": results_included,
        }
    )


def record_seal(
    state: ReeLifecycleState,
    *,
    sealed_at: UtcInstant,
    seal_hash: Digest,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> ReeLifecycleState:
    return state.model_copy(
        update={
            "sealed_at": sealed_at,
            "seal_hash": seal_hash,
            "source_included": source_included,
            "runtime_included": runtime_included,
            "results_included": results_included,
        }
    )
