"""Pure description of the on-disk layout of a single REE.

This module is part of the functional core: it contains the data type and
path arithmetic, but performs no filesystem I/O. The imperative shell in
``repo2ree_api.storage`` uses ``ReeLayout`` to know where to read and write.

Layout under ``<storage_root>/<ree_id>/``:

    .workspace.json       session metadata
    manifest.json         sealed REE spec sidecar
    snapshot.tar.gz       frozen upstream archive
    upload-staging/       staging area for in-flight source uploads
    upstream/             extracted snapshot, treated as read-only
    overlay/              user-added and tool-generated recipe files
    artifacts/            build outputs (runtime, sbom, ...)
    workspace/            materialized view (upstream + overlay) used at build time

``upstream/`` and ``overlay/`` are the sources of truth; ``workspace/`` is
derived and may be rebuilt at any time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


_METADATA_FILENAME = ".workspace.json"
_MANIFEST_FILENAME = "manifest.json"
_UPLOAD_STAGING_DIRNAME = "upload-staging"
_UPSTREAM_DIRNAME = "upstream"

# Public names: shared with the bundle layout so the published REE mirrors
# the on-disk tree. Import these (rather than redefining) to avoid drift.
SNAPSHOT_FILENAME = "snapshot.tar.gz"
OVERLAY_DIRNAME = "overlay"
ARTIFACTS_DIRNAME = "artifacts"
WORKSPACE_DIRNAME = "workspace"


@dataclass(frozen=True)
class ReeLayout:
    """The on-disk layout for a single REE, as a value.

    Construct with :meth:`for_ree`; every other attribute is a pure
    derivation from :attr:`root`. No method touches the filesystem.
    """

    root: Path

    @classmethod
    def for_ree(cls, storage_root: Path | str, ree_id: str) -> "ReeLayout":
        return cls(root=Path(storage_root) / ree_id)

    @property
    def metadata(self) -> Path:
        return self.root / _METADATA_FILENAME

    @property
    def manifest(self) -> Path:
        return self.root / _MANIFEST_FILENAME

    @property
    def snapshot_archive(self) -> Path:
        return self.root / SNAPSHOT_FILENAME

    @property
    def upload_staging(self) -> Path:
        return self.root / _UPLOAD_STAGING_DIRNAME

    @property
    def upstream(self) -> Path:
        return self.root / _UPSTREAM_DIRNAME

    @property
    def overlay(self) -> Path:
        return self.root / OVERLAY_DIRNAME

    @property
    def artifacts(self) -> Path:
        return self.root / ARTIFACTS_DIRNAME

    @property
    def workspace(self) -> Path:
        return self.root / WORKSPACE_DIRNAME

    def upstream_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.upstream, rel)

    def overlay_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.overlay, rel)

    def artifact_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.artifacts, rel)

    def workspace_file(self, rel: str | PurePosixPath) -> Path:
        return self._resolve_under(self.workspace, rel)

    def upload_staging_file(self, token: str) -> Path:
        validate_upload_token(token)
        return self.upload_staging / f"{token}.bin"

    @staticmethod
    def _resolve_under(base: Path, rel: str | PurePosixPath) -> Path:
        validate_relative_path(rel)
        return base / Path(str(rel))


def validate_relative_path(rel: str | PurePosixPath) -> None:
    """Reject absolute paths and parent traversals.

    Pure validator intended to run before any path is handed to the shell.
    """
    if not isinstance(rel, (str, PurePosixPath)):
        raise TypeError(
            f"relative path must be str or PurePosixPath, got {type(rel).__name__}"
        )
    text = str(rel)
    if text == "":
        raise ValueError("relative path must not be empty")
    pure = PurePosixPath(text)
    if pure.is_absolute() or text.startswith("/") or text.startswith("\\"):
        raise ValueError(f"relative path must not be absolute: {text!r}")
    if any(part == ".." for part in pure.parts):
        raise ValueError(f"relative path must not contain '..': {text!r}")


def validate_upload_token(token: str) -> None:
    if not token or "/" in token or "\\" in token or token.startswith("."):
        raise ValueError(f"invalid upload token: {token!r}")


def normalize_workspace_path(path: str | None) -> str:
    """Defensive cleanup for user-supplied workspace-relative paths.

    Strips surrounding whitespace and leading slashes. Permissive: returns
    ``""`` for falsy input and does not raise. Use :func:`validate_relative_path`
    when stricter checks are required.
    """
    return (path or "").lstrip("/").strip()
