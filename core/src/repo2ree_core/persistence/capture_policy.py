"""One file selection for snapshots, seals, and repository exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_ree.model import Ree


class CaptureEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    storage: Literal["git", "lfs"] = "git"

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        if "\\" in value or any(part in {"", ".", "..", ".git"} for part in value.split("/")):
            raise ValueError("Capture path must be a safe canonical relative path")
        return value


class CapturePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    entries: tuple[CaptureEntry, ...]

    @model_validator(mode="after")
    def ordered_paths(self) -> CapturePlan:
        paths = [entry.path for entry in self.entries]
        if paths != sorted(set(paths)):
            raise ValueError("Capture entries must be unique and sorted")
        return self


def capture_plan(layout: ReeLayout, ree: Ree | None) -> CapturePlan:
    paths: set[Path] = set()
    fixed = [*layout.history_files, layout.sbom, layout.reproducibility_report]
    fixed.extend(layout.root / name for name in (".gitattributes", ".gitignore", "run.sh", "REPRODUCING.md"))
    for path in fixed:
        if path.exists() or path.is_symlink():
            paths.add(path)
    for root in layout.history_trees:
        if root.is_symlink():
            paths.add(root)
        elif root.exists():
            for directory, _dirs, files in root.walk(on_error=lambda error: _raise(error)):
                paths.update(directory / name for name in files)
    if isinstance(layout, ReviewLayout) and layout.runs.exists():
        paths.update(layout.runs.glob("*.receipt.json"))
    lfs = {str(path) for path in ree.subject.capture.lfs_paths} if ree and ree.subject.capture else set()
    paths.update(layout.root / path for path in lfs)
    entries = []
    for path in sorted(paths):
        relative = path.relative_to(layout.root).as_posix()
        if ".git" in path.relative_to(layout.root).parts or any(
            parent.is_symlink() for parent in path.parents if parent != layout.root and layout.root in parent.parents
        ):
            raise ValueError(f"Unsafe capture path: {relative}")
        entries.append(CaptureEntry(path=relative, storage="lfs" if relative in lfs else "git"))
    return CapturePlan(entries=tuple(entries))


def _raise(error: OSError) -> None:
    raise error


def write_capture_controls(layout: ReeLayout, ree: Ree) -> None:
    """Ordinary Git commands share the recorder's optional-payload policy."""
    paths = ree.subject.capture.lfs_paths if ree.subject.capture else ()
    attributes = "".join(f"{json.dumps('/' + str(path))} filter=lfs diff=lfs merge=lfs -text\n" for path in paths)
    write_atomic(layout.root / ".gitattributes", attributes.encode())
    ignored = (
        "/upstream/\n/workspace/\n/results/\n/artifacts/*\n/snapshot.tar.gz\n"
        "/sealed.zip\n/upload-staging/\n/reviews/\n/runs/\n"
    )
    for path in (layout.sbom, layout.reproducibility_report):
        ignored += f"!/{path.relative_to(layout.root).as_posix()}\n"
    write_atomic(layout.root / ".gitignore", ignored.encode())
