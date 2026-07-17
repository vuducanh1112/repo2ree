"""HTTP wire-format boundary: the public API speaks snake_case JSON.

The workbench-owned workspace document and the command envelope keep their
camelCase keys — they are persisted inside REEs and shared across packages —
so every dict that crosses from the workbench into an HTTP response passes
through :func:`to_wire`, which renames the enumerated control-plane keys to
snake_case. Only keys in the enumerated set are touched: user-authored
content (intent bodies, hardware descriptions, manifests) passes through
unchanged, and the subtrees under :data:`_OPAQUE_KEYS` are never descended
into at all.
"""

from __future__ import annotations

import re
from typing import Any

# Control-plane vocabulary that crosses the HTTP boundary with camelCase keys
# (workspace metadata, source/consistency facts, and command-envelope outputs).
# Deliberately enumerated — an unknown key is assumed to be user content and
# passes through untouched.
_WIRE_KEYS = frozenset(
    {
        "activationScript",
        "activeRuns",
        "actualVersion",
        "agentId",
        "archiveName",
        "binDir",
        "buildRuntimeScriptPath",
        "buildScript",
        "componentCounts",
        "connectedAt",
        "containerExitCode",
        "contentType",
        "createdAt",
        "crossCheck",
        "crossChecked",
        "declaredSize",
        "deletedAt",
        "dependencyCount",
        "dependencyLevel",
        "detectedDependencies",
        "dockerMode",
        "draftManifest",
        "environmentLevel",
        "errorCode",
        "execPath",
        "exitCode",
        "expectedVersion",
        "experimentName",
        "experimentScript",
        "expiresAt",
        "externalRef",
        "fileName",
        "finishedAt",
        "hardwareDescription",
        "hasMore",
        "idempotencyKey",
        "machineLevel",
        "manifestCount",
        "materializedAt",
        "maxBytes",
        "mtimeNs",
        "nextCursor",
        "originUrl",
        "overlayDigest",
        "pausePath",
        "producedOutput",
        "recordedAt",
        "reeFiles",
        "reeId",
        "reeIntent",
        "reeSession",
        "reeWritable",
        "reportRelativePath",
        "runId",
        "runStatus",
        "runtimeArtifact",
        "runtimeIncluded",
        "runtimePath",
        "runtimeRelativePath",
        "sbomRelativePath",
        "schemaVersion",
        "sealHash",
        "sealedAt",
        "serverVersion",
        "snapshotDigest",
        "sourceIncluded",
        "sourceRepo",
        "sourceType",
        "staleInputs",
        "startedAt",
        "storedAt",
        "subjectName",
        "updatedAt",
        "uploadToken",
        "uploadUrl",
        "verifyExitCode",
        "verifyScript",
        "workbenchImage",
        "workspaceDrift",
        # sourceRepo facts
        "acquiredBy",
        "sizeBytes",
        "sizeLabel",
    }
)

# Snake_case keys whose values are user-authored (or mirror a user-authored
# document) — never descended into, so user keys survive round-trips intact.
_OPAQUE_KEYS = frozenset(
    {
        "ree_intent",
        "draft_manifest",
        "hardware_description",
        "manifest",
    }
)

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _snake(key: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", key).lower()


def to_wire(value: Any) -> Any:
    """Recursively rename enumerated camelCase control-plane keys to snake_case.

    Idempotent: snake_case input passes through unchanged.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            wire_key = _snake(key) if key in _WIRE_KEYS else key
            out[wire_key] = item if wire_key in _OPAQUE_KEYS else to_wire(item)
        return out
    if isinstance(value, list):
        return [to_wire(item) for item in value]
    return value
