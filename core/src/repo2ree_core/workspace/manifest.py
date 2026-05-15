"""Pure construction of the published REE manifest.

The manifest is the JSON payload written to ``manifest.json`` and embedded
into the downloadable bundle as ``ree/ree.json``. It is computed from a
:class:`~repo2ree_core.domain.ree.REE` together with the surrounding
:class:`~repo2ree_core.workspace.model.WorkspaceMetadata` (name, origin URL,
source type). This module performs no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from repo2ree_core.domain.ree import REE
from repo2ree_core.storage.layout import normalize_workspace_path


def build_manifest_payload(
    metadata: Mapping[str, Any],
    ree: REE,
    *,
    ree_id: str,
) -> dict[str, Any]:
    """Merge ``ree`` with workspace ``metadata`` into the published manifest."""
    runtime_path = normalize_workspace_path(ree.runtime)
    sbom_path = normalize_workspace_path(ree.sbom)
    build_script_path = normalize_workspace_path(ree.build_runtime_script)
    activation_script_path = normalize_workspace_path(ree.activation_script)

    manifest = ree.as_manifest()
    manifest["name"] = (
        metadata.get("name") or manifest["name"] or f"workspace-{ree_id[:8]}"
    )
    manifest["origin_url"] = metadata.get("externalRef") or manifest["origin_url"]
    source = metadata.get("source")
    manifest["source_type"] = (
        source.get("sourceType")
        if isinstance(source, Mapping)
        else manifest["source_type"]
    )
    manifest["runtime"] = runtime_path or None
    manifest["build_script"] = build_script_path or None
    manifest["activation_script"] = activation_script_path or None
    manifest["sbom"] = sbom_path or None
    return manifest
