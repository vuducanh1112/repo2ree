from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.model import ReeDefinition
from repo2ree_ree.signature import SignatureClaim


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRunPayload(StrictRequestModel):
    idempotency_key: str | None = None


class ReeCreatePayload(StrictRequestModel):
    name: str | None = None
    store_id: str = Field(min_length=1)


class PatchReeDefinitionPayload(StrictRequestModel):
    definition_patch: dict[str, object] = Field(
        default_factory=dict,
        description="Top-level fields of `ReeDefinition`, each replaced whole; others are kept. Script paths, digests, "
        "and sizes are derived from the files, so a patch names only what the author decides, such as "
        '`{"experiment_environment": {"artifact_path": "runtime.tar"}}` or '
        '`{"experiments": [{"name": "hello", "output_paths": ["results/run.log"]}]}`.',
    )
    expected_version: str | None = None


class ReeDefinitionReplacePayload(StrictRequestModel):
    definition: ReeDefinition
    expected_version: str | None = None


class AcquireSourcePayload(StrictRequestModel):
    origin_url: str
    source_type: Literal["git", "tarball", "zip"]
    revision: str | None = None
    idempotency_key: str | None = None


class UploadInitPayload(StrictRequestModel):
    file_name: str = Field(
        description="The archive's name: one ending in .zip is read as a zip, any other as a tarball."
    )
    size: int = Field(ge=0)
    content_type: str


class SourceUploadCompletePayload(StrictRequestModel):
    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class LoadReeBundlePayload(StrictRequestModel):
    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class WriteScriptPayload(StrictRequestModel):
    path: str
    content: str
    if_match: str | None = None


class SignReePayload(StrictRequestModel):
    claim: SignatureClaim = "author_approval"
    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class SignReviewPayload(StrictRequestModel):
    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class SealReePayload(StrictRequestModel):
    include_source: bool = Field(default=False, description="Put the source snapshot in the sealed archive.")
    include_experiment_environment: bool = Field(
        default=False, description="Put the declared experiment environment artifact in the sealed archive."
    )
    include_results: bool = Field(default=False, description="Put everything under results/ in the sealed archive.")
