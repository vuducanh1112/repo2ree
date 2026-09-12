"""Validate repository exports in isolation before importing their evidence."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from repo2ree_core.bundle.export_format import RepositoryExport
from repo2ree_core.bundle.repository_export import materialize, new_history, safe_relative, verify_inventory
from repo2ree_core.persistence.history import GitHistory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.lfs import copy_object
from repo2ree_core.persistence.operation_history import read_operation_history


def _copy_regular_tree(source: Path, target: Path) -> None:
    if source.is_symlink():
        raise ValueError("Symlinked Git storage is not supported")
    if not source.is_dir():
        return
    for directory, dirs, files in source.walk():
        for name in [*dirs, *files]:
            if (directory / name).is_symlink():
                raise ValueError("Symlinked Git storage is not supported")
        for name in files:
            path = directory / name
            relative = path.relative_to(source)
            # Local external object dependencies must never be activated.
            if relative.parts[0] == "info":
                continue
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


def restore_repository(layout: ReeLayout, bundle_root: Path) -> dict[str, str]:
    metadata = RepositoryExport.model_validate_json((bundle_root / "export.json").read_text())
    scopes = [entry.scope for entry in metadata.scopes]
    if not scopes or scopes[0] != "." or len(scopes) != len(set(scopes)):
        raise ValueError("Export must declare one author scope and unique review scopes")
    for scope in scopes[1:]:
        safe_relative(scope)
        if len(Path(scope).parts) != 2 or Path(scope).parts[0] != "reviews":
            raise ValueError("Invalid review scope")
    with tempfile.TemporaryDirectory() as temporary:
        validated = Path(temporary) / "validated"
        histories: list[GitHistory] = []
        for entry in metadata.scopes:
            source = bundle_root / "ree" / entry.scope / ".git"
            history = new_history(validated / entry.scope)
            _copy_regular_tree(source / "objects", history.layout.git_dir / "objects")
            _copy_regular_tree(source / "refs", history.layout.git_dir / "refs")
            packed = source / "packed-refs"
            if packed.is_symlink():
                raise ValueError("Symlinked packed refs")
            if packed.is_file():
                shutil.copyfile(packed, history.layout.git_dir / "packed-refs")
            history.git("fsck", "--full", "--no-reflogs")
            actual = materialize(history, entry.head, source)
            if actual != entry.lfs_objects:
                raise ValueError("Declared LFS objects differ from selected tree")
            verify_inventory(history.layout.root)
            _copy_regular_tree(source / "repo2ree" / "operations", history.layout.git_dir / "repo2ree" / "operations")
            histories.append(history)
        if not (validated / "ree.json").is_file():
            raise ValueError("Export has no author REE manifest")
        incoming = read_operation_history(ReeLayout(root=validated)).operations
        existing = {record.attempt_id: record for record in read_operation_history(layout).operations}
        for record in incoming:
            previous = existing.get(record.attempt_id)
            if previous is not None and previous.model_dump() != record.model_dump():
                raise ValueError(f"Conflicting imported execution attempt: {record.attempt_id}")
        # Validation above does not modify destination state or execute uploaded config.
        heads = {}
        for entry, history in zip(metadata.scopes, histories, strict=True):
            destination = new_history(layout.root / entry.scope)
            bundle = Path(temporary) / f"{entry.head}.bundle"
            history.git("bundle", "create", str(bundle), "--all")
            previous_head = destination.head_snapshot()
            if previous_head is not None:
                destination.git("update-ref", f"refs/repo2ree/imports/{previous_head}/journal", previous_head)
            namespace = f"refs/repo2ree/imports/{entry.head}"
            destination.git("fetch", "--no-write-fetch-head", str(bundle), f"+refs/*:{namespace}/*")
            for pointer in entry.lfs_objects:
                copy_object(pointer, history.layout.git_dir, destination.layout.git_dir)
            pending = history.layout.git_dir / "repo2ree" / "operations"
            if pending.is_dir():
                target = destination.layout.git_dir / "repo2ree" / "operations"
                target.mkdir(parents=True, exist_ok=True)
                for path in pending.glob("*.json"):
                    if not (target / path.name).exists():
                        shutil.copyfile(path, target / path.name)
            if entry.scope != ".":
                destination.git("update-ref", "refs/heads/ree-history", entry.head)
            heads[entry.scope] = entry.head
        # Remove the old mutable files, retaining active Git storage and upload staging.
        for path in layout.root.iterdir():
            if path.name in {".git", "upload-staging", "reviews"}:
                continue
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        for entry, history in zip(metadata.scopes, histories, strict=True):
            destination_root = layout.root / entry.scope
            for directory, dirs, files in history.layout.root.walk():
                dirs[:] = [name for name in dirs if name not in {".git", "reviews"}]
                for name in files:
                    path = directory / name
                    target = destination_root / path.relative_to(history.layout.root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    if path.is_symlink():
                        target.symlink_to(path.readlink())
                    else:
                        shutil.copy2(path, target)
        return heads
