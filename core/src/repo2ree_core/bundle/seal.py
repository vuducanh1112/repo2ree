"""Materialize and seal the bundle described by a portable REE subject."""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.bundle.plan import deterministic_zip_info
from repo2ree_core.digests import DIGEST_PREFIX, digest_bytes
from repo2ree_core.domain.primitives import Digest, ReePath, UtcInstant
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import BundleContents, BundleEntry, Ree
from repo2ree_core.domain.ree.transitions import ReePreconditionError, record_seal, replace_contents, revision_of
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import list_tree_relpaths, publish_atomic, staging_path
from repo2ree_core.persistence.layout import (
    BUNDLE_ARTIFACTS_PREFIX,
    BUNDLE_OVERLAY_PREFIX,
    BUNDLE_REE_MANIFEST_ENTRY_PATH,
    BUNDLE_RESULTS_PREFIX,
    BUNDLE_SNAPSHOT_ENTRY_PATH,
    ReeLayout,
)
from repo2ree_core.persistence.ree_manifest import ree_manifest_bytes
from repo2ree_core.persistence.repository import save_ree
from repo2ree_core.reproduction.reproducer import reproducer_entries


class SealOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sealed_at: UtcInstant
    ree_digest: Digest
    input_bytes: int
    archive_bytes: int
    entry_count: int


@dataclass(frozen=True)
class BundleEntrySource:
    archive_path: str
    file_path: Path | None = None
    inline_content: bytes | None = None

    @property
    def size(self) -> int:
        if self.inline_content is not None:
            return len(self.inline_content)
        if self.file_path is None:  # pragma: no cover - internal construction invariant
            raise RuntimeError(f"bundle entry {self.archive_path} has no source")
        return self.file_path.stat().st_size


@dataclass(frozen=True)
class BundleProgress:
    phase: Literal["writing", "manifest", "publishing"]
    bytes_processed: int
    bytes_total: int
    archive_bytes: int
    entries_processed: int
    entries_total: int


class BundleSealCanceledError(Exception):
    """Raised before publication when a seal operation is canceled."""


ProgressSink = Callable[[BundleProgress], None]
CancelCheck = Callable[[], bool]
_COPY_CHUNK_BYTES = 1024 * 1024


def _reproducer(ree: Ree) -> list[BundleEntrySource]:
    definition = ree.subject.definition
    source = definition.source
    runtime = definition.build_runtime
    activation = definition.test_activation
    return [
        BundleEntrySource(archive_path=path, inline_content=content)
        for path, content in reproducer_entries(
            activation_script=str(activation.run_script_path) if activation else "",
            activation_verify_script=str(activation.verify_script_path or "") if activation else "",
            experiments=[
                (experiment.name, str(experiment.run_script_path), str(experiment.verify_script_path or ""))
                for experiment in definition.experiments
            ],
            runtime_workspace_path=str(runtime.runtime_path) if runtime and runtime.runtime_path else "",
            runtime_artifact_basename=(
                PurePosixPath(str(runtime.runtime_path)).name if runtime and runtime.runtime_path else ""
            ),
            origin_url=source.origin_url or "" if source else "",
            source_type=source.source_type if source else "",
            revision=source.requested_ref or "" if source else "",
            swhid=str(ree.subject.receipts.source.observed_swhid or "") if ree.subject.receipts.source else "",
        )
    ]


def _tree_entries(root: Path, bundle_prefix: str) -> list[BundleEntrySource]:
    return [
        BundleEntrySource(archive_path=f"{bundle_prefix}{rel}", file_path=root / rel)
        for rel in list_tree_relpaths(root)
    ]


def _collect_entries(
    store: ReeDirectory,
    ree: Ree,
    *,
    source_included: bool,
    runtime_included: bool,
    results_included: bool,
) -> list[BundleEntrySource]:
    layout = store.layout
    entries = _reproducer(ree)
    entries.extend(_tree_entries(layout.overlay, BUNDLE_OVERLAY_PREFIX))
    entries.extend(_tree_entries(layout.artifacts, BUNDLE_ARTIFACTS_PREFIX))
    if source_included and layout.snapshot_archive.is_file():
        entries.append(BundleEntrySource(archive_path=BUNDLE_SNAPSHOT_ENTRY_PATH, file_path=layout.snapshot_archive))
    runtime = ree.subject.definition.build_runtime
    if runtime_included and runtime is not None and runtime.runtime_path is not None:
        runtime_file = layout.workspace / str(runtime.runtime_path)
        target = f"{BUNDLE_ARTIFACTS_PREFIX}{PurePosixPath(str(runtime.runtime_path)).name}"
        if runtime_file.is_file() and all(entry.archive_path != target for entry in entries):
            entries.append(BundleEntrySource(archive_path=target, file_path=runtime_file))
    if results_included:
        entries.extend(_tree_entries(layout.results, BUNDLE_RESULTS_PREFIX))
    return sorted(entries, key=lambda item: item.archive_path)


def _archive_position(archive: zipfile.ZipFile) -> int:
    return archive.fp.tell() if archive.fp is not None else 0


