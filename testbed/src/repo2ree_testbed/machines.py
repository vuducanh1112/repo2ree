from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repo2ree_testbed.artifacts import ROOT

LOCAL = "local"
NIX = ("nix", "--extra-experimental-features", "nix-command flakes")
DEFAULT_FILE = ROOT / ".config" / "machines.toml"


class MachineConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str | None = None
    jobs: int = Field(default=4, ge=1)


class MachinesFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    machines: dict[str, MachineConfig] = {}


def machines_file() -> Path:
    return Path(os.environ.get("REPO2REE_MACHINES") or DEFAULT_FILE).expanduser()


def load_machines(path: Path) -> dict[str, MachineConfig]:
    found: dict[str, MachineConfig] = {LOCAL: MachineConfig()}
    if not path.is_file():
        return found
    try:
        listed = MachinesFile.model_validate(tomllib.loads(path.read_text(encoding="utf-8"))).machines
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise SystemExit(f"{path}: {error}") from error
    for name, machine in listed.items():
        if name == LOCAL:
            raise SystemExit(f"{path}: {LOCAL!r} is this checkout and cannot be redefined")
        if not machine.host:
            raise SystemExit(f"{path}: machine {name!r} needs a host")
        found[name] = machine
    return found
