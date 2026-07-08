from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# ================================================
# Types
# ================================================

SourceAcquiredBy = Literal["", "download", "upload"]


# ================================================
# Data Models
# ================================================


class ReeSession(BaseModel):
    """Action-managed session state — mutated only via named transitions, never patched."""

    model_config = ConfigDict(extra="forbid")

    dependency_level: int = 0
    environment_level: int = 0
    machine_level: int = 0
    # Machine-produced summary of the dependencies detected during evaluation;
    # settled alongside the reproducibility levels, never author-declared.
    detected_dependencies: str | None = None
    sealed_at: str | None = None
    seal_hash: str | None = None
    source_available: bool = False
    source_acquired_by: SourceAcquiredBy = ""
    source_resolved_commit: str | None = None
    uploaded_archive: str | None = None
    source_snapshot_archive: str | None = None
    source_snapshot_captured_at: str | None = None
    # Content digest of the snapshot archive, recorded while it is written.
    # The chain root of every step's input slice (see ``repo2ree_core.receipts``).
    source_snapshot_digest: str | None = None
    # Packaging facts settled at bundle time and recorded in the published
    # manifest. Unset while authoring (inclusion is a download-time choice);
    # populated when reconstructing a session from an uploaded manifest.
    source_included: bool = False
    runtime_included: bool = False

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> ReeSession:
        raw = dict(metadata.get("reeSession") or {})
        filtered = {k: v for k, v in raw.items() if k in cls.model_fields}
        return cls.model_validate(filtered)

    def with_source(
        self,
        *,
        acquired_by: SourceAcquiredBy,
        archive_name: str | None = None,
        snapshot_archive: str | None = None,
        snapshot_captured_at: str | None = None,
        resolved_commit: str | None = None,
    ) -> ReeSession:
        return self.model_copy(
            update={
                "source_available": True,
                "source_acquired_by": acquired_by,
                "source_resolved_commit": resolved_commit or None,
                "uploaded_archive": archive_name or self.uploaded_archive,
                "source_snapshot_archive": snapshot_archive or self.source_snapshot_archive or None,
                "source_snapshot_captured_at": snapshot_captured_at or self.source_snapshot_captured_at,
            }
        )

    def with_snapshot_digest(self, digest: str | None) -> ReeSession:
        return self.model_copy(update={"source_snapshot_digest": digest or None})

    def with_evaluation(
        self,
        *,
        dependency_level: int,
        environment_level: int,
        machine_level: int,
        detected_dependencies: str,
    ) -> ReeSession:
        return self.model_copy(
            update={
                "dependency_level": dependency_level,
                "environment_level": environment_level,
                "machine_level": machine_level,
                "detected_dependencies": detected_dependencies,
            }
        )

    @property
    def is_sealed(self) -> bool:
        return bool(self.sealed_at and self.seal_hash)

    def with_packaging(self, *, source_included: bool, runtime_included: bool) -> ReeSession:
        return self.model_copy(
            update={
                "source_included": source_included,
                "runtime_included": runtime_included,
            }
        )

    def with_seal(
        self,
        *,
        sealed_at: str,
        seal_hash: str,
        source_included: bool,
        runtime_included: bool,
    ) -> ReeSession:
        return self.model_copy(
            update={
                "sealed_at": sealed_at,
                "seal_hash": seal_hash,
                "source_included": source_included,
                "runtime_included": runtime_included,
            }
        )
