from __future__ import annotations

import shutil

from repo2ree_core.evidence.review.comparison import compare_source_swhids
from repo2ree_core.evidence.review.records import (
    new_review_record,
    resolve_basis,
    review_receipt_envelope,
    review_subject,
)
from repo2ree_core.evidence.review.store import write_review_source_evidence
from repo2ree_core.execution.process import CancelCheck, format_command, run_streaming_process
from repo2ree_core.operations.steps.review import begin_review_step, refuse_signed_review, require_ree_baseline
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.lfs import LfsPointer
from repo2ree_core.reproduction.acquire_source import build_acquire_sh
from repo2ree_core.source_repo import (
    LfsPayloadError,
    SourceHistoryError,
    bundled_lfs_manifest,
    lfs_files,
    lfs_manifest,
    pack_source_history,
    verify_source_history,
)
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.time_utils import OperationTimer
from repo2ree_protocol.command import ReviewAcquireSourceArgs, ReviewBasis
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.outputs import ReviewAcquireSourceOutputs
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.model import Ree, SourceDefinition
from repo2ree_ree.primitives import GitRevision, SourceHistory, Swhid
from repo2ree_ree.receipt import AcquireSourceReceipt
from repo2ree_ree.review import EvidenceBasis, ReviewAcquireSourceReceipt


