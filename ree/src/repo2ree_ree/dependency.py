from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Ecosystem = Literal["pypi", "conda", "npm", "apt", "oci", "other"]


class Dependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ecosystem: Ecosystem = "other"
    name: str = Field(min_length=1)
    name_as_written: str | None = None
    scope: str | None = None
    direct: bool = True

    declared_constraint: str | None = None
    declared_in: str | None = None

    locked_version: str | None = None
    locked_hashes: list[str] = Field(default_factory=list)
    locked_in: str | None = None

    archived_path: str | None = None
    archived_digest: str | None = None

    observed_version: str | None = None


class DependencyInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependencies: list[Dependency] = Field(default_factory=list)


def normalize_package_name(ecosystem: Ecosystem, name: str) -> str:
    if ecosystem in ("pypi", "conda"):
        return re.sub(r"[-_.]+", "-", name).lower()
    return name
