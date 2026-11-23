from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArchiveProvider = Literal["software_heritage", "zenodo", "dataverse"]

DepositState = Literal["pending", "draft", "published", "failed"]

ArchivePresence = Literal["known", "unknown", "not_checked"]


class ArchiveBindingAttestation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_digest: str
    claim_type: Literal["archive_binding"] = "archive_binding"
    signer_identity: str = ""
    signer_role: str = "archive_adapter"
    signed_at: str = ""
    policy: str = ""
    signature: str | None = None
    verification_material: str | None = None

    archive: ArchiveProvider
    identifier: str
    record_url: str = ""
    concept_identifier: str = ""
    version: str = ""


class DepositRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deposit_id: str
    ree_id: str
    subject_digest: str
    archive: ArchiveProvider
    state: DepositState = "pending"
    idempotency_key: str | None = None
    attestation: ArchiveBindingAttestation | None = None
    error: str = ""
    created_at: str = ""
    updated_at: str = ""


class ArchivePresenceObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archive: ArchiveProvider
    subject: str
    presence: ArchivePresence = "not_checked"
    checked_at: str = ""
    record_url: str = ""


class DepositCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archive: ArchiveProvider
    supports_presence_lookup: bool = False
    supports_bundle_deposit: bool = False
    requires_origin_url: bool = False
    requires_institutional_credentials: bool = False
    supports_identifier_prereservation: bool = False
    notes: str = ""


class DepositRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ree_id: str
    subject_digest: str
    params: dict[str, str] = Field(default_factory=dict)
    idempotency_key: str | None = None
