from __future__ import annotations

import os
import shutil


def tool_env_var(name: str) -> str:
    return f"REPO2REE_TOOL_{name.upper().replace('-', '_')}"


def resolve_tool(name: str) -> str:
    return os.environ.get(tool_env_var(name)) or name


def find_tool(name: str) -> str | None:
    advertised = os.environ.get(tool_env_var(name))
    if advertised:
        return advertised if os.access(advertised, os.X_OK) else None
    return shutil.which(name)
