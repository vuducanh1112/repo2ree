"""Read views over a stored REE: its metadata, its files, its bytes.

Imperative shell — every function here performs filesystem I/O through
:class:`ReeStore` and :class:`ReeLayout`. No function reads application
settings; callers pass ``storage_root`` explicitly so this module can live in
core and run inside the workbench, which is the single source of truth for REE
state.

These are the *REE-side* views only: what is on disk and how it is classified.
Nothing here interprets evidence. The composed document an API client sees —
files plus consistency, receipts, and step states — is assembled a layer up, in
``repo2ree_core.operations.workspace_view``, because that reading depends on
``evidence`` and this package must not.

Mutating workspace operations (acquire, write, patch, upload, remove) are owned
by the operations handlers in ``repo2ree_core.operations.handlers``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from repo2ree_core.ree.layout import (
    ReeLayout,
    normalize_workspace_path,
    validate_relative_path,
)
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.inventory import (
    ReeFile,
    WorkspaceFile,
    classify_file_kind,
    is_reserved_workspace_filename,
    should_inline_file_content,
)
from repo2ree_core.ree.workspace.model import WorkspaceMetadata


def layout_for(storage_root: Path, ree_id: str) -> ReeLayout:
    return ReeLayout.for_ree(storage_root, ree_id)


def store_for(storage_root: Path, ree_id: str) -> ReeStore:
    return ReeStore(layout_for(storage_root, ree_id))


def read_metadata(storage_root: Path, ree_id: str) -> WorkspaceMetadata:
    store = store_for(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    return store.read_metadata()


def _validate_user_path(path: str) -> str:
    normalized = normalize_workspace_path(path)
    validate_relative_path(normalized)
    if is_reserved_workspace_filename(PurePosixPath(normalized).name):
        raise ValueError("Invalid workspace path")
    return normalized


def read_file_bytes(storage_root: Path, ree_id: str, path: str) -> bytes:
    normalized = _validate_user_path(path)
    fp = layout_for(storage_root, ree_id).workspace_file(normalized)
    if not fp.exists() or not fp.is_file():
        raise FileNotFoundError(path)
    return fp.read_bytes()


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _iter_workspace_files(store: ReeStore) -> Iterator[Path]:
    """Yield every regular file in the materialized workspace/ subtree."""
    root = store.layout.workspace
    if not root.exists():
        raise FileNotFoundError(f"REE {store.layout.root.name} not found")
    yield from (p for p in sorted(root.rglob("*")) if p.is_file())


def workspace_files(
    storage_root: Path,
    ree_id: str,
    *,
    include_content: bool = True,
) -> list[dict[str, Any]]:
    store = store_for(storage_root, ree_id)
    root = store.layout.workspace
    # Provenance: files present in overlay/ are user-added or tool-generated
    # recipe files; everything else came from the immutable upstream source.
    # The merged workspace flattens both, so we recover the origin here.
    overlay_rels = {rel.as_posix() for rel in store.overlay.iter_files()}
    entries: list[dict[str, Any]] = []
    for fp in _iter_workspace_files(store):
        rel = fp.relative_to(root).as_posix()
        size = fp.stat().st_size
        entry = WorkspaceFile(
            path=rel,
            kind="generated" if rel in overlay_rels else classify_file_kind(rel),
            size=size,
            content=(_read_text_if_possible(fp) if should_inline_file_content(rel, size) else None)
            if include_content
            else None,
        )
        entries.append(entry.model_dump())
    return entries


_REE_SUBTREE_TAGS: dict[str, str] = {
    "upstream": "Upstream",
    "overlay": "Overlay",
    "artifacts": "Artifact",
    "workspace": "Workspace",
}


def _ree_file_tag(rel: str) -> str:
    if rel == "manifest.json":
        return "Manifest"
    if rel.endswith(".zip") or rel.endswith(".tar.gz"):
        return "Archive"
    top, _, _ = rel.partition("/")
    return _REE_SUBTREE_TAGS.get(top, "REE")


def ree_files(
    storage_root: Path,
    ree_id: str,
    *,
    include_content: bool = True,
) -> list[dict[str, Any]]:
    """Enumerate every file under the REE root, mirroring the on-disk layout."""
    layout = layout_for(storage_root, ree_id)
    ree_root = layout.root
    if not ree_root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    entries: list[dict[str, Any]] = []
    for fp in sorted(ree_root.rglob("*")):
        if not fp.is_file():
            continue
        if is_reserved_workspace_filename(fp.name):
            continue
        rel_path = fp.relative_to(ree_root)
        if any(part.startswith(".upload.") for part in rel_path.parts):
            continue
        rel = rel_path.as_posix()
        size = fp.stat().st_size
        entry = ReeFile(
            path=rel,
            tag=_ree_file_tag(rel),
            size=size,
            content=(_read_text_if_possible(fp) if should_inline_file_content(rel, size) else None)
            if include_content
            else None,
        )
        entries.append(entry.model_dump())
    return entries
