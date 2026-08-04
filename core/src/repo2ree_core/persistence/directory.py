"""Imperative shell around :class:`ReeLayout`.

All filesystem I/O for a single REE goes through :class:`ReeDirectory`. It takes
a :class:`ReeLayout` at construction and performs reads, writes, and
directory bootstrapping at the paths the layout describes. The layout
itself is pure; this module is intentionally not.

Every write here replaces its target atomically
(:func:`repo2ree_core.persistence.files.write_atomic`), so a workbench killed mid-write
leaves the previous version rather than a prefix of the new one. That is what
lets the readers throughout ``operations`` treat an unparseable document as a
defect worth reporting rather than an expected state to recover from.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import ValidationError

from repo2ree_core.domain.ree.model import Ree
from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.persistence.files import write_atomic, write_json_atomic
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.ree_manifest import parse_ree_manifest, ree_manifest_bytes
from repo2ree_core.reserved_paths import RESERVED_OVERLAY_SCRIPTS
from repo2ree_core.reserved_templates import reserved_script_template

# What a half-built or damaged persisted document raises on the way through
# json and pydantic: an unreadable file, malformed bytes, or content that no
# longer fits the model. Named for the failure rather than for any one document,
# because every document this module reads — the manifest, the reproducibility
# report — fails exactly these four ways and no others. Anything
# outside this set is a defect in the reader, not a fact about the REE, and must
# not be mistaken for one.
#
# It lives here, beside the writes it is the counterpart of: the atomic-write
# guarantee above is what makes an unparseable document worth reporting rather
# than an expected state to recover from. Both step families read REE documents,
# and neither may import the other, so the shared name has to sit below both.
UNREADABLE_DOCUMENT = (OSError, json.JSONDecodeError, ValidationError, ValueError)


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
        """Replace a subtree file, atomically.

        Overlay content is authored, and the etag a client holds is a digest of
        what it last read — so a torn write here would both lose edits that
        exist nowhere else and leave the next optimistic-concurrency check
        comparing against a half-file.
        """
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


class ReeDirectory:
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

    def author_artifact(self, declared: str | None) -> Path | None:
        """Resolve an author-declared artifact path to the file it names.

        For the runtime, which an author's own build script writes: the declared
        path is workspace-relative while authoring, but bundling lifts the file
        into the bundle's ``artifacts/`` and rewrites the manifest to match — so
        an REE loaded from a bundle declares ``artifacts/<name>``, which is
        REE-root-relative and never appears under ``workspace/``. Both spellings
        resolve here, workspace first, so a loaded baseline reads exactly like an
        authored one to everything downstream. (REE-produced artifacts need none
        of this: they are written to their fixed ``artifacts/`` slot from the
        start — see ``ReeLayout.sbom``.)

        Returns None when the path is unset or names nothing on disk; callers
        decide whether that is a failure or merely inconclusive evidence.
        """
        if not declared:
            return None
        for candidate in (self.layout.workspace_file(declared), self.layout.ree_file(declared)):
            if candidate.is_file():
                return candidate
        return None

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

    def ensure_reserved_overlay_scripts(self) -> None:
        """Seed the REE-owned scripts with their packaged starter templates.

        Only missing files are created, so authored content is never touched.
        The overlay is the source of truth, while workspace is its materialized
        execution view. This method is intentionally separate from
        :meth:`ensure_dirs`: only REE creation should introduce these files.
        """
        for path in RESERVED_OVERLAY_SCRIPTS:
            if not self.overlay.exists(path):
                self.overlay.write_text(path, reserved_script_template(path))
            if not self.workspace.exists(path):
                self.workspace.write_text(path, self.overlay.read_text(path))

    def remove(self) -> None:
        """Delete the entire REE directory tree. No-op if absent."""
        if self.layout.root.exists():
            shutil.rmtree(self.layout.root)

    # --- Portable REE aggregate ----------------------------------------

    def manifest_exists(self) -> bool:
        return self.layout.manifest.is_file()

    def read_ree(self) -> Ree:
        return parse_ree_manifest(self.read_manifest_json())

    def write_ree(self, ree: Ree) -> None:
        write_atomic(self.layout.manifest, ree_manifest_bytes(ree))

    def read_manifest_json(self) -> dict[str, Any]:
        """The portable REE bytes parsed as JSON, without model validation.

        Used by the executor's ``get-ree-manifest`` passthrough, which must return
        what is actually on disk rather than a model-normalized projection.
        Aggregate mutations use :meth:`write_ree`, which is the only writer of
        the document's one encoding.
        """
        return _read_json(self.layout.manifest)

    def write_manifest_json(self, payload: dict[str, Any]) -> None:
        """Write raw REE JSON atomically. Companion to :meth:`read_manifest_json`."""
        write_json_atomic(self.layout.manifest, payload)


def _read_json(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed
