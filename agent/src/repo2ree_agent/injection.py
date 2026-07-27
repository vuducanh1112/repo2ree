"""Executor/tools bundle resolution for Docker workbench injection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InjectionBundle:
    exec_path: str
    pause_path: str
    store_sources: tuple[str, ...]
    volume_name: str
    tool_env: dict[str, str]


def load_injection_bundle(exec_bundle_dir: str | None, tools_bundle_dir: str | None) -> InjectionBundle | None:
    """Resolve agent-shipped bundle manifests into a mountable bundle."""
    if not exec_bundle_dir:
        return None

    def bundle_parts(bundle_dir: str) -> tuple[bytes, list[str]]:
        root = Path(bundle_dir)
        manifest_bytes = (root / "manifest.json").read_bytes()
        store_dir = root / "store"
        if store_dir.is_dir():
            return manifest_bytes, [f"{store_dir}/."]
        paths = [line for line in (root / "store-paths").read_text().splitlines() if line.strip()]
        return manifest_bytes, paths

    exec_manifest_bytes, sources = bundle_parts(exec_bundle_dir)
    exec_manifest = json.loads(exec_manifest_bytes)
    digest = hashlib.sha256(exec_manifest_bytes)
    tool_env: dict[str, str] = {}
    if tools_bundle_dir:
        tools_manifest_bytes, tools_sources = bundle_parts(tools_bundle_dir)
        sources += tools_sources
        digest.update(tools_manifest_bytes)
        tools_manifest = json.loads(tools_manifest_bytes)
        for name, path in tools_manifest.get("tools", {}).items():
            tool_env[f"REPO2REE_TOOL_{name.upper().replace('-', '_')}"] = path
        if bin_dir := tools_manifest.get("bin_dir"):
            tool_env["REPO2REE_TOOLS_BIN"] = bin_dir
        tool_env.update(tools_manifest.get("env", {}))
    for source in sources:
        digest.update(source.encode())
    return InjectionBundle(
        exec_path=exec_manifest["exec_path"],
        pause_path=exec_manifest["pause_path"],
        store_sources=tuple(sources),
        volume_name=f"repo2ree-store-{digest.hexdigest()[:12]}",
        tool_env=tool_env,
    )
