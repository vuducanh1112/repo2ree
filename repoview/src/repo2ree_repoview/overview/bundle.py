"""The overview's folder: its own copy of what it shows from outside the tree, and its manifest."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from pydantic import SerializerFunctionWrapHandler, ValidationError, model_serializer

from repo2ree_repoview.documents import Document, Record
from repo2ree_repoview.repository import ROOT, Provenance

COMMAND = "python -m repo2ree_repoview overview"


class Origin(Record):
    """What a bundled file is, or which run of the receipt it came from."""

    kind: str | None = None
    revision: str | None = None
    run: str | None = None
    run_revision: str | None = None


class _Sparse(Record):
    @model_serializer(mode="wrap")
    def _without_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return {key: value for key, value in handler(self).items() if value is not None}


class Copied(_Sparse):
    path: str
    source: str
    sha256: str
    kind: str | None = None
    revision: str | None = None
    run: str | None = None
    run_revision: str | None = None


class Referenced(_Sparse):
    """A file too large to copy, named by its digest."""

    source: str
    sha256: str
    bytes: int
    run: str | None = None
    run_revision: str | None = None


class Manifest(Provenance):
    command: str
    receipt_revision: str | None
    copied: tuple[Copied, ...]
    referenced: tuple[Referenced, ...]


class _Written(Document):
    command: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_name(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def is_overview(folder: Path) -> bool:
    try:
        return _Written.model_validate_json((folder / "manifest.json").read_bytes()).command == COMMAND
    except (OSError, ValidationError):
        return False


class Bundle:
    def __init__(self, root: Path, revision: str) -> None:
        """Start an empty bundle at ``root``; refuses a folder that holds anything but an overview."""
        if root.exists() and any(root.iterdir()) and not is_overview(root):
            raise FileExistsError(f"{root} holds something other than an overview; refusing to replace it")
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        self.root = root
        self.revision = revision
        self.copied: list[Copied] = []
        self.referenced: list[Referenced] = []

    def _copied(self, target: str, source: str, origin: Origin) -> None:
        self.copied.append(
            Copied(
                path=target,
                source=source,
                sha256=sha256(self.root / target),
                kind=origin.kind,
                revision=origin.revision,
                run=origin.run,
                run_revision=origin.run_revision,
            )
        )

    def copy(self, source: Path, target: str, origin: Origin) -> str | None:
        """Copy one file to ``target`` (relative to the bundle); None when the source is missing."""
        if not source.is_file():
            return None
        destination = self.root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self._copied(target, source_name(source), origin)
        return target

    def write(self, target: str, content: str, source: str, origin: Origin) -> None:
        """Keep a document an owner produced on request (``source`` is the command), as if copied."""
        destination = self.root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        self._copied(target, source, origin)

    def copy_tree(self, source: Path, target: str, origin: Origin) -> None:
        for path in sorted(source.rglob("*")) if source.is_dir() else []:
            if path.is_file():
                self.copy(path, f"{target}/{path.relative_to(source)}", origin)

    def reference(self, source: Path, origin: Origin) -> None:
        for path in sorted(source.rglob("*")) if source.is_dir() else [source] if source.is_file() else []:
            if path.is_file():
                self.referenced.append(
                    Referenced(
                        source=source_name(path),
                        sha256=sha256(path),
                        bytes=path.stat().st_size,
                        run=origin.run,
                        run_revision=origin.run_revision,
                    )
                )

    def manifest(self, provenance: Provenance, receipt_revision: str | None) -> Manifest:
        return Manifest(
            **provenance.model_dump(),
            command=COMMAND,
            receipt_revision=receipt_revision,
            copied=tuple(self.copied),
            referenced=tuple(self.referenced),
        )
