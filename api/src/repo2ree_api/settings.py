from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Transient landing zone for HTTP uploads before they are copied into a
    # workbench container. The workbench volume — not the host — is the source
    # of truth for REE state.
    UPLOAD_STAGING_DIR: Path = Path(".repo2ree/upload-staging")
    REVIEWS_STORAGE_DIR: Path = Path(".repo2ree/reviews")
    WORKBENCH_REGISTRY_FILE: Path = Path(".repo2ree/workbench-registry.json")
    WORKBENCH_IMAGE: str = "repo2ree-workbench:latest"
    OTLP_ENDPOINT: str | None = None


service_settings = Settings()
