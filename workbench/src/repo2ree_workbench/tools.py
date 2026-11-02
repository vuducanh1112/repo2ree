"""The tools a workbench gives the executor (git, curl, syft, …), from a tools bundle.

A provider mounts the bundle into each bench it sets up; a workbench installed on its own
host is pointed at one with ``--tools-bundle``. Either way the executor is told where each
tool is, so what an REE step runs does not depend on what the host happens to have.
"""

from __future__ import annotations

import json
from pathlib import Path

from repo2ree_protocol.tools import tool_env_var


def tool_environment(bundle_dir: Path | None) -> dict[str, str]:
    """The environment naming each tool of the bundle at ``bundle_dir``; nothing without one."""
    if bundle_dir is None:
        return {}
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    environment = {tool_env_var(name): path for name, path in manifest.get("tools", {}).items()}
    if bin_dir := manifest.get("bin_dir"):
        environment["REPO2REE_TOOLS_BIN"] = bin_dir
    environment.update(manifest.get("env", {}))
    return environment
