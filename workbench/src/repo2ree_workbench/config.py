"""Environment-backed process configuration for the workbench service."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from repo2ree_workbench.identity import load_or_create_workbench_id

# Where this workbench's *own* spans go. ``direct`` posts to a collector it can
# reach; ``relay`` ships them over the control-plane socket it already holds;
# ``local`` writes the TRACE_FILE path or stdout; ``off`` makes tracing a no-op.
TelemetryMode = Literal["direct", "relay", "local", "off"]
_TELEMETRY_MODES = ("direct", "relay", "local", "off")


@dataclass(frozen=True)
class WorkbenchConfig:
    api_ws_url: str
    workbench_id: str
    allocation_id: str
    enrollment_token: str
    root: Path
    exec_path: str
    location_id: str
    image: str
    mode: Literal["managed", "external"] = "managed"
    otlp_endpoint: str | None = None
    telemetry: TelemetryMode = "off"


class WorkbenchEnvironment(BaseSettings):
    """Validated environment accepted by a resident workbench process."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True, validate_default=True)

    WORKBENCH_ROOT: Path = Path("/ree")
    WORKBENCH_API_WS_URL: str = "ws://localhost:8000/workbench/connect"
    WORKBENCH_AUTH_TOKEN: str = ""
    WORKBENCH_ID: str = ""
    WORKBENCH_MODE: Literal["managed", "external"] | None = None
    WORKBENCH_ALLOCATION_ID: str = ""
    WORKBENCH_STATE_DIR: Path = Path("~/.repo2ree")
    WORKBENCH_LOCATION_ID: str = ""
    WORKBENCH_IMAGE: str = ""
    WORKBENCH_TELEMETRY: Literal["direct", "relay", "local", "off"] | None = None
    REPO2REE_EXEC_PATH: str = "repo2ree-exec"
    OTLP_ENDPOINT: str | None = None
    TRACE_FILE: str | None = None

    @field_validator("WORKBENCH_MODE", "WORKBENCH_TELEMETRY", mode="before")
    @classmethod
    def _normalize_modes(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = value.strip().lower()
        if normalized not in (*_TELEMETRY_MODES, "managed", "external"):
            modes = ", ".join(_TELEMETRY_MODES)
            raise ValueError(f"unknown mode {normalized!r}; telemetry modes are: {modes}")
        return normalized

    @field_validator("OTLP_ENDPOINT", "TRACE_FILE", mode="before")
    @classmethod
    def _blank_optional_is_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


def _resolve_telemetry(
    mode: str,
    otlp_endpoint: str | None,
    explicit: TelemetryMode | None,
    trace_file: str | None,
) -> TelemetryMode:
    """Decide where this workbench's own spans go.

    An explicit ``WORKBENCH_TELEMETRY`` always wins — that is the operator's
    escape hatch, and the way to keep telemetry off the control plane or off the
    machine entirely. Otherwise a configured collector means direct export, a
    configured TRACE_FILE means local, and the fallback follows the trust
    boundary the connection already draws: a managed bench was provisioned by
    the fleet that runs this control plane and is already fully observed by it,
    so relaying costs nothing new. An external bench is someone else's machine;
    it does not start shipping telemetry across that boundary merely because
    nobody configured a collector for it.
    """
    if explicit:
        return explicit
    if otlp_endpoint:
        return "direct"
    if trace_file:
        return "local"
    return "relay" if mode == "managed" else "off"


def load_config(argv: Sequence[str] = ()) -> WorkbenchConfig:
    environment = WorkbenchEnvironment()
    parser = argparse.ArgumentParser(prog="repo2ree-workbench")
    parser.add_argument("--root", default=environment.WORKBENCH_ROOT)
    parser.add_argument("--connect", default=environment.WORKBENCH_API_WS_URL)
    parser.add_argument("--token", default=environment.WORKBENCH_AUTH_TOKEN)
    parser.add_argument("--name", default=environment.WORKBENCH_ID)
    default_mode = environment.WORKBENCH_MODE or ("external" if not environment.WORKBENCH_ALLOCATION_ID else "managed")
    parser.add_argument("--mode", choices=("managed", "external"), default=default_mode)
    args = parser.parse_args(list(argv))
    explicit_id = args.name
    if explicit_id:
        workbench_id = explicit_id
    else:
        state_dir = environment.WORKBENCH_STATE_DIR.expanduser()
        workbench_id = load_or_create_workbench_id(state_dir)
    otlp_endpoint = environment.OTLP_ENDPOINT
    return WorkbenchConfig(
        api_ws_url=args.connect,
        workbench_id=workbench_id,
        mode=args.mode,
        allocation_id=environment.WORKBENCH_ALLOCATION_ID,
        enrollment_token=args.token,
        root=Path(args.root),
        exec_path=environment.REPO2REE_EXEC_PATH,
        location_id=environment.WORKBENCH_LOCATION_ID,
        image=environment.WORKBENCH_IMAGE,
        otlp_endpoint=otlp_endpoint,
        telemetry=_resolve_telemetry(
            args.mode,
            otlp_endpoint,
            environment.WORKBENCH_TELEMETRY,
            environment.TRACE_FILE,
        ),
    )
