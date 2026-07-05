"""Resolving the external tools core handlers shell out to.

On benches with the tools baked into the image (the legacy workbench image)
they live on PATH. On benches the agent injected its bundles into, PATH knows
nothing — the agent advertises each tool's absolute path through a
``REPO2REE_TOOL_<NAME>`` environment variable set on the bench container
(see the tools manifest in nix/tools.nix). Handlers resolve through here so
both worlds work without the handler knowing which one it is in.
"""

from __future__ import annotations

import os
import shutil


def tool_env_var(name: str) -> str:
    return f"REPO2REE_TOOL_{name.upper().replace('-', '_')}"


def resolve_tool(name: str) -> str:
    """The argv[0] to invoke ``name`` with: the advertised absolute path if the
    agent injected one, otherwise the bare name for PATH lookup."""
    return os.environ.get(tool_env_var(name)) or name


def find_tool(name: str) -> str | None:
    """Like ``resolve_tool`` but verified: the executable's path, or None when
    the tool is genuinely unavailable on this bench."""
    advertised = os.environ.get(tool_env_var(name))
    if advertised:
        return advertised if os.access(advertised, os.X_OK) else None
    return shutil.which(name)
