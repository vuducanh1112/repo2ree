"""Request payload shapes for every route.

REE state lives in the per-REE workbench volume (the single source of truth);
the host no longer persists workspaces, so these are pure request schemas with
no filesystem I/O — all of that happens inside the workbench via the command
envelope.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.model import ReeDefinition


class StrictRequestModel(BaseModel):
    """Base for request bodies: an unknown field is a client error, not ignored.

    Declared here with the rest of the control-plane contract so every route's
    payload inherits the same strictness instead of re-spelling the config.
    """

    model_config = ConfigDict(extra="forbid")


class CreateRunPayload(StrictRequestModel):
    """The body every "start a run" route accepts.

    Routes that need nothing else subclass it as-is; the two that take
    parameters (sbom, evaluate) add their fields. Subclassing rather than
    sharing one model keeps each route's schema named after its operation.
    """

    idempotency_key: str | None = None


class ReeCreatePayload(StrictRequestModel):
    """Create a new empty REE in a store.

    Source acquisition is intentionally a separate lifecycle operation through
    ``source:acquire`` or the upload-init/upload/complete sequence.
    """

    name: str | None = None
    # The store to create the REE in; its workbench serves it from then on. The REE starts out
    # declaring one of the images the store offers, or its host when it offers none, and the
    # author declares another like any field.
    store_id: str = Field(min_length=1)
    # The image the REE declares, one the store offers; blank is the store's first.
    image: str = ""


class ReeDefinitionPatchPayload(StrictRequestModel):
    """Replace top-level fields of the current portable REE definition."""

    definition_patch: dict[str, object] = Field(
        default_factory=dict,
        description="Top-level fields of `ReeDefinition`, each replaced whole; others are kept. Script paths, digests, "
        "and sizes are derived from the files, so a patch names only what the author decides, such as "
        '`{"experiment_environment": {"artifact_path": "runtime.tar"}}` or, once its run script is written, '
        '`{"experiments": [{"name": "hello", "output_paths": ["results/run.log"]}]}`.',
    )
    expected_version: str | None = None


class ReeDefinitionReplacePayload(StrictRequestModel):
    definition: ReeDefinition
    expected_version: str | None = None


class SourceAcquirePayload(StrictRequestModel):
    origin_url: str
    source_type: Literal["git", "tarball", "zip"]
    # Git revision (commit, branch, or tag) to pin the fetch to. Blank/omitted
    # means the origin's default branch HEAD. Ignored for non-git sources.
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


class ReeBundleLoadPayload(StrictRequestModel):
    """Load a staged REE bundle into this (freshly provisioned) REE."""

    upload_token: str
    archive_name: str
    idempotency_key: str | None = None


class WorkspaceFileContentPayload(StrictRequestModel):
    path: str
    content: str
    if_match: str | None = None


class ReeSealPayload(StrictRequestModel):
    include_source: bool = Field(default=False, description="Put the source snapshot in the sealed archive.")
    include_experiment_environment: bool = Field(
        default=False, description="Put the declared experiment environment artifact in the sealed archive."
    )
    include_results: bool = Field(default=False, description="Put everything under results/ in the sealed archive.")
