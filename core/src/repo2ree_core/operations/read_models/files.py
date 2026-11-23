from __future__ import annotations

from pathlib import Path

from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.files import ReeFile, WorkspaceFile, WorkspaceFileKind
from repo2ree_ree.paths import resolve_within

MAX_INLINE_TEXT_BYTES = 1024 * 1024
MAX_INLINE_SBOM_BYTES = 8 * 1024 * 1024

_REE_SUBTREE_TAGS: dict[str, str] = {
    "upstream": "Upstream",
    "overlay": "Overlay",
    "artifacts": "Artifact",
}


def should_inline_file_content(relative_path: str, size: int) -> bool:
    lower_path = relative_path.lower()
    if lower_path.endswith("sbom.json") and size > MAX_INLINE_SBOM_BYTES:
        return False
    return size <= MAX_INLINE_TEXT_BYTES


def classify_workspace_file_kind(relative_path: str) -> WorkspaceFileKind:
    _ = relative_path
    return "source"


def _tag(relative: str) -> str:
    if relative.endswith((".zip", ".tar.gz")):
        return "Archive"
    top, _, _ = relative.partition("/")
    return _REE_SUBTREE_TAGS.get(top, "REE")


def _read_text_if_possible(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def read_ree_file_bytes(layout: ReeLayout, path: str) -> bytes:
    target = resolve_within(layout.root, path)
    if target is None or _is_history_storage(layout, target):
        raise ValueError("Invalid REE file path")
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_bytes()


def _is_history_storage(layout: ReeLayout, path: Path) -> bool:
    resolved = path.resolve()
    if resolved.is_relative_to(layout.git_dir.resolve()):
        return True
    if resolved.is_relative_to(layout.reviews.resolve()):
        parts = resolved.relative_to(layout.reviews.resolve()).parts
        return len(parts) >= 2 and parts[1] == ".git"
    return False


def list_workspace_files(
    layout: ReeLayout,
    *,
    include_content: bool = True,
) -> list[WorkspaceFile]:
    if not layout.workspace.exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    directory = ReeDirectory(layout)
    overlay_paths = {relative.as_posix() for relative in directory.overlay.iter_files()}
    entries: list[WorkspaceFile] = []
    for path in sorted(layout.workspace.rglob("*")):
        if not path.is_file() or _is_history_storage(layout, path):
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
    layout: ReeLayout,
    *,
    include_content: bool = True,
) -> list[ReeFile]:
    if not layout.root.exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    entries: list[ReeFile] = []
    visible_paths: list[Path] = []
    for directory, directories, files in layout.root.walk():
        directories[:] = [name for name in directories if not _is_history_storage(layout, directory / name)]
        visible_paths.extend(directory / name for name in files)
    for path in sorted(visible_paths):
        if (
            not path.is_file()
            or _is_history_storage(layout, path)
            or path.is_relative_to(layout.upload_staging)
            or path.is_relative_to(layout.stages)
            or path.is_relative_to(layout.workspace)
        ):
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
