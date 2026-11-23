from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from repo2ree_workbench.identity import load_or_create_workbench_id

TelemetryMode = Literal["direct", "relay", "local", "off"]
_TELEMETRY_MODES = ("direct", "relay", "local", "off")


@dataclass(frozen=True)
class WorkbenchConfig:
    api_ws_url: str
    workbench_id: str
    enrollment_token: str
    cli_path: str
    store_id: str
    store_root: Path
    otlp_endpoint: str | None = None
    telemetry: TelemetryMode = "off"
    slots: int = 1
    tools_bundle: Path | None = None


class WorkbenchEnvironment(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True, validate_default=True)

    WORKBENCH_API_WS_URL: str = "ws://localhost:8000/workbench/connect"
    WORKBENCH_AUTH_TOKEN: str = ""
    WORKBENCH_ID: str = ""
    WORKBENCH_STATE_DIR: Path = Path("~/.repo2ree")
    WORKBENCH_TELEMETRY: Literal["direct", "relay", "local", "off"] | None = None
    REPO2REE_CLI_PATH: str = "ree"
    OTLP_ENDPOINT: str | None = None
    TRACE_FILE: str | None = None
    WORKBENCH_STORE: str = ""
    WORKBENCH_SLOTS: int = 1
    WORKBENCH_TOOLS_BUNDLE: Path | None = None

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
    if explicit:
        return explicit
    if otlp_endpoint:
        return "direct"
    if trace_file:
        return "local"
    return "off"


def _store(value: str) -> tuple[str, Path]:
    store_id, separator, path = value.partition("=")
    if not separator or not store_id.strip() or not path.strip():
        raise SystemExit(f"repo2ree-workbench: --store takes ID=PATH, not {value!r}")
    return store_id.strip(), Path(path.strip()).expanduser()


def load_config(argv: Sequence[str] = ()) -> WorkbenchConfig:
    environment = WorkbenchEnvironment()
    parser = argparse.ArgumentParser(prog="repo2ree-workbench")
    parser.add_argument("--connect", default=environment.WORKBENCH_API_WS_URL)
    tokens = parser.add_mutually_exclusive_group()
    tokens.add_argument("--token", default=environment.WORKBENCH_AUTH_TOKEN, help="the store's token")
    tokens.add_argument("--token-file", type=Path, help="a file holding the store's token, read at start")
    parser.add_argument("--name", default=environment.WORKBENCH_ID)
    parser.add_argument(
        "--store",
        default=environment.WORKBENCH_STORE,
        required=not environment.WORKBENCH_STORE,
        help="ID=PATH: serve the store ID, a directory of REEs",
    )
    parser.add_argument("--slots", type=int, default=environment.WORKBENCH_SLOTS, help="actions run at once")
    parser.add_argument(
        "--tools-bundle", type=Path, default=environment.WORKBENCH_TOOLS_BUNDLE, help="the tools the executor runs"
    )
    args = parser.parse_args(list(argv))
    store_id, store_root = _store(args.store)
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
        enrollment_token=args.token_file.read_text().strip() if args.token_file else args.token,
        cli_path=environment.REPO2REE_CLI_PATH,
        store_id=store_id,
        store_root=store_root,
        slots=args.slots,
        tools_bundle=args.tools_bundle,
        otlp_endpoint=otlp_endpoint,
        telemetry=_resolve_telemetry(otlp_endpoint, environment.WORKBENCH_TELEMETRY, environment.TRACE_FILE),
    )
