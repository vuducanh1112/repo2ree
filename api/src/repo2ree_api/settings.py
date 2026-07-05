from pathlib import Path

from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkbenchImage(BaseModel):
    """A base image offered for workbench provisioning.

    Config schema, so it lives with the settings that carry the catalog. The
    ``/api/v1/workbench/images`` route (workbench_images.py) serves these to the
    UI's image picker.

    Only ``ref`` is required — it's the sole backend-meaningful field (the image
    that gets provisioned). ``id``/``label``/``description`` are UI-facing (the
    picker's identity, title, subtitle) and default off the ref when omitted, so a
    catalog entry can be as terse as ``{"ref": "docker:29-dind"}``.
    """

    ref: str
    id: str = ""
    label: str = ""
    description: str = ""

    @model_validator(mode="after")
    def _default_ui_fields_from_ref(self) -> "WorkbenchImage":
        # A ref uniquely identifies an entry, so it doubles as a stable id; the
        # label falls back to it too. Description is optional — blank reads fine.
        self.id = self.id or self.ref
        self.label = self.label or self.ref
        return self


# The catalog default when a deployment overrides nothing. Overriding
# WORKBENCH_IMAGE_CATALOG below replaces this wholesale.
#
# The sole default entry is upstream docker:dind, pinned by manifest-list
# digest (multi-arch: agents resolve their own platform) — the agent injects
# the executor and base tools at provision time, so the bench image carries
# zero repo2ree content. The tag beside the digest is human context only; the
# digest wins. Bump deliberately.
_DEFAULT_WORKBENCH_IMAGE_CATALOG: tuple[WorkbenchImage, ...] = (
    WorkbenchImage(
        id="standard",
        ref="docker.io/library/docker:29-dind@sha256:66d292e5c26bd33a6f6f61cacb880de2186339a524ecba1ce098dbbaceed6515",
        label="Standard (docker)",
        description="Lean docker-in-docker bench; the agent injects the repo2ree executor and base tools.",
    ),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Transient landing zone for HTTP uploads before they are copied into a
    # workbench container. The workbench volume — not the host — is the source
    # of truth for REE state.
    UPLOAD_STAGING_DIR: Path = Path(".repo2ree/upload-staging")
    # Hard cap on a single staged upload; the PUT is rejected (413) beyond it so
    # a runaway body cannot fill the host disk.
    UPLOAD_MAX_BYTES: int = 2 * 1024 * 1024 * 1024
    # Total budget for the staging dir across all concurrently staged uploads;
    # a PUT that would push past it is rejected (507). The per-upload cap alone
    # cannot bound the aggregate — many parallel uploads could.
    UPLOAD_STAGING_MAX_BYTES: int = 8 * 1024 * 1024 * 1024
    # Staged files older than this are abandoned uploads (init/PUT with no
    # upload-complete) and are swept; also the advertised token lifetime.
    UPLOAD_TTL_SECONDS: int = 3600
    WORKBENCH_REGISTRY_FILE: Path = Path(".repo2ree/workbench-registry.json")
    # The workbench agent owns the container runtime (WORKBENCH_DOCKER_MODE is its
    # concern, not consumed here). It dials this API outbound and holds a WebSocket
    # at /agent/connect — there is no inbound agent endpoint to configure.
    OTLP_ENDPOINT: str | None = None

    # Base images the workbench offers at provision time. Ordered: the first entry
    # is the default a request gets when it omits an image (and the UI's highlighted
    # default). Override with a JSON array in the WORKBENCH_IMAGE_CATALOG env var to
    # serve a different set — e.g. to point provisioning at a locally-built image —
    # without touching code. Per-REE overrides still come in on the provision request.
    WORKBENCH_IMAGE_CATALOG: tuple[WorkbenchImage, ...] = _DEFAULT_WORKBENCH_IMAGE_CATALOG

    @field_validator("WORKBENCH_IMAGE_CATALOG")
    @classmethod
    def _catalog_non_empty_unique(cls, catalog: tuple[WorkbenchImage, ...]) -> tuple[WorkbenchImage, ...]:
        if not catalog:
            raise ValueError("WORKBENCH_IMAGE_CATALOG must list at least one image")
        ids = [image.id for image in catalog]
        if len(ids) != len(set(ids)):
            raise ValueError("WORKBENCH_IMAGE_CATALOG image ids must be unique")
        return catalog


service_settings = Settings()
