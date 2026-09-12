"""Offline Git LFS objects and canonical pointers; no ambient filters or network."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

_POINTER = re.compile(rb"version https://git-lfs.github.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize ([0-9]+)\n")


class LfsPointer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    oid: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)

    def encode(self) -> bytes:
        return f"version https://git-lfs.github.com/spec/v1\noid sha256:{self.oid}\nsize {self.size}\n".encode()

    @classmethod
    def parse(cls, data: bytes) -> LfsPointer | None:
        match = _POINTER.fullmatch(data)
        return cls(oid=match[1].decode(), size=int(match[2])) if match else None

    def object_path(self, git_dir: Path) -> Path:
        return git_dir / "lfs" / "objects" / self.oid[:2] / self.oid[2:4] / self.oid

    def verify(self, git_dir: Path) -> Path:
        path = self.object_path(git_dir)
        if (
            path.is_symlink()
            or not path.is_file()
            or any(parent.is_symlink() for parent in path.parents if parent == git_dir or git_dir in parent.parents)
        ):
            raise ValueError(f"Missing LFS object: {self.oid}")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != self.size or digest != self.oid:
            raise ValueError(f"Corrupt LFS object: {self.oid}")
        return path


def store_payload(source: Path, git_dir: Path, *, on_chunk: Callable[[int], None] = lambda _size: None) -> LfsPointer:
    """Publish immutable bytes before their pointer can enter a commit."""
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"LFS payload must be a regular file: {source.name}")
    temporary_dir = git_dir / "lfs" / "tmp"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with tempfile.NamedTemporaryFile(dir=temporary_dir) as staged:
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                staged.write(chunk)
                digest.update(chunk)
                size += len(chunk)
                on_chunk(len(chunk))
        staged.flush()
        os.fsync(staged.fileno())
        pointer = LfsPointer(oid=digest.hexdigest(), size=size)
        destination = pointer.object_path(git_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            pointer.verify(git_dir)
        else:
            # Hard-link publication is atomic and leaves NamedTemporaryFile cleanup intact.
            os.link(staged.name, destination)
        return pointer


def copy_object(pointer: LfsPointer, source_git: Path, target_git: Path) -> None:
    source = pointer.verify(source_git)
    destination = pointer.object_path(target_git)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(source, destination)
    pointer.verify(target_git)
