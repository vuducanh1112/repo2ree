"""Environment-backed process configuration for the workbench service."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo2ree_protocol.tracing import TRACE_FILE_ENV
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


def _resolve_telemetry(mode: str, otlp_endpoint: str | None) -> TelemetryMode:
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
    explicit = os.environ.get("WORKBENCH_TELEMETRY", "").strip().lower()
    if explicit:
        if explicit not in _TELEMETRY_MODES:
            modes = ", ".join(_TELEMETRY_MODES)
            raise ValueError(f"unknown WORKBENCH_TELEMETRY {explicit!r}; expected one of: {modes}")
        return explicit  # type: ignore[return-value]
    if otlp_endpoint:
        return "direct"
    if os.environ.get(TRACE_FILE_ENV):
        return "local"
    return "relay" if mode == "managed" else "off"


def load_config(argv: Sequence[str] = ()) -> WorkbenchConfig:
    parser = argparse.ArgumentParser(prog="repo2ree-workbench")
    parser.add_argument("--root", default=os.environ.get("WORKBENCH_ROOT", "/ree"))
    parser.add_argument(
        "--connect", default=os.environ.get("WORKBENCH_API_WS_URL", "ws://localhost:8000/workbench/connect")
    )
    parser.add_argument("--token", default=os.environ.get("WORKBENCH_AUTH_TOKEN", ""))
    parser.add_argument("--name", default=os.environ.get("WORKBENCH_ID", ""))
    default_mode = os.environ.get(
        "WORKBENCH_MODE",
        "external" if not os.environ.get("WORKBENCH_ALLOCATION_ID") else "managed",
    )
    parser.add_argument("--mode", choices=("managed", "external"), default=default_mode)
    args = parser.parse_args(list(argv))
    explicit_id = args.name
    if explicit_id:
        workbench_id = explicit_id
    else:
        state_dir = Path(os.environ.get("WORKBENCH_STATE_DIR", "~/.repo2ree")).expanduser()
        workbench_id = load_or_create_workbench_id(state_dir)
    otlp_endpoint = os.environ.get("OTLP_ENDPOINT") or None
    return WorkbenchConfig(
        api_ws_url=args.connect,
        workbench_id=workbench_id,
        mode=args.mode,
        allocation_id=os.environ.get("WORKBENCH_ALLOCATION_ID", ""),
        enrollment_token=args.token,
        root=Path(args.root),
        exec_path=os.environ.get("REPO2REE_EXEC_PATH", "repo2ree-exec"),
        location_id=os.environ.get("WORKBENCH_LOCATION_ID", ""),
        image=os.environ.get("WORKBENCH_IMAGE", ""),
        otlp_endpoint=otlp_endpoint,
        telemetry=_resolve_telemetry(args.mode, otlp_endpoint),
    )
