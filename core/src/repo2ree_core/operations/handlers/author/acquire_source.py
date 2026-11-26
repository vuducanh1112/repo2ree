from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.envelope import receipt_envelope
from repo2ree_core.domain.ree.transitions import (
    ReePreconditionError,
    commit_receipt,
    replace_definition,
    revision_of,
)
from repo2ree_core.execution.process import CancelCheck, StreamingProcessResult, format_command, run_streaming_process
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author.extract_upload import freeze_upload
from repo2ree_core.operations.handlers.author.materialize_workspace import materialize_workspace
from repo2ree_core.operations.handlers.author.snapshot_upstream import SNAPSHOT_FAILURES, freeze_upstream
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ACQUIRE_SCRIPT_FILENAME, ReeLayout
from repo2ree_core.persistence.repository import load_ree, observe_source_slot, save_ree
from repo2ree_core.reproduction.acquire_source import build_acquire_sh
from repo2ree_core.source_repo import (
    LfsPayloadError,
    SourceHistoryError,
    directory_swhid,
    lfs_files,
    lfs_manifest,
    pack_source_history,
)
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import AcquireSourceOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import Digest
from repo2ree_ree.model import Ree, SourceDefinition
from repo2ree_ree.primitives import GitRevision, SourceHistory, Swhid
from repo2ree_ree.receipt import AcquireSourceReceipt, LfsFile


@dataclass(frozen=True)
class _Acquisition:
    mode: Literal["download", "upload"]
    definition: SourceDefinition
    upload_token: str = ""
    archive_name: str = ""


@dataclass(frozen=True)
class _ObservedSource:
    resolved_revision: GitRevision | None
    swhid: Swhid | None
    history: SourceHistory | None = None
    history_digest: Digest | None = None
    lfs_files: tuple[LfsFile, ...] = ()


