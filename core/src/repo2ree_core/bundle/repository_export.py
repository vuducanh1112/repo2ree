"""Mechanical Git transfer and offline LFS checkout at pinned commits."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path, PurePosixPath

from repo2ree_core.bundle.export_format import ScopeExport
from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.history import HISTORY_REF, GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.lfs import LfsPointer, copy_object
from repo2ree_core.persistence.ree_manifest import parse_ree_manifest
from repo2ree_protocol.tools import find_tool
from repo2ree_ree.digest import digest_bytes


def safe_relative(path: str) -> str:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or any(part in {"..", ".git"} for part in parts) or "\\" in path:
        raise ValueError(f"Unsafe repository path: {path}")
    return path


def new_history(root: Path) -> GitHistory:
    if root.is_symlink() or (root / ".git").is_symlink():
        raise ValueError("Repository storage must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    executable = find_tool("git")
    if executable is None:
        raise HistoryCaptureError("Git is required for repository transfer")
    history = GitHistory(ReeLayout(root=root), executable)
    history.initialize()
    return history


def materialize(history: GitHistory, head: str, source_git: Path) -> tuple[LfsPointer, ...]:
    """Read only the pinned tree; never select files from an author's working tree."""
    objects: dict[str, LfsPointer] = {}
    manifest = history.git("show", f"{head}:ree.json", check=False)
    ree = parse_ree_manifest(json.loads(manifest.stdout)) if manifest.returncode == 0 else None
    required = set(ree.subject.capture.lfs_paths) if ree and ree.subject.capture else set()
    seen: set[str] = set()
    entries = history.git("ls-tree", "-rz", head).stdout.split(b"\0")
    for entry in entries:
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        path = safe_relative(raw_path.decode())
        if kind != "blob" or mode not in {"100644", "100755", "120000"}:
            raise ValueError(f"Unsupported repository entry: {path}")
        target = history.layout.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if any(parent.is_symlink() for parent in target.parents if history.layout.root in parent.parents):
            raise ValueError(f"Repository path traverses a symlink: {path}")
        size = int(history.git("cat-file", "-s", oid).stdout)
        pointer = None
        if path in required and size <= 1024:
            data = history.git("cat-file", "blob", oid).stdout
            pointer = LfsPointer.parse(data)
        if path in required and (pointer is None or mode == "120000"):
            raise ValueError(f"Expected an LFS pointer: {path}")
        if pointer:
            seen.add(path)
            copy_object(pointer, source_git, history.layout.git_dir)
            shutil.copyfile(pointer.verify(history.layout.git_dir), target)
            objects[pointer.oid] = pointer
        elif mode == "120000":
            link = history.git("cat-file", "blob", oid).stdout.decode()
            resolved = (target.parent / link).resolve()
            if not resolved.is_relative_to(history.layout.root.resolve()) or ".git" in resolved.parts:
                raise ValueError(f"Unsafe repository symlink: {path}")
            target.symlink_to(link)
        else:
            with target.open("wb") as stream:
                history.git("cat-file", "blob", oid, output=stream)
        if mode != "120000":
            target.chmod(0o755 if mode == "100755" else 0o644)
    if seen != required:
        raise ValueError("Selected tree is missing declared LFS paths")
    history.git("symbolic-ref", "HEAD", HISTORY_REF)
    history.git("update-ref", HISTORY_REF, head)
    history.git("read-tree", head)
    # Standard LFS commands are enabled locally, without embedding executable paths.
    history.git("config", "filter.lfs.clean", "git-lfs clean -- %f")
    history.git("config", "filter.lfs.smudge", "git-lfs smudge -- %f")
    history.git("config", "filter.lfs.process", "git-lfs filter-process")
    history.git("config", "filter.lfs.required", "true")
    return tuple(objects[key] for key in sorted(objects))


def transfer_scope(source: GitHistory, root: Path, *, head: str, scope: str, bundle: Path) -> ScopeExport:
    source.git("bundle", "create", str(bundle), "--all")
    target = new_history(root)
    target.git("fetch", "--update-head-ok", "--no-write-fetch-head", str(bundle), "+refs/*:refs/*")
    # Checkout may select an older seal. Retain later journal entries as evidence.
    journal_head = source.head_snapshot()
    if journal_head is not None:
        target.git("update-ref", f"refs/repo2ree/imports/{journal_head}/journal", journal_head)
    objects = materialize(target, head, source.layout.git_dir)
    records = source.layout.git_dir / "repo2ree" / "operations"
    if records.is_dir():
        destination = target.layout.git_dir / "repo2ree" / "operations"
        destination.mkdir(parents=True, exist_ok=True)
        for record in records.glob("*.json"):
            if record.is_symlink():
                raise ValueError("Cannot export a symlinked pending record")
            shutil.copyfile(record, destination / record.name)
    verify_inventory(root)
    return ScopeExport(scope=scope, head=head, lfs_objects=objects)


def verify_inventory(root: Path) -> None:
    manifest = root / "ree.json"
    if not manifest.is_file():
        return  # An uninitialized review may contain evidence but no subject yet.
    ree = parse_ree_manifest(json.loads(manifest.read_text()))
    if ree.seal is None or ree.subject.capture is None:
        return
    actual: set[str] = set()
    for directory, dirs, files in root.walk():
        dirs[:] = [name for name in dirs if name not in {".git", "reviews"}]
        actual.update((directory / name).relative_to(root).as_posix() for name in files)
    expected = {str(entry.path) for entry in ree.subject.contents.entries} | {"ree.json"}
    if actual != expected:
        raise ValueError("Sealed inventory differs from the selected repository tree")
    for entry in ree.subject.contents.entries:
        path = root / safe_relative(str(entry.path))
        if path.is_symlink():
            data = os.fsencode(path.readlink())
            digest, size = digest_bytes(data), len(data)
        else:
            digest, size = digest_file(path), path.stat().st_size
        if digest != entry.digest or size != entry.size:
            raise ValueError(f"Sealed inventory mismatch: {entry.path}")
