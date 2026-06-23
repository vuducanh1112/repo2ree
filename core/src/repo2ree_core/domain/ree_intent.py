from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from repo2ree_core.domain.env_entry import ContainerEntry, EnvEntry
from repo2ree_core.domain.hbom import HBOM
from repo2ree_core.experiment import Activation, Experiment

# ================================================
# Types
# ================================================

SourceType = Literal["", "git", "hg", "svn", "cvs", "bzr", "tarball", "zip"]

NormalizedPath = Annotated[str | None, BeforeValidator(lambda v: (v or "").lstrip("/").strip() or None)]

REE_MANIFEST_VERSION = 1  # bump on any breaking schema change


# ================================================
# Helpers
# ================================================

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
                    {str(extra_key): extra_value for extra_key, extra_value in item.items()}
                )
            else:
                normalized["extra_info"][key] = item
            continue
        normalized["extra_info"][key] = item

    return normalized


# ================================================
# Data Models
# ================================================


class Contributor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str = ""
    name: str = ""
    affiliation_name: str = ""
    affiliation_identifier: str = ""


class ReeCatalogMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = ""
    version: str = ""
    website: str = ""
    keywords: list[str] = Field(default_factory=list)
    contributors: list[Contributor] = Field(default_factory=list)
    corresponding_author_identifier: str | None = None


class ReeIntent(BaseModel):
    """Author-declared reproducibility intent — the only patchable model."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    catalog_metadata: ReeCatalogMetadata = Field(default_factory=ReeCatalogMetadata)
    origin_url: str = ""
    source_type: SourceType = ""
    runtime: NormalizedPath = None
    runtime_entry: EnvEntry = Field(default_factory=ContainerEntry)
    build_runtime_script: NormalizedPath = None
    activation: Activation = Field(default_factory=Activation)
    sbom: NormalizedPath = None
    swhid: str = ""
    zenodo_doi: str | None = None
    dataverse_doi: str | None = None
    hardware_description: HBOM = Field(default_factory=HBOM)
    experiments: list[Experiment] = Field(default_factory=list)

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

    @field_validator("catalog_metadata", mode="before")
    @classmethod
    def normalize_catalog_metadata(cls, value: Any) -> Any:
        if value in (None, ""):
            return ReeCatalogMetadata()
        return value

    @model_validator(mode="after")
    def _unique_experiment_names(self) -> ReeIntent:
        names = [e.name for e in self.experiments if e.name]
        if len(names) != len(set(names)):
            raise ValueError("experiment names must be unique")
        return self

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, Any]) -> ReeIntent:
        intent = dict(metadata.get("reeIntent") or {})
        intent = {k: v for k, v in intent.items() if k in cls.model_fields}
        if not intent.get("name"):
            intent["name"] = str(metadata.get("name") or "")
        if not intent.get("origin_url"):
            intent["origin_url"] = str(metadata.get("externalRef") or "")
        return cls.model_validate(intent)

    def apply_patch(self, patch: Mapping[str, Any]) -> ReeIntent:
        merged = self.model_dump()
        merged.update(dict(patch or {}))
        try:
            return ReeIntent.model_validate(merged)
        except ValidationError as exc:
            raise ValueError(f"Invalid REE intent patch: {exc}") from exc
