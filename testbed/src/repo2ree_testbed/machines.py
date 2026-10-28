"""Where stacks can run: this checkout, and the SSH machines a developer lists for themselves."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repo2ree_testbed.artifacts import ROOT

LOCAL = "local"
# Nix on a machine, flakes switched on per command so its Nix needs no configuration.
NIX = ("nix", "--extra-experimental-features", "nix-command flakes")
# In the checkout, so it outlives a rebuilt dev container; .gitignore keeps it out of the repository.
DEFAULT_FILE = ROOT / ".config" / "machines.toml"


class MachineConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str | None = None
    jobs: int = Field(default=4, ge=1)
    # The checkout's own .envrc, as in this one: the dev shell, and the venv it syncs and activates.
    shell: tuple[str, ...] = ("direnv", "exec", ".")
    fetch: Literal["slim", "full"] = "slim"
    # Where a remote machine runs everything; `local` is this checkout, already a dev container.
    container: str = "repo2ree-dev"
    dockerfile: str = "docker/dev/nix.Dockerfile"


class MachinesFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    machines: dict[str, MachineConfig] = {}


def machines_file() -> Path:
    return Path(os.environ.get("REPO2REE_MACHINES") or DEFAULT_FILE).expanduser()


def load_machines(path: Path) -> dict[str, MachineConfig]:
    """Every machine: ``local``, and each one the file names (a file is optional)."""
    found: dict[str, MachineConfig] = {LOCAL: MachineConfig(shell=())}
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
