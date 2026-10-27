"""Where stacks can run: this checkout, and the SSH machines a developer lists for themselves."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from repo2ree_testbed.artifacts import ROOT

LOCAL = "local"
DEFAULT_FILE = Path("~/.config/repo2ree/targets.toml")


class Target(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str | None = None
    path: str = "repo2ree"
    jobs: int = Field(default=4, ge=1)
    shell: tuple[str, ...] = ("nix", "develop", "--command")
    fetch: Literal["slim", "full"] = "slim"


class TargetsFile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: dict[str, Target] = {}


def targets_file() -> Path:
    return Path(os.environ.get("REPO2REE_TARGETS") or DEFAULT_FILE).expanduser()


def load_targets(path: Path) -> dict[str, Target]:
    """Every target: ``local``, and each one the file names (a file is optional)."""
    found: dict[str, Target] = {LOCAL: Target(path=str(ROOT), shell=())}
    if not path.is_file():
        return found
    try:
        listed = TargetsFile.model_validate(tomllib.loads(path.read_text(encoding="utf-8"))).targets
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        raise SystemExit(f"{path}: {error}") from error
    for name, target in listed.items():
        if name == LOCAL:
            raise SystemExit(f"{path}: {LOCAL!r} is this checkout and cannot be redefined")
        if not target.host:
            raise SystemExit(f"{path}: target {name!r} needs a host")
        found[name] = target
    return found
