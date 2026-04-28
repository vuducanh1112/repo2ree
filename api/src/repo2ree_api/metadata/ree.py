from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from repo2ree_core.hbom import HBOM


SourceType = Literal["", "git", "hg", "svn", "cvs", "bzr", "tarball", "zip"]
SourceAcquiredBy = Literal["", "download", "upload"]

_HBOM_COMPONENT_FIELD_MAP = {
    "cpus": "cpus",
    "cpu": "cpus",
    "gpus": "gpus",
    "gpu": "gpus",
    "memory": "memory",
    "storage": "storage",
    "network": "network",
}


def _normalize_hbom_component_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _normalize_hbom_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "cpus": {},
        "gpus": {},
        "memory": {},
        "storage": {},
        "network": {},
        "extra_info": {},
    }

    for raw_key, item in value.items():
        key = str(raw_key)
        component_field = _HBOM_COMPONENT_FIELD_MAP.get(key)
        if component_field:
            if isinstance(item, Mapping):
                normalized[component_field] = _normalize_hbom_component_mapping(item)
            else:
                normalized["extra_info"][key] = item
            continue
        if key == "extra_info":
            if isinstance(item, Mapping):
                normalized["extra_info"].update(
                    {
                        str(extra_key): extra_value
                        for extra_key, extra_value in item.items()
                    }
                )
            else:
                normalized["extra_info"][key] = item
            continue
        normalized["extra_info"][key] = item

    return normalized


class REE(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = ""
    origin_url: str = ""
    source_type: SourceType = ""
    runtime: str = ""
    build_runtime_script: str = ""
    activation_script: str = ""
    sbom: str = ""
    swhid: str = ""
    zenodo_doi: str | None = None
    dataverse_doi: str | None = None
    repro_level: str | None = None
    detected_dependencies: str | None = None
    hardware_description: HBOM = Field(default_factory=HBOM)
    eval_level: int = Field(default=0, alias="_evalLevel")
    sealed_at: str | None = Field(default=None, alias="_sealedAt")
    seal_hash: str | None = Field(default=None, alias="_sealHash")
    source_available: bool = Field(default=False, alias="_sourceAvailable")
    source_included: bool = Field(default=False, alias="_sourceIncluded")
    source_acquired_by: SourceAcquiredBy = Field(default="", alias="_sourceAcquiredBy")
    uploaded_archive: str | None = Field(default=None, alias="_uploadedArchive")
    source_snapshot_archive: str | None = Field(
        default=None, alias="_sourceSnapshotArchive"
    )
    source_snapshot_captured_at: str | None = Field(
        default=None, alias="_sourceSnapshotCapturedAt"
    )
    runtime_included: bool = Field(default=False, alias="_runtimeIncluded")
    downloadable_files: list[str] = Field(
        default_factory=list, alias="_downloadableFiles"
    )

    @field_validator("hardware_description", mode="before")
    @classmethod
    def normalize_hardware_description(cls, value: Any) -> Any:
        if value in (None, ""):
            return HBOM()
        if isinstance(value, HBOM):
            return value
        if isinstance(value, Mapping):
            return _normalize_hbom_payload(value)
        return value

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> "REE":
        draft = dict(metadata.get("reeDraft") or {})
        if not draft.get("name"):
            draft["name"] = str(metadata.get("name") or "")
        if not draft.get("origin_url"):
            draft["origin_url"] = str(metadata.get("externalRef") or "")

        source = metadata.get("source")
        if isinstance(source, dict):
            source_type = str(source.get("sourceType") or "")
            if source_type and not draft.get("source_type"):
                draft["source_type"] = source_type

        ree = cls.model_validate(draft)
        return ree.with_source(source if isinstance(source, dict) else None)

    def apply_patch(self, patch: Mapping[str, Any]) -> "REE":
        merged = self.model_dump(by_alias=True)
        merged.update(dict(patch or {}))
        try:
            return REE.model_validate(merged)
        except ValidationError as exc:
            raise ValueError(f"Invalid REE patch: {exc}") from exc

    def with_source(self, source: Mapping[str, Any] | None) -> "REE":
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

        source_included = self.source_included
        if acquired_by == "upload":
            source_included = True

        snapshot_archive = self.source_snapshot_archive
        snapshot_archive = (
            str(source.get("snapshotArchive") or "")
            or str(source.get("archiveName") or "")
            or snapshot_archive
            or None
        )

        source_type = self.source_type
        if isinstance(source.get("sourceType"), str) and source.get("sourceType"):
            source_type = source["sourceType"]

        return self.model_copy(
            update={
                "source_type": source_type,
                "source_available": True,
                "source_acquired_by": acquired_by,
                "source_included": source_included,
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

    def as_manifest(self) -> dict[str, Any]:
        return {
            "ree_version": "1.0",
            "name": self.name or None,
            "origin_url": self.origin_url or None,
            "source_type": self.source_type or None,
            "runtime": self.runtime or None,
            "build_script": self.build_runtime_script or None,
            "activation_script": self.activation_script or None,
            "sbom": self.sbom or None,
            "swhid": self.swhid or None,
            "zenodo_doi": self.zenodo_doi or None,
            "dataverse_doi": self.dataverse_doi or None,
            "hardware_description": self.hardware_description.model_dump(),
            "sealed_at": self.sealed_at or None,
            "seal_hash": self.seal_hash or None,
            "eval_level": self.eval_level or 0,
            "source_included": bool(self.source_included),
            "source_available": bool(self.source_available),
            "source_acquired_by": self.source_acquired_by or None,
            "source_snapshot_archive": self.source_snapshot_archive or None,
            "source_snapshot_captured_at": self.source_snapshot_captured_at or None,
            "runtime_included": bool(self.runtime_included),
            "downloadable_files": list(self.downloadable_files or []),
        }
