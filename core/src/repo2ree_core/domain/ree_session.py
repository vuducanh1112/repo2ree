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


class ReeSession(BaseModel):
    """Legacy machine-state projection transformed only by pure functions."""

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
    # The chain root of every step's input slice (see ``repo2ree_core.evidence.receipts``).
    source_snapshot_digest: Digest | None = None
    # Packaging facts settled at bundle time and recorded in the published
    # manifest. Unset while authoring (inclusion is a download-time choice);
    # populated when reconstructing a session from an uploaded manifest.
    source_included: bool = False
    runtime_included: bool = False
    results_included: bool = False


def record_source(
    session: ReeSession,
    *,
    acquired_by: SourceAcquiredBy,
    archive_name: ReePath | None = None,
    snapshot_archive: ReePath | None = None,
    snapshot_captured_at: UtcInstant | None = None,
    resolved_commit: GitRevision | None = None,
) -> ReeSession:
    return session.model_copy(
        update={
            "source_available": True,
            "source_acquired_by": acquired_by,
            "source_resolved_commit": resolved_commit or None,
            "uploaded_archive": archive_name or session.uploaded_archive,
            "source_snapshot_archive": snapshot_archive or session.source_snapshot_archive or None,
            "source_snapshot_captured_at": snapshot_captured_at or session.source_snapshot_captured_at,
        }
    )


def remove_source(session: ReeSession) -> ReeSession:
    """Drop every source fact while preserving unrelated machine facts."""
    return session.model_copy(
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


def record_snapshot_digest(session: ReeSession, digest: Digest | None) -> ReeSession:
    return session.model_copy(update={"source_snapshot_digest": digest or None})


def record_evaluation(
    session: ReeSession,
    *,
    dependency_level: int,
    environment_level: int,
    machine_level: int,
    detected_dependencies: str,
) -> ReeSession:
    return session.model_copy(
        update={
            "dependency_level": dependency_level,
            "environment_level": environment_level,
            "machine_level": machine_level,
            "detected_dependencies": detected_dependencies,
        }
    )


def is_sealed(session: ReeSession) -> bool:
    return bool(session.sealed_at and session.seal_hash)


def select_packaging(
    session: ReeSession,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> ReeSession:
    return session.model_copy(
        update={
            "source_included": source_included,
            "runtime_included": runtime_included,
            "results_included": results_included,
        }
    )


def record_seal(
    session: ReeSession,
    *,
    sealed_at: UtcInstant,
    seal_hash: Digest,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> ReeSession:
    return session.model_copy(
        update={
            "sealed_at": sealed_at,
            "seal_hash": seal_hash,
            "source_included": source_included,
            "runtime_included": runtime_included,
            "results_included": results_included,
        }
    )
