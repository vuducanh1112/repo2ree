from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Optional override for the default workbench image. When unset, the default
    # comes from the workbench image catalog (workbench_images.py). Set this to
    # provision from a locally-built image (e.g. `repo2ree-workbench:latest` from
    # `make workbench-image`) without touching the catalog.
    WORKBENCH_IMAGE: str | None = None
    # The workbench agent owns the container runtime (WORKBENCH_DOCKER_MODE is its
    # concern, not consumed here). It dials this API outbound and holds a WebSocket
    # at /agent/connect — there is no inbound agent endpoint to configure.
    OTLP_ENDPOINT: str | None = None


service_settings = Settings()
