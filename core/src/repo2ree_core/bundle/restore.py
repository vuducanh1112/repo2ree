"""Restore and verify an extracted REE bundle."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.primitives import ReePath
from repo2ree_core.domain.ree.model import BundleContents, BundleEntry
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import list_tree_relpaths
from repo2ree_core.persistence.layout import (
    BUNDLE_ARTIFACTS_PREFIX,
    BUNDLE_OVERLAY_PREFIX,
    BUNDLE_REE_MANIFEST_ENTRY_PATH,
    BUNDLE_RESULTS_PREFIX,
    BUNDLE_SNAPSHOT_ENTRY_PATH,
    ReeLayout,
)
from repo2ree_core.persistence.ree_manifest import parse_ree_manifest


class BundleLoadOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    sealed: bool
    ree_digest: str | None
    source_restored: bool
    overlay_files: int
    artifact_files: int


def _actual_inventory(bundle_root: Path) -> BundleContents:
    entries: list[BundleEntry] = []
    for path in list_tree_relpaths(bundle_root):
        if path == BUNDLE_REE_MANIFEST_ENTRY_PATH:
            continue
        absolute = bundle_root / path
        entries.append(BundleEntry(path=ReePath(path), digest=digest_file(absolute), size=absolute.stat().st_size))
    return BundleContents(entries=tuple(entries))


def restore_ree_bundle(
    layout: ReeLayout,
    *,
    bundle_root: Path,
    archive_path: Path,
) -> BundleLoadOutputs:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    document_path = bundle_root / BUNDLE_REE_MANIFEST_ENTRY_PATH
    if not document_path.is_file():
        raise ValueError(f"not an REE bundle: missing {BUNDLE_REE_MANIFEST_ENTRY_PATH}")
    ree = parse_ree_manifest(json.loads(document_path.read_text(encoding="utf-8")))
    actual = _actual_inventory(bundle_root)
    if actual != ree.subject.contents:
        raise ValueError("bundle contents do not match the REE subject inventory")

    for target in (layout.upstream, layout.overlay, layout.artifacts, layout.workspace, layout.results):
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)
    source_restored = _restore_file(bundle_root / BUNDLE_SNAPSHOT_ENTRY_PATH, layout.snapshot_archive)
    overlay_files = _restore_tree(bundle_root / BUNDLE_OVERLAY_PREFIX, layout.overlay)
    artifact_files = _restore_tree(bundle_root / BUNDLE_ARTIFACTS_PREFIX, layout.artifacts)
    _restore_tree(bundle_root / BUNDLE_RESULTS_PREFIX, layout.results)
    store.write_ree(ree)
    if ree.seal is not None:
        shutil.copyfile(archive_path, layout.sealed_archive)
    else:
        layout.sealed_archive.unlink(missing_ok=True)
    return BundleLoadOutputs(
        name=ree.subject.definition.name,
        sealed=ree.seal is not None,
        ree_digest=str(ree.seal.ree_digest) if ree.seal else None,
        source_restored=source_restored,
        overlay_files=overlay_files,
        artifact_files=artifact_files,
    )


def _restore_file(source: Path, target: Path) -> bool:
    if not source.is_file():
        target.unlink(missing_ok=True)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def _restore_tree(source: Path, target: Path) -> int:
    if not source.is_dir():
        return 0
    shutil.copytree(source, target, dirs_exist_ok=True)
    return len(list_tree_relpaths(source))
