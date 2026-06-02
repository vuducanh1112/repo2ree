"""Imperative shell around :class:`ReeLayout`.

All filesystem I/O for a single REE goes through :class:`ReeStore`. It takes
a :class:`ReeLayout` at construction and performs reads, writes, and
directory bootstrapping at the paths the layout describes. The layout
itself is pure; this module is intentionally not.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.storage.layout import ReeLayout, validate_relative_path
from repo2ree_core.workspace.model import WorkspaceMetadata


class SubtreeStore:
    """File operations rooted at a specific subtree of an REE layout.

    Used for ``upstream/``, ``overlay/``, ``artifacts/``, and the
    materialized ``workspace/``. Every relative path is validated to stay
    inside the subtree before any I/O happens.
    """

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
        target = self.absolute(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def write_text(
        self,
        rel: str | PurePosixPath,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        target = self.absolute(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)

    def delete(self, rel: str | PurePosixPath) -> None:
        target = self.absolute(rel)
        if not target.exists():
            raise FileNotFoundError(str(rel))
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

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
        """Empty the subtree, leaving the root directory itself in place."""
        if not self.root.is_dir():
            return
        for child in self.root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def iter_files(self) -> Iterator[PurePosixPath]:
        """Yield POSIX-style relative paths of every file in the subtree."""
        if not self.root.is_dir():
            return
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(self.root)
                yield PurePosixPath(*rel.parts)

    def list_files(self) -> list[PurePosixPath]:
        return list(self.iter_files())


class ReeStore:
    """Filesystem-backed operations for a single REE.

    Construct with a :class:`ReeLayout`. Methods perform I/O at the paths
    the layout names; the layout stays a pure value.
    """

    def __init__(self, layout: ReeLayout):
        self.layout = layout
        self._upstream = SubtreeStore(layout.upstream)
        self._overlay = SubtreeStore(layout.overlay)
        self._artifacts = SubtreeStore(layout.artifacts)
        self._workspace = SubtreeStore(layout.workspace)

    # --- Tree accessors -------------------------------------------------

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

    # --- Whole-REE operations -------------------------------------------

    def exists(self) -> bool:
        return self.layout.root.is_dir()

    def ensure_dirs(self) -> None:
        """Create the full REE directory skeleton. Idempotent."""
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

    def remove(self) -> None:
        """Delete the entire REE directory tree. No-op if absent."""
        if self.layout.root.exists():
            shutil.rmtree(self.layout.root)

    # --- Metadata -------------------------------------------------------

    def metadata_exists(self) -> bool:
        return self.layout.metadata.is_file()

    def read_metadata(self) -> WorkspaceMetadata:
        return WorkspaceMetadata.model_validate(self.read_metadata_json())

    def write_metadata(self, metadata: WorkspaceMetadata) -> None:
        self.write_metadata_json(metadata.model_dump(by_alias=True, exclude_none=True))

    def read_metadata_json(self) -> dict[str, Any]:
        """Raw JSON metadata, without model validation.

        Use this when callers need to mutate the metadata dict directly. For
        new code, prefer :meth:`read_metadata`.
        """
        return _read_json(self.layout.metadata)

    def write_metadata_json(self, payload: dict[str, Any]) -> None:
        """Write raw JSON metadata atomically. Companion to :meth:`read_metadata_json`."""
        _write_json_atomic(self.layout.metadata, payload)

    # --- Manifest -------------------------------------------------------

    def read_manifest(self) -> dict[str, Any] | None:
        if not self.layout.manifest.is_file():
            return None
        return _read_json(self.layout.manifest)

    def write_manifest(self, payload: dict[str, Any]) -> None:
        _write_json_atomic(self.layout.manifest, payload)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, path)
    except BaseException:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
