from __future__ import annotations

import json
from pathlib import Path

from repo2ree_protocol.tools import tool_env_var


def tool_environment(bundle_dir: Path | None) -> dict[str, str]:
    if bundle_dir is None:
        return {}
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    environment = {tool_env_var(name): path for name, path in manifest.get("tools", {}).items()}
    if bin_dir := manifest.get("bin_dir"):
        environment["REPO2REE_TOOLS_BIN"] = bin_dir
    environment.update(manifest.get("env", {}))
    return environment
