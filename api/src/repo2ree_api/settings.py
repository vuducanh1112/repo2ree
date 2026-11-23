from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True, validate_default=True)

    UPLOAD_STAGING_DIR: Path = Path(".repo2ree/upload-staging")
    UPLOAD_MAX_BYTES: int = 2 * 1024 * 1024 * 1024
    UPLOAD_STAGING_MAX_BYTES: int = 8 * 1024 * 1024 * 1024
    UPLOAD_TTL_SECONDS: int = 3600
    CONTROL_STATE_DIR: Path = Path(".repo2ree")
    REE_INDEX_FILE: Path = Path(".repo2ree/ree-index.json")
    RUN_REGISTRY_DIR: Path = Path(".repo2ree/runs")
    BEHAVIOUR_JOURNAL_DIR: Path = Path(".repo2ree/journal")
    BEHAVIOUR_FINAL_SHUTDOWN: bool = False
    RUN_MAX_WORKERS: int = 4
    OTLP_ENDPOINT: str | None = None

    @field_validator("OTLP_ENDPOINT", mode="before")
    @classmethod
    def _blank_endpoint_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("RUN_MAX_WORKERS")
    @classmethod
    def _positive_run_workers(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RUN_MAX_WORKERS must be at least 1")
        return value


service_settings = Settings()