def handle_review_acquire_source(
    args: ReviewAcquireSourceArgs,
    *,
    layout: ReeLayout,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    review_layout = layout.review(args.review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(layout, log=log)
    if isinstance(ree, ActionResult):
        return ree
    if (refused := refuse_signed_review(review_layout, args.review_id, log)) is not None:
        return refused

    step = begin_review_step(
        review_layout,
        new_review_record(args.review_id, subject=review_subject(ree), at=timer.started_at, launch=args.launch),
        "acquire_source",
        review_id=args.review_id,
        timer=timer,
        log=log,
        noun="review source acquisition",
    )
    started, stop = step.record, step.stop

    if is_canceled():
        return stop("canceled", "canceled before source acquisition")

    basis = resolve_basis(args.basis, available=_available_bases(ree, layout))
    if basis is None:
        return stop("failed", _basis_refusal(args.basis))

    review_layout.root.mkdir(parents=True, exist_ok=True)
    _stage_acquisition(layout, review_layout, ree, basis=basis, log=log)
    command = ["sh", str(review_layout.acquire_script)]
    source_of = "the recorded origin" if basis == "independent" else "the REE's own snapshot"
    log("system", "info", f"review {args.review_id}: acquiring source from {source_of} into {review_layout.upstream}")
    log("system", "info", format_command(command))
    result = run_streaming_process(command, log=log, is_canceled=is_canceled)
    if result.canceled or is_canceled():
        return stop("canceled", "source acquisition canceled")
    if result.returncode != 0:
        return stop("failed", f"acquire script exited {result.returncode}")

    source = ree.subject.definition.source
    author_source = ree.subject.receipts.acquire_source
    lfs = _review_lfs(review_layout, author_source, basis=basis, log=log)
    lfs_failure: str | None = None
    try:
        observed_swhid = directory_swhid(review_layout.upstream, lfs=lfs)
    except LfsPayloadError as exc:
        log("system", "warn", f"the source's Git LFS files did not arrive whole: {exc}")
        observed_swhid, lfs_failure = "", str(exc)
    expected_swhid = str(author_source.observed_swhid) if author_source and author_source.observed_swhid else ""
    observed_revision, history, history_failure = _review_history(
        review_layout, author_source, observed_swhid, basis=basis, log=log
    )
    comparison = compare_source_swhids(
        expected_swhid,
        observed_swhid,
        basis=basis,
        expected_revision=author_source.resolved_revision if author_source else None,
        observed_revision=observed_revision,
        history_failure=history_failure,
        lfs_failure=lfs_failure,
    )
    timing = timer.finish()
    receipt = ReviewAcquireSourceReceipt(
        **review_receipt_envelope(run_id, timing, "succeeded"),
        origin_url=source.origin_url if basis == "independent" and source else None,
        source_type=source.source_type if basis == "independent" and source else "",
        requested_ref=source.requested_ref if basis == "independent" and source else None,
        expected_swhid=Swhid(comparison.expected_swhid) if comparison.expected_swhid else None,
        observed_swhid=Swhid(comparison.observed_swhid) if comparison.observed_swhid else None,
        expected_revision=comparison.expected_revision,
        observed_revision=observed_revision,
        history=history,
        lfs_files=lfs_files(lfs) if lfs_failure is None else (),
    )
    write_review_source_evidence(review_layout, receipt, comparison)
    log(
        "system",
        "info" if comparison.verdict == "identical" else "warn",
        f"source comparison {comparison.verdict} ({basis}): expected {comparison.expected_swhid or 'none'}, "
        f"observed {comparison.observed_swhid or 'none'}"
        + (
            f"; commit expected {comparison.expected_revision}, observed {observed_revision or 'none'}"
            if comparison.expected_revision
            else ""
        ),
    )
    if basis == "bundled":
        log(
            "system",
            "warn",
            "this verdict certifies the bundle's own snapshot — the recorded origin was never contacted, "
            "so it is an integrity check rather than an independent reproduction",
        )
    step.settle(
        started.model_copy(
            update={
                "receipts": started.receipts.model_copy(update={"acquire_source": receipt}),
                "source_comparison": comparison,
            }
        ),
        timing,
        verdict=comparison.verdict,
        basis=basis,
    )
    outputs = ReviewAcquireSourceOutputs(
        review_id=args.review_id,
        receipt=receipt,
        comparison=comparison,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _review_history(
    review_layout: ReviewLayout,
    author_source: AcquireSourceReceipt | None,
    observed_swhid: str,
    *,
    basis: EvidenceBasis,
    log: LogSink,
) -> tuple[GitRevision | None, SourceHistory | None, str | None]:
    if author_source is None or author_source.resolved_revision is None or author_source.history is None:
        return None, None, None
    held = review_layout.source_history
    try:
        if basis == "independent":
            packed = pack_source_history(review_layout.upstream, held)
            revision, history = packed.revision, packed.history
        else:
            revision, history = author_source.resolved_revision, author_source.history
        if not observed_swhid:
            return revision, history, "the source's files hold no identity to hold the history to"
        verify_source_history(held, revision=revision, swhid=Swhid(observed_swhid), history=history)
    except SourceHistoryError as exc:
        log("system", "warn", f"the source's history does not hold: {exc}")
        held.unlink(missing_ok=True)
        return None, None, str(exc)
    if history != author_source.history:
        return revision, history, f"the history is {history}, the author's {author_source.history}"
    log("system", "info", f"the source's history ({history}) holds commit {revision} and its files")
    return revision, history, None


def _review_lfs(
    review_layout: ReviewLayout,
    author_source: AcquireSourceReceipt | None,
    *,
    basis: EvidenceBasis,
    log: LogSink,
) -> dict[str, LfsPointer]:
    if author_source is None or author_source.resolved_revision is None or author_source.history is None:
        return {}
    try:
        if basis == "independent":
            lfs = lfs_manifest(review_layout.upstream, "HEAD")
        elif review_layout.source_history.is_file():
            lfs = bundled_lfs_manifest(
                review_layout.source_history, revision=author_source.resolved_revision, history=author_source.history
            )
        else:
            return {}
    except SourceHistoryError as exc:
        log("system", "warn", f"the files the source keeps in Git LFS could not be read: {exc}")
        return {}
    if lfs:
        log("system", "info", f"the source keeps {len(lfs)} files in Git LFS: each holds to its pointer")
    return lfs


def _has_acquirable_origin(source: SourceDefinition | None) -> bool:
    return source is not None and bool(source.origin_url) and source.source_type in {"git", "tarball", "zip"}


def _available_bases(ree: Ree, ree_layout: ReeLayout) -> set[EvidenceBasis]:
    available: set[EvidenceBasis] = set()
    if _has_acquirable_origin(ree.subject.definition.source):
        available.add("independent")
    if ree_layout.snapshot_archive.is_file():
        available.add("bundled")
    return available


def _basis_refusal(requested: ReviewBasis) -> str:
    if requested == "independent":
        return "The author baseline has no independently acquirable source origin"
    if requested == "bundled":
        return "This REE carries no source snapshot to reproduce from"
    return "The author baseline has neither an acquirable source origin nor a bundled snapshot"


def _stage_acquisition(
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    ree: Ree,
    *,
    basis: EvidenceBasis,
    log: LogSink,
) -> None:
    shutil.rmtree(review_layout.upstream, ignore_errors=True)
    review_layout.source_history.unlink(missing_ok=True)
    if basis == "bundled":
        shutil.copyfile(ree_layout.snapshot_archive, review_layout.snapshot_archive)
        log("system", "info", f"staged the author snapshot into {review_layout.snapshot_archive}")
        if ree_layout.source_history.is_file():
            shutil.copyfile(ree_layout.source_history, review_layout.source_history)
            log("system", "info", f"staged the author's source history into {review_layout.source_history}")
        author_source = ree.subject.receipts.acquire_source
        expected_swhid = str(author_source.observed_swhid) if author_source and author_source.observed_swhid else ""
        write_atomic(review_layout.acquire_script, build_acquire_sh(swhid=expected_swhid))
        return
    source = ree.subject.definition.source
    if source is None:
        raise ValueError("independent source acquisition requires a source definition")
    author_source = ree.subject.receipts.acquire_source
    expected_swhid = str(author_source.observed_swhid) if author_source and author_source.observed_swhid else ""
    review_layout.snapshot_archive.unlink(missing_ok=True)
    write_atomic(
        review_layout.acquire_script,
        build_acquire_sh(
            origin_url=source.origin_url or "",
            source_type=source.source_type,
            revision=str(author_source.resolved_revision)
            if author_source and author_source.resolved_revision
            else source.requested_ref or "",
            swhid=expected_swhid,
            history=author_source.history if author_source and author_source.history else "tip",
        ),
    )
