from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Transient landing zone for HTTP uploads before they are copied into a
    # workbench container. The workbench volume — not the host — is the source
    # of truth for REE state.
    UPLOAD_STAGING_DIR: Path = Path(".repo2ree/upload-staging")
    WORKBENCH_REGISTRY_FILE: Path = Path(".repo2ree/workbench-registry.json")
    # Optional override for the default workbench image. When unset, the default
    # comes from the workbench image catalog (workbench/catalog.py). Set this to
    # provision from a locally-built image (e.g. `repo2ree-workbench:latest` from
    # `make workbench-image`) without touching the catalog.
    WORKBENCH_IMAGE: str | None = None
    # The workbench agent owns the container runtime (WORKBENCH_DOCKER_MODE is its
    # concern, not consumed here). It dials this API outbound and holds a WebSocket
    # at /agent/connect — there is no inbound agent endpoint to configure.
    OTLP_ENDPOINT: str | None = None


service_settings = Settings()
