"""Restoring an extracted bundle back into an REE — the inverse of sealing.

Imperative shell. Everything the bundle publishes is written to the on-disk
home it was packaged from; the derived subtrees are deliberately left empty for
the caller to rebuild.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repo2ree_core.bundle.manifest import split_manifest_payload
from repo2ree_core.bundle.plan import (
    REE_ARTIFACTS_PREFIX,
    REE_AUTHOR_RECEIPTS_PREFIX,
    REE_MANIFEST_ENTRY_PATH,
    REE_OVERLAY_PREFIX,
    REE_RESULTS_PREFIX,
    REE_SNAPSHOT_ENTRY_PATH,
)
from repo2ree_core.ree.files import list_tree_relpaths
from repo2ree_core.ree.store import reset_source_state
from repo2ree_core.ree.workspace.views import layout_for, store_for


class BundleLoadOutputs(BaseModel):
    """What loading a bundle put into the REE."""

    model_config = ConfigDict(extra="forbid")

    name: str
    sealed: bool
    seal_hash: str | None
    source_restored: bool
    overlay_files: int
    artifact_files: int
    author_receipts: int


def restore_ree_bundle(
    storage_root: Path,
    ree_id: str,
    *,
    bundle_root: Path,
    archive_path: Path,
) -> BundleLoadOutputs:
    """Replace this REE's contents with an extracted bundle's (shell).

    The inverse of :func:`~repo2ree_core.bundle.seal.seal_workspace_ree` /
    :func:`~repo2ree_core.bundle.seal.build_workspace_ree_archive`:
    ``bundle_root`` is the already-extracted (and path-checked) bundle tree, so
    every path read here is trusted; ``archive_path`` is the ZIP it came from.
    Everything the bundle publishes is restored to the on-disk home it was
    packaged from — snapshot, overlay, artifacts,
    results, and the selected author receipts — while ``upstream/`` and
    ``workspace/`` stay empty: they are derived, and the caller rebuilds them
    from the restored snapshot.

    Artifacts land under ``artifacts/`` (where the seal reads them), not in the
    workspace: a loaded REE carries the author's built outputs as *evidence*,
    and a reviewer's own build writes its own. A bundle with no snapshot leaves
    the source facts cleared — the origin is still on the intent, so the source
    can be acquired (or reviewed) from it.
    """
    store = store_for(storage_root, ree_id)
    if not store.metadata_exists():
        raise FileNotFoundError(f"REE {ree_id} not found")

    manifest_path = bundle_root / REE_MANIFEST_ENTRY_PATH
    if not manifest_path.is_file():
        raise ValueError(f"not an REE bundle: missing {REE_MANIFEST_ENTRY_PATH}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    intent, session = split_manifest_payload(manifest)

    layout = layout_for(storage_root, ree_id)
    store.ensure_dirs()
    # A load is a whole-REE replacement, so it starts from the same cleared
    # state a source change does, plus the derived caches and produced results
    # that only a full replacement invalidates.
    reset_source_state(layout=layout, store=store)
    shutil.rmtree(layout.results, ignore_errors=True)
    for stale in (layout.digest_cache, layout.materialize_marker):
        stale.unlink(missing_ok=True)

    source_restored = _restore_file(bundle_root / REE_SNAPSHOT_ENTRY_PATH, layout.snapshot_archive)
    overlay_files = _restore_tree(bundle_root / REE_OVERLAY_PREFIX, layout.overlay)
    artifact_files = _restore_tree(bundle_root / REE_ARTIFACTS_PREFIX, layout.artifacts)
    _restore_tree(bundle_root / REE_RESULTS_PREFIX, layout.results)
    author_receipts = _restore_tree(bundle_root / REE_AUTHOR_RECEIPTS_PREFIX, layout.author_receipts)

    if not source_restored:
        session = session.without_source()
    store.write_intent(intent)
    store.write_session(session)
    if session.is_sealed:
        # The uploaded bytes *are* the sealed archive the seal hash covers, so
        # the loaded REE can hand back the identical download.
        shutil.copyfile(archive_path, layout.sealed_archive)
        store.write_manifest(manifest)

    return BundleLoadOutputs(
        name=intent.name,
        sealed=session.is_sealed,
        seal_hash=session.seal_hash,
        source_restored=source_restored,
        overlay_files=overlay_files,
        artifact_files=artifact_files,
        author_receipts=author_receipts,
    )


def _restore_file(source: Path, target: Path) -> bool:
    """Copy a single bundle entry into place. False when the bundle omits it."""
    if not source.is_file():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return True


def _restore_tree(source: Path, target: Path) -> int:
    """Copy a bundle subtree into place, returning how many files it held."""
    if not source.is_dir():
        return 0
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)
    return len(list_tree_relpaths(source))
