"""Environment-backed process configuration for the workbench service."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo2ree_workbench.identity import load_or_create_workbench_id


@dataclass(frozen=True)
class WorkbenchConfig:
    api_ws_url: str
    workbench_id: str
    allocation_id: str
    enrollment_token: str
    root: Path
    exec_path: str
    location_id: str
    profile_id: str
    profile_revision: str
    mode: Literal["managed", "external"] = "managed"
    otlp_endpoint: str | None = None


def load_config(argv: Sequence[str] = ()) -> WorkbenchConfig:
    parser = argparse.ArgumentParser(prog="repo2ree-workbench")
    parser.add_argument("--root", default=os.environ.get("WORKBENCH_ROOT", "/ree"))
    parser.add_argument(
        "--connect", default=os.environ.get("WORKBENCH_API_WS_URL", "ws://localhost:8000/workbench/connect")
    )
    default_token = os.environ.get("WORKBENCH_AUTH_TOKEN") or os.environ.get("WORKBENCH_ENROLLMENT_TOKEN", "")
    parser.add_argument("--token", default=default_token)
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
    return WorkbenchConfig(
        api_ws_url=args.connect,
        workbench_id=workbench_id,
        mode=args.mode,
        allocation_id=os.environ.get("WORKBENCH_ALLOCATION_ID", ""),
        enrollment_token=args.token,
        root=Path(args.root),
        exec_path=os.environ.get("REPO2REE_EXEC_PATH", "repo2ree-exec"),
        location_id=os.environ.get("WORKBENCH_LOCATION_ID", ""),
        profile_id=os.environ.get("WORKBENCH_PROFILE_ID", ""),
        profile_revision=os.environ.get("WORKBENCH_PROFILE_REVISION", ""),
        otlp_endpoint=os.environ.get("OTLP_ENDPOINT") or None,
    )
