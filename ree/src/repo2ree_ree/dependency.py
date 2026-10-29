"""Tool-agnostic dependency model.

A ``Dependency`` is one identity — ``(ecosystem, normalized name)`` — plus a
column group per evidence stage of the reproducibility ladder:

    declared_*   filled by manifest parsing (the intake evaluate step)
    locked_*     filled by lockfile parsing
    archived_*   filled by the dependency-archival step
    observed_*   filled by the runtime-SBOM cross-check

Each stage only ever adds columns to existing rows or adds rows (an
SBOM-only row with just ``observed_version`` set is an undeclared
dependency). The per-dependency rung is derived from which columns are
filled, never stored.

Every producer (manifest parsers, the future SBOM cross-check, ...) adapts
its own output to this IR; the reproducibility analysis consumes only this
IR — no tool-specific payload shapes leak past the adapter boundary.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ================================================
# Types
# ================================================

# A container base image is not a special case: it is a dependency in the
# ``oci`` ecosystem whose tag is the declared constraint and whose digest-pin
# lives in ``locked_hashes``.
Ecosystem = Literal["pypi", "conda", "npm", "apt", "oci", "other"]


# ================================================
# Data models
# ================================================


class Dependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # --- identity: the join key for every comparison ---
    ecosystem: Ecosystem = "other"
    name: str = Field(min_length=1)
    # Only set when it differs from the normalized ``name``.
    name_as_written: str | None = None
    # Which environment the row belongs to (e.g. a workflow process);
    # ``None`` is the repo's root environment.
    scope: str | None = None
    # Top-level declaration vs transitive closure entry.
    direct: bool = True

    # --- declared: from a manifest ---
    declared_constraint: str | None = None  # ">=2.1", "==2.1.0", None for bare
    declared_in: str | None = None  # "requirements.txt"

    # --- locked: from a lockfile (or a digest pin, for oci) ---
    locked_version: str | None = None
    # Acceptable artifact digests for the locked version — one per wheel /
    # platform artifact. Archival is verified against this set.
    locked_hashes: list[str] = Field(default_factory=list)
    locked_in: str | None = None  # "uv.lock"

    # --- archived: from the dependency-archival step ---
    archived_path: str | None = None  # bundle-relative artifact path
    archived_digest: str | None = None

    # --- observed: from the built-runtime SBOM ---
    observed_version: str | None = None


class DependencyInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependencies: list[Dependency] = Field(default_factory=list)


# ================================================
# Helpers
# ================================================


def normalize_package_name(ecosystem: Ecosystem, name: str) -> str:
    """Normalize a package name into the identity join key for its ecosystem
    (PEP 503 for pypi; conda names share the same convention)."""
    if ecosystem in ("pypi", "conda"):
        return re.sub(r"[-_.]+", "-", name).lower()
    return name