def _write_entry(
    archive: zipfile.ZipFile,
    source: BundleEntrySource,
    *,
    on_chunk: Callable[[int], None],
    is_canceled: CancelCheck,
) -> BundleEntry:
    info = deterministic_zip_info(source.archive_path)
    if source.inline_content is not None:
        if is_canceled():
            raise BundleSealCanceledError
        archive.writestr(info, source.inline_content)
        on_chunk(len(source.inline_content))
        return BundleEntry(
            path=ReePath(source.archive_path),
            digest=digest_bytes(source.inline_content),
            size=len(source.inline_content),
        )
    if source.file_path is None:  # pragma: no cover - internal construction invariant
        raise RuntimeError(f"bundle entry {source.archive_path} has no source")

    hasher = hashlib.sha256()
    size = 0
    with source.file_path.open("rb") as input_file, archive.open(info, "w", force_zip64=True) as output_file:
        while chunk := input_file.read(_COPY_CHUNK_BYTES):
            if is_canceled():
                raise BundleSealCanceledError
            output_file.write(chunk)
            hasher.update(chunk)
            size += len(chunk)
            on_chunk(len(chunk))
    return BundleEntry(
        path=ReePath(source.archive_path),
        digest=Digest(DIGEST_PREFIX + hasher.hexdigest()),
        size=size,
    )


def _write_archive(
    path: Path,
    ree: Ree,
    sources: list[BundleEntrySource],
    *,
    sealed_at: UtcInstant | None,
    progress: ProgressSink,
    is_canceled: CancelCheck,
) -> tuple[Ree, int, int]:
    bytes_total = sum(source.size for source in sources)
    bytes_processed = 0
    entries_processed = 0
    entries_total = len(sources)
    inventory: list[BundleEntry] = []

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:

        def report_chunk(size: int) -> None:
            nonlocal bytes_processed
            bytes_processed += size
            progress(
                BundleProgress(
                    phase="writing",
                    bytes_processed=bytes_processed,
                    bytes_total=bytes_total,
                    archive_bytes=_archive_position(archive),
                    entries_processed=entries_processed,
                    entries_total=entries_total,
                )
            )

        progress(BundleProgress("writing", 0, bytes_total, 0, 0, entries_total))
        for source in sources:
            inventory.append(_write_entry(archive, source, on_chunk=report_chunk, is_canceled=is_canceled))
            entries_processed += 1
            progress(
                BundleProgress(
                    "writing",
                    bytes_processed,
                    bytes_total,
                    _archive_position(archive),
                    entries_processed,
                    entries_total,
                )
            )

        inventoried = replace_contents(ree, BundleContents(entries=tuple(inventory)))
        archived = record_seal(inventoried, sealed_at=sealed_at) if sealed_at is not None else inventoried
        progress(
            BundleProgress(
                "manifest",
                bytes_processed,
                bytes_total,
                _archive_position(archive),
                entries_processed,
                entries_total,
            )
        )
        archive.writestr(deterministic_zip_info(BUNDLE_REE_MANIFEST_ENTRY_PATH), ree_manifest_bytes(archived))

    return archived, bytes_total, path.stat().st_size


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
    sources = _collect_entries(
        store,
        ree,
        source_included=source_included,
        runtime_included=runtime_included,
        results_included=results_included,
    )
    report = progress or (lambda _update: None)
    canceled = is_canceled or (lambda: False)
    temporary = staging_path(store.layout.sealed_archive)
    try:
        sealed, input_bytes, archive_bytes = _write_archive(
            temporary,
            ree,
            sources,
            sealed_at=sealed_at,
            progress=report,
            is_canceled=canceled,
        )
        if canceled():
            raise BundleSealCanceledError
        report(
            BundleProgress(
                "publishing",
                input_bytes,
                input_bytes,
                archive_bytes,
                len(sources),
                len(sources),
            )
        )
        publish_atomic(temporary, store.layout.sealed_archive)
        save_ree(store.layout, store, sealed, expected_revision=before_revision)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    seal = sealed.seal
    if seal is None:  # pragma: no cover - record_seal establishes this postcondition
        raise RuntimeError("seal transition did not produce a seal")
    return SealOutputs(
        sealed_at=seal.sealed_at,
        ree_digest=seal.ree_digest,
        input_bytes=input_bytes,
        archive_bytes=archive_bytes,
        entry_count=len(sources),
    )


@contextmanager
def materialized_ree_archive(layout: ReeLayout) -> Iterator[Path]:
    """Yield a file-backed sealed or draft archive, cleaning up drafts afterward."""
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        raise FileNotFoundError(f"REE not found at {layout.root}")
    ree = store.read_ree()
    if ree.seal is not None:
        if not store.layout.sealed_archive.is_file():
            raise RuntimeError("sealed archive file is missing")
        yield store.layout.sealed_archive
        return
    sources = _collect_entries(
        store,
        ree,
        source_included=True,
        runtime_included=True,
        results_included=True,
    )
    with tempfile.TemporaryDirectory() as temporary_dir:
        archive_path = Path(temporary_dir) / "ree.zip"
        _write_archive(
            archive_path,
            ree,
            sources,
            sealed_at=None,
            progress=lambda _update: None,
            is_canceled=lambda: False,
        )
        yield archive_path
