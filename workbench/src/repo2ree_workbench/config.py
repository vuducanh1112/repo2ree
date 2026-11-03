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
    # The store's token, which admits this workbench for that store alone.
    enrollment_token: str
    exec_path: str
    # The store this workbench serves, and the directory of REEs it is on this machine.
    store_id: str
    store_root: Path
    otlp_endpoint: str | None = None
    telemetry: TelemetryMode = "off"
    backend: Literal["host", "container"] = "host"
    slots: int = 1
    # For the container backend: the engine it runs scripts with, the engine a script may reach
    # (none, or the host's socket), and where the engine finds this workbench's files ("LOCAL=ENGINE").
    engine: str = "docker"
    script_engine: Literal["none", "socket"] = "none"
    engine_path: tuple[str, str] | None = None
    # For the container backend: the images it offers an REE created in its store, the first the default.
    images: tuple[str, ...] = ()
    # The tools bundle the executor takes git, curl, syft and the rest from, when not the host's.
    tools_bundle: Path | None = None


class WorkbenchEnvironment(BaseSettings):
    """Validated environment accepted by a resident workbench process."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True, validate_default=True)

    WORKBENCH_API_WS_URL: str = "ws://localhost:8000/workbench/connect"
    WORKBENCH_AUTH_TOKEN: str = ""
    WORKBENCH_ID: str = ""
    WORKBENCH_STATE_DIR: Path = Path("~/.repo2ree")
    WORKBENCH_TELEMETRY: Literal["direct", "relay", "local", "off"] | None = None
    REPO2REE_EXEC_PATH: str = "repo2ree-exec"
    OTLP_ENDPOINT: str | None = None
    TRACE_FILE: str | None = None
    # "ID=PATH": serve the store ID, a directory of REEs at PATH.
    WORKBENCH_STORE: str = ""
    WORKBENCH_SLOTS: int = 1
    WORKBENCH_TOOLS_BUNDLE: Path | None = None
    WORKBENCH_BACKEND: Literal["host", "container"] = "host"
    WORKBENCH_ENGINE: str = "docker"
    WORKBENCH_SCRIPT_ENGINE: Literal["none", "socket"] = "none"
    WORKBENCH_ENGINE_PATH: str = ""

    @field_validator("WORKBENCH_TELEMETRY", mode="before")
    @classmethod
    def _normalize_modes(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            return None
        normalized = value.strip().lower()
        if normalized not in _TELEMETRY_MODES:
            modes = ", ".join(_TELEMETRY_MODES)
            raise ValueError(f"unknown mode {normalized!r}; telemetry modes are: {modes}")
        return normalized

    @field_validator("OTLP_ENDPOINT", "TRACE_FILE", mode="before")
    @classmethod
    def _blank_optional_is_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


def _resolve_telemetry(
    otlp_endpoint: str | None,
    explicit: TelemetryMode | None,
    trace_file: str | None,
) -> TelemetryMode:
    """Decide where this workbench's own spans go.

    An explicit ``WORKBENCH_TELEMETRY`` always wins — that is the operator's
    escape hatch, and the way to keep telemetry off the control plane or off the
    machine entirely. Otherwise a configured collector means direct export, a
    configured TRACE_FILE means local, and the fallback is off: a store's
    workbench may be someone else's machine, and it does not start shipping
    telemetry across that boundary merely because nobody configured a collector
    for it.
    """
    if explicit:
        return explicit
    if otlp_endpoint:
        return "direct"
    if trace_file:
        return "local"
    return "off"


def _engine_path(value: str) -> tuple[str, str] | None:
    if not value:
        return None
    local, separator, engine = value.partition("=")
    if not separator or not local or not engine:
        raise SystemExit(f"repo2ree-workbench: --engine-path takes LOCAL=ENGINE, not {value!r}")
    return local, engine


def _store(value: str) -> tuple[str, Path]:
    store_id, separator, path = value.partition("=")
    if not separator or not store_id.strip() or not path.strip():
        raise SystemExit(f"repo2ree-workbench: --store takes ID=PATH, not {value!r}")
    return store_id.strip(), Path(path.strip()).expanduser()


def load_config(argv: Sequence[str] = ()) -> WorkbenchConfig:
    environment = WorkbenchEnvironment()
    parser = argparse.ArgumentParser(prog="repo2ree-workbench")
    parser.add_argument("--connect", default=environment.WORKBENCH_API_WS_URL)
    parser.add_argument("--token", default=environment.WORKBENCH_AUTH_TOKEN, help="the store's token")
    parser.add_argument("--name", default=environment.WORKBENCH_ID)
    parser.add_argument(
        "--store",
        default=environment.WORKBENCH_STORE,
        required=not environment.WORKBENCH_STORE,
        help="ID=PATH: serve the store ID, a directory of REEs",
    )
    # Where the author's scripts run: on this host, or in a fresh container from the REE's image.
    parser.add_argument("--backend", choices=("host", "container"), default=environment.WORKBENCH_BACKEND)
    parser.add_argument("--engine", default=environment.WORKBENCH_ENGINE, help="container: docker or podman")
    parser.add_argument(
        "--script-engine",
        choices=("none", "socket"),
        default=environment.WORKBENCH_SCRIPT_ENGINE,
        help="container: whether a script may reach the host engine",
    )
    parser.add_argument(
        "--engine-path", default=environment.WORKBENCH_ENGINE_PATH, help="container: LOCAL=ENGINE path prefixes"
    )
    parser.add_argument(
        "--image",
        dest="images",
        action="append",
        default=[],
        metavar="REF",
        help="container: an image an REE created in the store may run in (repeatable; the first is the default)",
    )
    parser.add_argument("--slots", type=int, default=environment.WORKBENCH_SLOTS, help="actions run at once")
    parser.add_argument(
        "--tools-bundle", type=Path, default=environment.WORKBENCH_TOOLS_BUNDLE, help="the tools the executor runs"
    )
    args = parser.parse_args(list(argv))
    store_id, store_root = _store(args.store)
    if args.slots < 1:
        parser.error("--slots must be at least 1")
    images = tuple(dict.fromkeys(ref.strip() for ref in args.images if ref.strip()))
    if images and args.backend != "container":
        parser.error("--image offers images to the store's REEs, so it needs --backend container")
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
        enrollment_token=args.token,
        exec_path=environment.REPO2REE_EXEC_PATH,
        store_id=store_id,
        store_root=store_root,
        backend=args.backend,
        slots=args.slots,
        tools_bundle=args.tools_bundle,
        engine=args.engine,
        script_engine=args.script_engine,
        engine_path=_engine_path(args.engine_path),
        images=images,
        otlp_endpoint=otlp_endpoint,
        telemetry=_resolve_telemetry(otlp_endpoint, environment.WORKBENCH_TELEMETRY, environment.TRACE_FILE),
    )
