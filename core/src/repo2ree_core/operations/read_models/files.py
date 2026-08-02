"""Client-facing file inventories for the workspace subtree and whole REE."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.path_safety import resolve_within
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout

MAX_INLINE_TEXT_BYTES = 1024 * 1024
MAX_INLINE_SBOM_BYTES = 8 * 1024 * 1024

WorkspaceFileKind = Literal["source", "generated"]


class WorkspaceFile(BaseModel):
    """One file projected from the materialized workspace subtree."""

    model_config = ConfigDict(extra="forbid")

    path: str
    kind: WorkspaceFileKind
    size: int
    content: str | None = None


class ReeFile(BaseModel):
    """One file under the REE root (upstream/overlay/artifacts/…)."""

    model_config = ConfigDict(extra="forbid")

    path: str
    kind: Literal["ree"] = "ree"
    tag: str
    size: int
    content: str | None = None


_REE_SUBTREE_TAGS: dict[str, str] = {
    "upstream": "Upstream",
    "overlay": "Overlay",
    "artifacts": "Artifact",
    "workspace": "Workspace",
}


def should_inline_file_content(relative_path: str, size: int) -> bool:
    """Whether a file's text content is small enough for a read-model response."""
    lower_path = relative_path.lower()
    if lower_path.endswith("sbom.json") and size > MAX_INLINE_SBOM_BYTES:
        return False
    return size <= MAX_INLINE_TEXT_BYTES


def classify_workspace_file_kind(relative_path: str) -> WorkspaceFileKind:
    """Classify a workspace inventory entry by its origin."""
    _ = relative_path
    return "source"


def _tag(relative: str) -> str:
    if relative == "manifest.json":
        return "Manifest"
    if relative.endswith((".zip", ".tar.gz")):
        return "Archive"
    top, _, _ = relative.partition("/")
    return _REE_SUBTREE_TAGS.get(top, "REE")


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def read_ree_file_bytes(storage_root: Path, ree_id: str, path: str) -> bytes:
    """Read one regular file addressed relative to the REE root."""
    layout = ReeLayout.for_ree(storage_root, ree_id)
    target = resolve_within(layout.root, path)
    if target is None:
        raise ValueError("Invalid REE file path")
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_bytes()


def list_workspace_files(
    storage_root: Path,
    ree_id: str,
    *,
    include_content: bool = True,
) -> list[WorkspaceFile]:
    """Project the materialized workspace as a client-facing inventory."""
    layout = ReeLayout.for_ree(storage_root, ree_id)
    if not layout.workspace.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    directory = ReeDirectory(layout)
    overlay_paths = {relative.as_posix() for relative in directory.overlay.iter_files()}
    entries: list[WorkspaceFile] = []
    for path in sorted(layout.workspace.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(layout.workspace).as_posix()
        size = path.stat().st_size
        entries.append(
            WorkspaceFile(
                path=relative,
                kind="generated" if relative in overlay_paths else classify_workspace_file_kind(relative),
                size=size,
                content=(_read_text_if_possible(path) if should_inline_file_content(relative, size) else None)
                if include_content
                else None,
            )
        )
    return entries


def list_ree_files(
    storage_root: Path,
    ree_id: str,
    *,
    include_content: bool = True,
) -> list[ReeFile]:
    """Enumerate client-visible files across the complete REE directory."""
    layout = ReeLayout.for_ree(storage_root, ree_id)
    if not layout.root.exists():
        raise FileNotFoundError(f"REE {ree_id} not found")
    entries: list[ReeFile] = []
    for path in sorted(layout.root.rglob("*")):
        if not path.is_file() or path == layout.sidecar or path.is_relative_to(layout.upload_staging):
            continue
        relative = path.relative_to(layout.root).as_posix()
        size = path.stat().st_size
        entries.append(
            ReeFile(
                path=relative,
                tag=_tag(relative),
                size=size,
                content=(_read_text_if_possible(path) if should_inline_file_content(relative, size) else None)
                if include_content
                else None,
            )
        )
    return entries
