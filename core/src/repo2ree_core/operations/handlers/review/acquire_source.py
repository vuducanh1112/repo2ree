"""Acquire and verify source identity inside an isolated review attempt.

Two ways to get a tree to verify, and the choice is the reviewer's:

* ``independent`` — fetch the recorded origin, exactly as the author first did.
  The strong form: agreement means the origin still serves the authored source.
* ``bundled`` — extract the REE's own ``snapshot.tar.gz``. No network, no live
  origin, and the only path open for an REE whose source was uploaded rather
  than fetched. Agreement means the bundle is intact — an integrity check, not
  an independent reproduction, and recorded as such on the comparison.

Either way the same generated ``acquire_source.sh`` does the work, and the same
SWHID comparison judges it; only what lands next to the script differs.
"""

from __future__ import annotations

import shutil

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.primitives import Swhid
from repo2ree_core.domain.ree.model import Ree, SourceDefinition
from repo2ree_core.evidence.review.comparison import compare_source_swhids
from repo2ree_core.evidence.review.models import (
    EvidenceBasis,
    ReviewAcquireSourceReceipt,
    SourceComparison,
    new_review_record,
    resolve_basis,
    review_receipt_envelope,
)
from repo2ree_core.evidence.review.store import write_review_source_evidence
from repo2ree_core.execution.process import CancelCheck, format_command, run_streaming_process
from repo2ree_core.operations.steps.review import begin_review_step, require_ree_baseline
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.reproduction.acquire_source import build_acquire_sh
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.time_utils import OperationTimer, format_utc_instant
from repo2ree_protocol.command import ReviewAcquireSourceArgs, ReviewBasis
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewAcquireSourceOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: ReviewAcquireSourceReceipt
    comparison: SourceComparison


def handle_review_acquire_source(
    args: ReviewAcquireSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    ree_layout = ReeLayout.in_workbench()
    review_layout = ree_layout.review(args.review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(ree_layout, log=log)
    if isinstance(ree, ActionResult):
        return ree

    # The one step that opens an attempt rather than joining one: there is no
    # record to require, so it starts from a freshly minted one.
    step = begin_review_step(
        review_layout,
        new_review_record(args.review_id, at=format_utc_instant(timer.started_at)),
        "source",
        review_id=args.review_id,
        timer=timer,
        log=log,
        noun="review source acquisition",
    )
    started, stop = step.record, step.stop

    if is_canceled():
        return stop("canceled", "canceled before source acquisition")

    basis = resolve_basis(args.basis, available=_available_bases(ree, ree_layout))
    if basis is None:
        return stop("failed", _basis_refusal(args.basis))

    review_layout.root.mkdir(parents=True, exist_ok=True)
    _stage_acquisition(ree_layout, review_layout, ree, basis=basis, log=log)
    command = ["sh", str(review_layout.acquire_script)]
    source_of = "the recorded origin" if basis == "independent" else "the REE's own snapshot"
    log("system", "info", f"review {args.review_id}: acquiring source from {source_of} into {review_layout.upstream}")
    log("system", "info", format_command(command))
    result = run_streaming_process(command, log=log, is_canceled=is_canceled)
    if result.canceled or is_canceled():
        return stop("canceled", "source acquisition canceled")
    if result.returncode != 0:
        return stop("failed", f"acquire script exited {result.returncode}")

    observed_swhid = directory_swhid(review_layout.upstream)
    source = ree.subject.definition.source
    author_source = ree.subject.receipts.source
    expected_swhid = str(author_source.observed_swhid) if author_source and author_source.observed_swhid else ""
    comparison = compare_source_swhids(expected_swhid, observed_swhid, basis=basis)
    timing = timer.finish()
    receipt = ReviewAcquireSourceReceipt(
        **review_receipt_envelope(run_id, timing, "succeeded"),
        # Origin facts describe a fetch. A bundled acquisition performed none,
        # so the receipt records none rather than implying the origin was reached.
        origin_url=source.origin_url if basis == "independent" and source else None,
        source_type=source.source_type if basis == "independent" and source else "",
        requested_ref=source.requested_ref if basis == "independent" and source else None,
        expected_swhid=Swhid(comparison.expected_swhid) if comparison.expected_swhid else None,
        observed_swhid=Swhid(comparison.observed_swhid) if comparison.observed_swhid else None,
    )
    write_review_source_evidence(review_layout, receipt, comparison)
    log(
        "system",
        "info" if comparison.verdict == "identical" else "warn",
        f"source comparison {comparison.verdict} ({basis}): expected {comparison.expected_swhid or 'none'}, "
        f"observed {comparison.observed_swhid or 'none'}",
    )
    if basis == "bundled":
        log(
            "system",
            "warn",
            "this verdict certifies the bundle's own snapshot — the recorded origin was never contacted, "
            "so it is an integrity check rather than an independent reproduction",
        )
    step.settle(
        started.model_copy(update={"source_receipt": receipt, "source_comparison": comparison}),
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


def _has_acquirable_origin(source: SourceDefinition | None) -> bool:
    """Whether the baseline names an origin a reviewer could fetch for themselves.

    The version-control types the generated script cannot drive (hg, svn, ...)
    are as good as originless here, so they fall back like an upload does.
    """
    return source is not None and bool(source.origin_url) and source.source_type in {"git", "tarball", "zip"}


def _available_bases(ree: Ree, ree_layout: ReeLayout) -> set[EvidenceBasis]:
    """Which bases this baseline can actually offer a source acquisition."""
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
    # auto only refuses when it had nothing at all to choose between.
    return "The author baseline has neither an acquirable source origin nor a bundled snapshot"


def _stage_acquisition(
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    ree: Ree,
    *,
    basis: EvidenceBasis,
    log: LogSink,
) -> None:
    """Put the acquire script — and, for a bundled basis, its input — in place.

    ``acquire_source.sh`` derives every path from its own directory and prefers
    a snapshot sitting beside it to any origin, which is exactly the switch the
    two bases need: generate it with the origin baked in and the attempt fetches;
    copy the snapshot in and generate it bare, and the attempt extracts.

    The snapshot is *copied* rather than read across from the author's tree, for
    the same reason the overlay is: the attempt is a parallel REE, and a script
    that reaches into author evidence to work is one edit away from writing
    there. The copy also stays as the attempt's own record of what it verified.

    Any previously acquired tree is cleared first. The script deliberately
    leaves a populated upstream alone, which would otherwise make re-running the
    step on a different basis a no-op that reports the old tree's verdict.
    """
    shutil.rmtree(review_layout.upstream, ignore_errors=True)
    if basis == "bundled":
        shutil.copyfile(ree_layout.snapshot_archive, review_layout.snapshot_archive)
        log("system", "info", f"staged the author snapshot into {review_layout.snapshot_archive}")
        author_source = ree.subject.receipts.source
        expected_swhid = str(author_source.observed_swhid) if author_source and author_source.observed_swhid else ""
        write_atomic(review_layout.acquire_script, build_acquire_sh(swhid=expected_swhid))
        return
    source = ree.subject.definition.source
    if source is None:
        raise ValueError("independent source acquisition requires a source definition")
    author_source = ree.subject.receipts.source
    expected_swhid = str(author_source.observed_swhid) if author_source and author_source.observed_swhid else ""
    review_layout.snapshot_archive.unlink(missing_ok=True)
    write_atomic(
        review_layout.acquire_script,
        build_acquire_sh(
            origin_url=source.origin_url or "",
            source_type=source.source_type,
            revision=source.requested_ref or "",
            swhid=expected_swhid,
        ),
    )
