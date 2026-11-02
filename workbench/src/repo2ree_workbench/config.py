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
    # The store this workbench serves (blank: it serves its root as one REE), and where it is.
    store_id: str = ""
    store_root: Path | None = None
    backend: Literal["host"] = "host"
    slots: int = 1


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
    # "ID=PATH": serve the store ID, a directory of REEs at PATH.
    WORKBENCH_STORE: str = ""
    WORKBENCH_SLOTS: int = 1

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


def _store(value: str) -> tuple[str, Path | None]:
    if not value:
        return "", None
    store_id, separator, path = value.partition("=")
    if not separator or not store_id.strip() or not path.strip():
        raise SystemExit(f"repo2ree-workbench: --store takes ID=PATH, not {value!r}")
    return store_id.strip(), Path(path.strip()).expanduser()


def load_config(argv: Sequence[str] = ()) -> WorkbenchConfig:
    environment = WorkbenchEnvironment()
    parser = argparse.ArgumentParser(prog="repo2ree-workbench")
    parser.add_argument("--root", default=environment.WORKBENCH_ROOT)
    parser.add_argument("--connect", default=environment.WORKBENCH_API_WS_URL)
    parser.add_argument("--token", default=environment.WORKBENCH_AUTH_TOKEN)
    parser.add_argument("--name", default=environment.WORKBENCH_ID)
    default_mode = environment.WORKBENCH_MODE or ("external" if not environment.WORKBENCH_ALLOCATION_ID else "managed")
    parser.add_argument("--mode", choices=("managed", "external"), default=default_mode)
    parser.add_argument(
        "--store", default=environment.WORKBENCH_STORE, help="ID=PATH: serve the store ID, a directory of REEs"
    )
    # Where the author's scripts run. Only on this host for now; in a container is still to come.
    parser.add_argument("--backend", choices=("host",), default="host")
    parser.add_argument("--slots", type=int, default=environment.WORKBENCH_SLOTS, help="actions run at once")
    args = parser.parse_args(list(argv))
    store_id, store_root = _store(args.store)
    if store_id and args.mode == "managed":
        parser.error("a managed bench serves the REE it was provisioned for, not a store")
    if args.slots < 1:
        parser.error("--slots must be at least 1")
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
        store_id=store_id,
        store_root=store_root,
        backend=args.backend,
        slots=args.slots,
        otlp_endpoint=otlp_endpoint,
        telemetry=_resolve_telemetry(
            args.mode,
            otlp_endpoint,
            environment.WORKBENCH_TELEMETRY,
            environment.TRACE_FILE,
        ),
    )
