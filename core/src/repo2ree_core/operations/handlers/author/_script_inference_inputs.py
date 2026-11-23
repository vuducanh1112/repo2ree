from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

from repo2ree_core.author_recipes.inference.experiment_environment_inputs import (
    ArtifactFile,
    ExperimentEnvironmentInputs,
)
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.model import ReeDefinition

_DIGEST_CHUNK = 1024 * 1024


class LayoutArtifactAccessor:
    def __init__(self, layout: ReeLayout) -> None:
        self._layout = layout
        self._digests: dict[str, str | None] = {}

    def _resolve(self, rel_path: str) -> Path | None:
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


def _declared_experiment_environment_path(definition: ReeDefinition | None) -> str | None:
    build = definition.experiment_environment if definition else None
    return str(build.artifact_path) if build and build.artifact_path else None


def build_experiment_environment_inputs(
    layout: ReeLayout, definition: ReeDefinition | None
) -> ExperimentEnvironmentInputs:
    return ExperimentEnvironmentInputs(
        declared_experiment_environment_path=_declared_experiment_environment_path(definition),
        experiments=list(definition.experiments) if definition else [],
        accessor=LayoutArtifactAccessor(layout),
    )
