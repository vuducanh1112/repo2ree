from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Loading dotenv files belongs to the launcher (Compose, CI, or a developer's
    # shell). A service must not silently change configuration with its cwd.
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True, validate_default=True)

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
    ALLOCATION_STORE_FILE: Path = Path(".repo2ree/allocations.json")
    # Operator credential for directly installed, externally managed workbenches.
    # Empty disables external registration.
    EXTERNAL_WORKBENCH_TOKEN: str = ""
    # The durable record of sealed REEs and their archive bindings. Unlike the
    # workbench registry beside it, nothing here is reconstructible from live
    # infrastructure: an REE's workbench is torn down long before its deposit
    # stops being citable, so losing this file loses the deposits.
    REE_INDEX_FILE: Path = Path(".repo2ree/ree-index.json")
    # Durable background-run state. The JSON backend coordinates threads in one
    # API process; deployments using it must run a single API worker.
    RUN_REGISTRY_DIR: Path = Path(".repo2ree/runs")
    # Bounds both concurrent workbench commands and the API's worker threads.
    RUN_MAX_WORKERS: int = 4
    # The provider owns the container runtime (PROVIDER_DOCKER_MODE is its concern,
    # not consumed here). Workbenches dial this API outbound and hold a WebSocket
    # at /workbench/connect — there is no inbound workbench endpoint to configure.
    OTLP_ENDPOINT: str | None = None

    @field_validator("OTLP_ENDPOINT", mode="before")
    @classmethod
    def _blank_endpoint_is_unset(cls, value: object) -> object:
        # Compose pass-throughs (`OTLP_ENDPOINT: ${OTLP_ENDPOINT:-}`) surface an
        # unset host var as "" — treat that as no collector, so downstream
        # `is not None` checks (structured logging) don't trip on it.
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