def handle_acquire_source(
    args: AcquireSourceArgs,
    *,
    layout: ReeLayout,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    store = ReeDirectory(layout)
    if not store.manifest_exists():
        return ActionResult.failed("precondition", "no REE here: run `ree initialize-ree` first")

    try:
        acquisition = _acquisition_from(args)
        ree = load_ree(layout, store)
        if (current := _current_receipt(layout, ree, acquisition)) is not None:
            log("system", "info", "this source is acquired already and current: nothing to do")
            return ActionResult(
                status="succeeded", exit_code=0, outputs=_outputs(acquisition, current).model_dump(exclude_none=True)
            )
        _check_preconditions(ree, acquisition, layout)
    except ReePreconditionError as exc:
        log("system", "error", f"cannot acquire a source: {exc}")
        return ActionResult.failed("precondition", f"cannot acquire a source: {exc}")
    except ValueError as exc:
        log("system", "error", f"invalid source request: {exc}")
        return ActionResult.failed("validation", f"invalid source request: {exc}")

    before_revision = revision_of(ree)
    timer = OperationTimer.start()
    performed = _perform(layout, acquisition, log=log, is_canceled=is_canceled)
    if isinstance(performed, ActionResult):
        return performed
    snapshot_digest = performed
    try:
        observed = _observe_acquired_source(layout, acquisition.definition, log=log)
    except SourceHistoryError as exc:
        log("system", "error", f"the source's history could not be packed: {exc}")
        return ActionResult.failed("execution", f"the source's history could not be packed: {exc}")
    except LfsPayloadError as exc:
        log("system", "error", f"the source's Git LFS files did not arrive whole: {exc}")
        return ActionResult.failed("validation", f"the source's Git LFS files did not arrive whole: {exc}")
    try:
        _validate_observation(acquisition.definition, observed, log=log)
    except ValueError as exc:
        log("system", "error", f"acquired source failed identity validation: {exc}")
        return ActionResult.failed("validation", str(exc))
    timing = timer.finish()

    receipt = AcquireSourceReceipt(
        **receipt_envelope(run_id, timing),
        origin_url=acquisition.definition.origin_url,
        source_type=acquisition.definition.source_type,
        requested_ref=acquisition.definition.requested_ref,
        resolved_revision=observed.resolved_revision,
        history=observed.history,
        history_digest=observed.history_digest,
        observed_swhid=observed.swhid,
        snapshot_digest=snapshot_digest,
        lfs_files=observed.lfs_files,
    )
    updated = ree
    if updated.subject.definition.source is None:
        updated = replace_definition(
            updated,
            updated.subject.definition.model_copy(update={"source": acquisition.definition}),
        )
    updated = commit_receipt(updated, receipt)
    try:
        save_ree(layout, store, updated, expected_revision=before_revision)
    except Exception as exc:
        log("system", "error", f"failed to commit acquired source: {exc}")
        return failed_from_exception(exc, f"failed to commit acquired source: {exc}")

    materialized = materialize_workspace(
        layout,
        snapshot_digest=snapshot_digest,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = _outputs(acquisition, receipt).model_dump(exclude_none=True)
    if materialized.status != "succeeded":
        log("system", "error", "source acquired, but the workspace could not be materialized")
        return materialized.model_copy(update={"outputs": outputs})
    log(
        "system",
        "info",
        f"acquire_source succeeded in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs)


def _acquisition_from(args: AcquireSourceArgs) -> _Acquisition:
    requested_ref = args.revision.strip() or None
    if args.mode == "download":
        if not args.origin_url.strip():
            raise ValueError("a download acquisition needs an origin URL")
        if args.source_type is None:
            raise ValueError("a download acquisition needs a source type")
        if args.source_type != "git" and args.history is not None:
            raise ValueError("only a git source has a history to carry")
        return _Acquisition(
            mode="download",
            definition=SourceDefinition(
                origin_url=args.origin_url.strip(),
                source_type=args.source_type,
                requested_ref=requested_ref,
                history=(args.history or "full") if args.source_type == "git" else None,
            ),
        )
    if args.history is not None:
        raise ValueError("an uploaded archive has no history to carry")
    if not args.upload_token or not args.archive_name:
        raise ValueError("an upload acquisition needs an upload token and archive name")
    source_type: Literal["zip", "tarball"] = "zip" if args.archive_name.lower().endswith(".zip") else "tarball"
    return _Acquisition(
        mode="upload",
        definition=SourceDefinition(source_type=source_type),
        upload_token=args.upload_token,
        archive_name=args.archive_name,
    )


def _current_receipt(layout: ReeLayout, ree: Ree, acquisition: _Acquisition) -> AcquireSourceReceipt | None:
    receipt = ree.subject.receipts.acquire_source
    if receipt is None or ree.seal is not None or acquisition.mode != "download":
        return None
    if ree.subject.definition.source != acquisition.definition or audit(ree).acquire_source.evidence != "current":
        return None
    archive = layout.snapshot_archive
    if not archive.is_file() or digest_file(archive) != receipt.snapshot_digest:
        return None
    if receipt.history_digest is None:
        return receipt
    held = layout.source_history
    return receipt if held.is_file() and digest_file(held) == receipt.history_digest else None


def _check_preconditions(ree: Ree, acquisition: _Acquisition, layout: ReeLayout) -> None:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot acquire a source")
    if ree.subject.receipts.acquire_source is not None:
        raise ReePreconditionError("this REE already has a source; remove it before acquiring another")
    current = ree.subject.definition.source
    if current is not None and current != acquisition.definition:
        raise ReePreconditionError("the acquisition request does not match the current source definition")
    slot = observe_source_slot(layout, upload_token=acquisition.upload_token)
    if slot.upstream_populated or slot.snapshot_archive_present:
        raise ReePreconditionError(
            "source content exists without committed acquisition evidence; remove the source before retrying"
        )
    if acquisition.mode == "upload" and not slot.staged_upload_present:
        raise ReePreconditionError("the staged upload is no longer available")


def _perform(
    layout: ReeLayout,
    acquisition: _Acquisition,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> Digest | ActionResult:
    snapshot_digest: Digest | None = None
    if acquisition.mode == "upload":
        try:
            snapshot_digest = freeze_upload(
                layout,
                upload_token=acquisition.upload_token,
                archive_name=acquisition.archive_name,
                log=log,
            )
        except Exception as exc:
            log("system", "error", f"upload ingest failed: {exc}")
            return ActionResult.failed("validation", f"upload ingest failed: {exc}")

    acquired = _run_acquire_script(layout, acquisition.definition, log=log, is_canceled=is_canceled)
    if acquired.canceled or is_canceled():
        return ActionResult(status="canceled")
    if acquired.returncode != 0:
        return ActionResult.failed(
            "execution",
            f"acquire script exited {acquired.returncode}",
            exit_code=acquired.returncode or 1,
        )
    if snapshot_digest is not None:
        return snapshot_digest
    try:
        return freeze_upstream(layout, log=log)
    except SNAPSHOT_FAILURES as exc:
        log("system", "error", f"snapshot failed: {exc}")
        return failed_from_exception(exc, f"snapshot failed: {exc}")


def _write_acquire_script(definition: SourceDefinition, *, log: LogSink, layout: ReeLayout) -> Path:
    write_atomic(
        layout.acquire_script,
        build_acquire_sh(
            origin_url=definition.origin_url or "",
            source_type=definition.source_type,
            revision=definition.requested_ref or "",
            history=definition.history or "tip",
        ),
    )
    log("system", "info", f"wrote acquire script → {ACQUIRE_SCRIPT_FILENAME}")
    return layout.acquire_script


def _run_acquire_script(
    layout: ReeLayout,
    definition: SourceDefinition,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> StreamingProcessResult:
    log("system", "info", f"acquire: {definition.source_type} {definition.origin_url or 'snapshot'}")
    script = _write_acquire_script(definition, log=log, layout=layout)
    command = ["sh", str(script)]
    log("system", "info", format_command(command))
    return run_streaming_process(command, log=log, is_canceled=is_canceled)


def _observe_acquired_source(
    layout: ReeLayout,
    definition: SourceDefinition,
    *,
    log: LogSink,
) -> _ObservedSource:
    lfs = lfs_manifest(layout.upstream, "HEAD") if definition.source_type == "git" else {}
    if lfs:
        log("system", "info", f"the source keeps {len(lfs)} files in Git LFS: each holds to its pointer")
    swhid: Swhid | None = None
    try:
        observed = directory_swhid(layout.upstream, lfs=lfs)
        swhid = Swhid(observed) if observed else None
    except LfsPayloadError:
        raise
    except Exception as exc:
        log("system", "warn", f"swhid computation skipped: {exc}")
    if definition.source_type != "git":
        return _ObservedSource(resolved_revision=None, swhid=swhid)
    packed = pack_source_history(layout.upstream, layout.source_history)
    log("system", "info", f"packed the source's history ({packed.history}) → {layout.source_history.name}")
    return _ObservedSource(
        resolved_revision=packed.revision,
        swhid=swhid,
        history=packed.history,
        history_digest=packed.digest,
        lfs_files=lfs_files(lfs),
    )


def _validate_observation(definition: SourceDefinition, observed: _ObservedSource, *, log: LogSink) -> None:
    if definition.source_type == "git" and observed.resolved_revision is None:
        raise ValueError("git acquisition did not produce a resolved revision")
    requested = definition.requested_ref
    if (
        requested
        and observed.resolved_revision
        and re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", requested)
        and requested.lower() != observed.resolved_revision
    ):
        raise ValueError(f"requested immutable revision {requested!r} resolved to {observed.resolved_revision!r}")
    if definition.history == "full" and observed.history == "tip":
        log("system", "warn", "the origin served the commit alone: the source carries no history beyond it")


def _outputs(acquisition: _Acquisition, receipt: AcquireSourceReceipt) -> AcquireSourceOutputs:
    return AcquireSourceOutputs(
        mode=acquisition.mode,
        origin_url=receipt.origin_url,
        source_type=receipt.source_type,
        requested_ref=receipt.requested_ref,
        resolved_revision=str(receipt.resolved_revision) if receipt.resolved_revision else None,
        history=receipt.history,
        upload_token=acquisition.upload_token or None,
        archive_name=acquisition.archive_name or None,
        snapshot_digest=str(receipt.snapshot_digest),
        swhid=str(receipt.observed_swhid) if receipt.observed_swhid else None,
    )
