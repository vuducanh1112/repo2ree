from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from repo2ree_authoring.templates import reserved_script_template
from repo2ree_core.persistence.files import write_atomic, write_json_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.ree_manifest import parse_ree_manifest, ree_manifest_bytes
from repo2ree_ree.model import Ree
from repo2ree_ree.paths import validate_relative_path
from repo2ree_ree.reserved_paths import RESERVED_OVERLAY_SCRIPTS

UNREADABLE_DOCUMENT = (OSError, json.JSONDecodeError, ValidationError, ValueError)


class SubtreeStore:
    def __init__(self, root: Path):
        self.root = root

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def absolute(self, rel: str | PurePosixPath) -> Path:
        validate_relative_path(rel)
        return self.root / Path(str(rel))

    def exists(self, rel: str | PurePosixPath) -> bool:
        return self.absolute(rel).exists()

    def is_file(self, rel: str | PurePosixPath) -> bool:
        return self.absolute(rel).is_file()

    def read_bytes(self, rel: str | PurePosixPath) -> bytes:
        return self.absolute(rel).read_bytes()

    def read_text(self, rel: str | PurePosixPath, encoding: str = "utf-8") -> str:
        return self.absolute(rel).read_text(encoding=encoding)

    def write_bytes(self, rel: str | PurePosixPath, content: bytes) -> None:
        write_atomic(self.absolute(rel), content)

    def write_text(
        self,
        rel: str | PurePosixPath,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        write_atomic(self.absolute(rel), content.encode(encoding))

    def delete_if_exists(self, rel: str | PurePosixPath) -> bool:
        target = self.absolute(rel)
        if not target.exists():
            return False
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return True

    def clear(self) -> None:
        if not self.root.is_dir():
            return
        for child in self.root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def iter_files(self) -> Iterator[PurePosixPath]:
        if not self.root.is_dir():
            return
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(self.root)
                yield PurePosixPath(*rel.parts)


class ReeDirectory:
    def __init__(self, layout: ReeLayout):
        self.layout = layout
        self._upstream = SubtreeStore(layout.upstream)
        self._overlay = SubtreeStore(layout.overlay)
        self._artifacts = SubtreeStore(layout.artifacts)
        self._workspace = SubtreeStore(layout.workspace)

    @property
    def upstream(self) -> SubtreeStore:
        return self._upstream

    @property
    def overlay(self) -> SubtreeStore:
        return self._overlay

    @property
    def artifacts(self) -> SubtreeStore:
        return self._artifacts

    @property
    def workspace(self) -> SubtreeStore:
        return self._workspace

    def author_artifact(self, declared: str | None) -> Path | None:
        if not declared:
            return None
        for candidate in (
            self.layout.kept_environment(declared),
            self.layout.ree_file(declared),
            self.layout.artifacts / Path(declared).name,
        ):
            if candidate.is_file():
                return candidate
        return None

    def ensure_dirs(self) -> None:
        self.layout.root.mkdir(parents=True, exist_ok=True)
        for subtree in (
            self._upstream,
            self._overlay,
            self._artifacts,
            self._workspace,
        ):
            subtree.ensure_root()
        self.layout.upload_staging.mkdir(parents=True, exist_ok=True)
        self.layout.runs.mkdir(parents=True, exist_ok=True)

    def history_artifacts(self) -> tuple[Path, ...]:
        if not self.manifest_exists():
            return ()
        build = self.read_ree().subject.definition.experiment_environment
        artifact = self.author_artifact(str(build.artifact_path)) if build.artifact_path else None
        return (artifact,) if artifact is not None else ()

    def ensure_reserved_overlay_scripts(self) -> None:
        for path in RESERVED_OVERLAY_SCRIPTS:
            if not self.overlay.exists(path):
                self.overlay.write_text(path, reserved_script_template(path))
            if not self.workspace.exists(path):
                self.workspace.write_text(path, self.overlay.read_text(path))

    def remove(self) -> None:
        if self.layout.root.exists():
            shutil.rmtree(self.layout.root)

    def manifest_exists(self) -> bool:
        return self.layout.manifest.is_file()

    def read_ree(self) -> Ree:
        return parse_ree_manifest(self.read_manifest_json())

    def write_ree(self, ree: Ree) -> None:
        write_atomic(self.layout.manifest, ree_manifest_bytes(ree))

    def read_manifest_json(self) -> dict[str, Any]:
        return _read_json(self.layout.manifest)

    def write_manifest_json(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.layout.manifest, payload)


def _read_json(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed
