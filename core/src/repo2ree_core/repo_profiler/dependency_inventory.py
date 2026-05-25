"""Tool-agnostic dependency inventory.

Each dependency analysis tool (Renovate, pip-audit, ...) produces a
``DependencyInventory`` by adapting its own output to this IR.  The
reproducibility analysis consumes only this IR — no tool-specific payload
shapes leak past the adapter boundary.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ================================================
# Data models
# ================================================


class Dependency(BaseModel):
    name: str
    declared_version: str | None = None
    locked_version: str | None = None
    kind: Literal["library", "container_image"] = "library"
    # Content-addressable digest; only meaningful for container_image.
    digest: str | None = None
    manifest_path: str | None = None


class DependencyInventory(BaseModel):
    dependencies: list[Dependency] = Field(default_factory=list)
