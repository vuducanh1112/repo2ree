from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field


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
    sealed_at: str | None = None
    seal_hash: str | None = None
    source_available: bool = False
    source_acquired_by: SourceAcquiredBy = ""
    uploaded_archive: str | None = None
    source_snapshot_archive: str | None = None
    source_snapshot_captured_at: str | None = None
    downloadable_files: list[str] = Field(default_factory=list)

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> "ReeSession":
        raw = dict(metadata.get("reeSession") or {})
        filtered = {k: v for k, v in raw.items() if k in cls.model_fields}
        return cls.model_validate(filtered)

    def with_source(self, source: Mapping[str, Any] | None) -> "ReeSession":
        if not source:
            return self.model_copy(
                update={
                    "source_available": False,
                    "source_acquired_by": "",
                    "uploaded_archive": None,
                    "source_snapshot_archive": None,
                    "source_snapshot_captured_at": None,
                }
            )

        mode = str(source.get("mode") or "")
        acquired_by: SourceAcquiredBy = ""
        if mode == "download":
            acquired_by = "download"
        elif mode == "upload":
            acquired_by = "upload"

        snapshot_archive = (
            str(source.get("snapshotArchive") or "")
            or str(source.get("archiveName") or "")
            or self.source_snapshot_archive
            or None
        )

        return self.model_copy(
            update={
                "source_available": True,
                "source_acquired_by": acquired_by,
                "uploaded_archive": str(source.get("archiveName") or "")
                or self.uploaded_archive,
                "source_snapshot_archive": snapshot_archive,
                "source_snapshot_captured_at": str(
                    source.get("snapshotCapturedAt")
                    or source.get("completedAt")
                    or source.get("acquiredAt")
                    or ""
                )
                or self.source_snapshot_captured_at,
            }
        )

    def with_evaluation(
        self,
        *,
        dependency_level: int,
        environment_level: int,
        machine_level: int,
    ) -> "ReeSession":
        return self.model_copy(
            update={
                "dependency_level": dependency_level,
                "environment_level": environment_level,
                "machine_level": machine_level,
            }
        )

    def with_downloadables(self, files: list[str]) -> "ReeSession":
        return self.model_copy(update={"downloadable_files": list(files)})

    def as_manifest_fields(self) -> dict[str, Any]:
        return {
            "sealed_at": self.sealed_at or None,
            "seal_hash": self.seal_hash or None,
            "dependency_level": self.dependency_level or 0,
            "environment_level": self.environment_level or 0,
            "machine_level": self.machine_level or 0,
            "source_available": bool(self.source_available),
            "source_acquired_by": self.source_acquired_by or None,
            "source_snapshot_archive": self.source_snapshot_archive or None,
            "source_snapshot_captured_at": self.source_snapshot_captured_at or None,
            "downloadable_files": list(self.downloadable_files or []),
        }
