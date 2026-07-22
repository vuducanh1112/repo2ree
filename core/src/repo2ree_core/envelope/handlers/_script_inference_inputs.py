"""Concrete authored-state inputs for script inference, over ``ReeLayout``.

The pure inference engine sees only the ``ArtifactAccessor`` protocol; this is
the workbench-side implementation that reads the built runtime artifact (in the
workspace) and the written reserved scripts (in the overlay). It resolves a
workspace-relative path against the workspace first, then the overlay, so both
namespaces are reachable through one accessor. Digests are streamed in chunks
and cached so a large runtime image is hashed at most once per request.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.script_inference.runtime_inputs import ArtifactFile, RuntimeInputs
from repo2ree_core.storage.layout import ReeLayout

_DIGEST_CHUNK = 1024 * 1024


class LayoutArtifactAccessor:
    """Read-only view of authored bytes under a workbench layout."""

    def __init__(self, layout: ReeLayout) -> None:
        self._layout = layout
        self._digests: dict[str, str | None] = {}

    def _resolve(self, rel_path: str) -> Path | None:
        # Workspace (built artifacts) wins over overlay (written scripts); both
        # are reachable, and their path namespaces do not collide.
        for resolver in (self._layout.workspace_file, self._layout.overlay_file):
            try:
                candidate = resolver(rel_path)
            except (ValueError, TypeError):
                continue
            if candidate.exists():
                return candidate
        return None

    def stat(self, rel_path: str) -> ArtifactFile:
        path = self._resolve(rel_path)
        if path is None or not path.exists():
            return ArtifactFile()
        if not path.is_file():
            return ArtifactFile(exists=True, is_file=False)
        return ArtifactFile(
            exists=True,
            is_file=True,
            size=path.stat().st_size,
            digest=self._digest(rel_path, path),
        )

    def read(self, rel_path: str, *, max_bytes: int) -> bytes | None:
        path = self._resolve(rel_path)
        if path is None or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def open(self, rel_path: str) -> BinaryIO | None:
        path = self._resolve(rel_path)
        if path is None or not path.is_file():
            return None
        try:
            return path.open("rb")
        except OSError:
            return None

    def _digest(self, rel_path: str, path: Path) -> str | None:
        if rel_path in self._digests:
            return self._digests[rel_path]
        hasher = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(_DIGEST_CHUNK), b""):
                    hasher.update(chunk)
        except OSError:
            self._digests[rel_path] = None
            return None
        digest = f"sha256:{hasher.hexdigest()}"
        self._digests[rel_path] = digest
        return digest


def build_runtime_inputs(layout: ReeLayout, intent: ReeIntent | None) -> RuntimeInputs:
    """Assemble the authored-state inputs for one inference request."""
    return RuntimeInputs(
        declared_runtime_path=(intent.runtime if intent else None),
        experiments=list(intent.experiments) if intent else [],
        accessor=LayoutArtifactAccessor(layout),
    )
