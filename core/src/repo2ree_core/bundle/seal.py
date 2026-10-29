"""Seal a captured repository by including selected local LFS payloads."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.bundle.repository_files import prepare_reproducer
from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.transitions import ReePreconditionError, record_seal, replace_contents, revision_of
from repo2ree_core.persistence.capture_policy import capture_plan, write_capture_controls
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import list_tree_relpaths
from repo2ree_core.persistence.layout import (
    ReeLayout,
)
from repo2ree_core.persistence.lfs import store_payload
from repo2ree_core.persistence.repository import save_ree
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import BundleContents, BundleEntry, CapturePolicy, Ree
from repo2ree_ree.primitives import Digest, ReePath, UtcInstant


class SealOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sealed_at: UtcInstant
    ree_digest: Digest
    input_bytes: int
    entry_count: int


@dataclass(frozen=True)
class BundleProgress:
    phase: Literal["writing", "manifest", "publishing"]
    bytes_processed: int
    bytes_total: int
    entries_processed: int
    entries_total: int


class BundleSealCanceledError(Exception):
    """Raised before publication when a seal operation is canceled."""


ProgressSink = Callable[[BundleProgress], None]
CancelCheck = Callable[[], bool]
_COPY_CHUNK_BYTES = 1024 * 1024


def _refuse_stale_evidence(ree: Ree) -> None:
    """Refuse to seal an REE whose receipts no longer describe what it holds.

    Sealing is the step that turns an aggregate into something citable, and a
    stale receipt is the one defect a reader cannot detect for themselves: the
    digests all agree, the evidence is all present, and it describes a build
    script or a source that the bundle no longer contains. Publishing that is
    worse than publishing nothing, so it is a refusal rather than a warning.

    *Missing* evidence is deliberately not refused. An REE with no SBOM and no
    activation test is incomplete, which its own audit says plainly and which a
    reader can weigh; an author may have nothing more to add. Incomplete and
    self-contradictory are different failures and only the second is a lie.
    """
    stale = audit(ree).stale_steps()
    if not stale:
        return
    detail = "; ".join(f"{name}: {', '.join(step.reasons)}" for name, step in stale)
    raise ReePreconditionError(
        f"cannot seal an REE with stale evidence — re-run the affected steps or drop what they describe ({detail})"
    )


def seal_ree(
    layout: ReeLayout,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
    sealed_at: UtcInstant,
    progress: ProgressSink | None = None,
    is_canceled: CancelCheck | None = None,
) -> SealOutputs:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = store.read_ree()
    _refuse_stale_evidence(ree)
    before_revision = revision_of(ree)
    if ree.seal is not None:
        raise ReePreconditionError("REE is already sealed")
    report = progress or (lambda _update: None)
    canceled = is_canceled or (lambda: False)
    paths: set[str] = set()
    if source_included:
        if ree.subject.definition.source is not None and not layout.snapshot_archive.is_file():
            raise ValueError("Selected source snapshot is unavailable")
        if layout.snapshot_archive.is_file():
            paths.add(layout.snapshot_archive.relative_to(layout.root).as_posix())
    runtime = ree.subject.definition.build_runtime
    if runtime_included and runtime and runtime.runtime_path:
        source = store.author_artifact(str(runtime.runtime_path))
        if source is None:
            raise ValueError("Selected runtime is unavailable")
        target = layout.artifacts / PurePosixPath(str(runtime.runtime_path)).name
        if target != source:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        paths.add(target.relative_to(layout.root).as_posix())
    if results_included:
        paths.update(f"results/{name}" for name in list_tree_relpaths(layout.results))
    policy = CapturePolicy(lfs_paths=tuple(ReePath(path) for path in sorted(paths)))
    ree = ree.model_copy(update={"subject": ree.subject.model_copy(update={"capture": policy})})
    prepare_reproducer(layout, ree)
    write_capture_controls(layout, ree)
    plan = capture_plan(layout, ree)
    selected = [entry for entry in plan.entries if entry.path != "ree.json"]
    total = sum((layout.root / entry.path).lstat().st_size for entry in selected)
    processed = 0
    inventory: list[BundleEntry] = []

    def chunk_done(size: int) -> None:
        nonlocal processed
        if canceled():
            raise BundleSealCanceledError
        processed += size
        report(BundleProgress("writing", processed, total, len(inventory), len(selected)))

    for entry in selected:
        if canceled():
            raise BundleSealCanceledError
        path = layout.root / entry.path
        if entry.storage == "lfs":
            pointer = store_payload(path, layout.git_dir, on_chunk=chunk_done)
            digest, size = Digest("sha256:" + pointer.oid), pointer.size
        elif path.is_symlink():
            data = os.fsencode(path.readlink())
            digest, size = digest_bytes(data), len(data)
            chunk_done(size)
        else:
            digest, size = digest_file(path), path.stat().st_size
            chunk_done(size)
        inventory.append(BundleEntry(path=ReePath(entry.path), digest=digest, size=size))
    if canceled():
        raise BundleSealCanceledError
    sealed = record_seal(replace_contents(ree, BundleContents(entries=tuple(inventory))), sealed_at=sealed_at)
    report(BundleProgress("manifest", processed, total, len(selected), len(selected)))
    save_ree(layout, store, sealed, expected_revision=before_revision)
    report(BundleProgress("publishing", processed, total, len(selected), len(selected)))
    if sealed.seal is None:
        raise RuntimeError("seal transition did not produce a seal")
    return SealOutputs(
        sealed_at=sealed.seal.sealed_at,
        ree_digest=sealed.seal.ree_digest,
        input_bytes=total,
        entry_count=len(inventory),
    )
