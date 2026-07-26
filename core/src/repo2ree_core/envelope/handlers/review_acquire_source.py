"""Acquire and verify source identity inside an isolated review attempt.

Two ways to get a tree to verify, and the choice is the reviewer's:

* ``independent`` — fetch the recorded origin, exactly as the author first did.
  The strong form: agreement means the origin still serves the authored source.
* ``bundled`` — extract the REE's own ``snapshot.tar.gz``. No network, no live
  origin, and it is the only path open for an REE whose source was uploaded
  rather than fetched. Agreement means the carried bytes hash to the recorded
  identity — the bundle is intact — which is an integrity check, not an
  independent reproduction, and is recorded as such on the comparison.

Either way the same generated ``acquire_source.sh`` does the work, and the same
SWHID comparison judges it; only what lands next to the script differs.
"""

from __future__ import annotations

import shutil

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.envelope.handlers._review_common import review_step_halt
from repo2ree_core.receipts import AcquireSourceReceipt, receipt_run_id
from repo2ree_core.ree_scripts.acquire_source import build_acquire_sh
from repo2ree_core.reviews import (
    EvidenceBasis,
    SourceComparison,
    compare_source_swhids,
    new_review_record,
    with_step,
    write_review_record,
    write_review_source_evidence,
)
from repo2ree_core.run_script import CancelCheck, format_command, run_streaming_process
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.storage.layout import ReeLayout, ReviewLayout
from repo2ree_core.storage.store import ReeStore
from repo2ree_core.time_utils import OperationTimer, format_duration_ms
from repo2ree_protocol.command import ReviewAcquireSourceArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class ReviewAcquireSourceOutputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    receipt: AcquireSourceReceipt
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
    intent = ReeStore(ree_layout).read_intent()
    timer = OperationTimer.start()

    started = with_step(
        new_review_record(args.review_id, at=timer.started_at),
        "source",
        status="running",
        at=timer.started_at,
    )
    write_review_record(review_layout, started)

    stop = review_step_halt(
        review_layout=review_layout,
        record=started,
        step="source",
        review_id=args.review_id,
        timer=timer,
        log=log,
        noun="review source acquisition",
    )

    if is_canceled():
        return stop("canceled", "canceled before source acquisition")

    has_origin = _has_acquirable_origin(intent)
    has_snapshot = ree_layout.snapshot_archive.is_file()
    basis = _resolve_basis(args.basis, has_origin=has_origin, has_snapshot=has_snapshot)
    if basis is None:
        return stop("failed", _basis_refusal(args.basis))

    review_layout.root.mkdir(parents=True, exist_ok=True)
    _stage_acquisition(ree_layout, review_layout, intent, basis=basis, log=log)
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
    comparison = compare_source_swhids(intent.swhid, observed_swhid, basis=basis)
    timing = timer.finish()
    receipt = AcquireSourceReceipt(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status="succeeded",
        # Origin facts describe a fetch. A bundled acquisition performed none,
        # so the receipt records none rather than implying the origin was reached.
        origin_url=intent.origin_url if basis == "independent" else "",
        source_type=intent.source_type if basis == "independent" else "",
        revision=intent.revision if basis == "independent" else "",
        expected_swhid=comparison.expected_swhid,
        observed_swhid=comparison.observed_swhid,
    )
    write_review_source_evidence(review_layout, receipt, comparison)
    write_review_record(
        review_layout,
        with_step(
            started.model_copy(update={"source_receipt": receipt, "source_comparison": comparison}),
            "source",
            status="completed",
            at=timing.finished_at,
        ),
    )
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
    log(
        "system",
        "info",
        f"review source acquisition succeeded in {format_duration_ms(timing.duration_ms)} "
        f"(duration_ms={timing.duration_ms})",
    )
    outputs = ReviewAcquireSourceOutputs(
        review_id=args.review_id,
        receipt=receipt,
        comparison=comparison,
    )
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs.model_dump(mode="json"))


def _has_acquirable_origin(intent: ReeIntent) -> bool:
    """Whether the baseline names an origin a reviewer could fetch for themselves.

    The version-control types the generated script cannot drive (hg, svn, ...)
    are as good as originless here, so they fall back like an upload does.
    """
    return bool(intent.origin_url) and intent.source_type in {"git", "tarball", "zip"}


def _resolve_basis(requested: str, *, has_origin: bool, has_snapshot: bool) -> EvidenceBasis | None:
    """Settle the requested basis against what the baseline actually carries.

    ``auto`` prefers the independent path and falls back to the snapshot, so a
    reviewer who states no preference always gets the strongest evidence
    available. An explicit request is never silently downgraded — asking for a
    reproduction and receiving an integrity check would be the one failure this
    module cannot afford — so it fails instead, and the caller reports why.
    """
    if requested == "independent":
        return "independent" if has_origin else None
    if requested == "bundled":
        return "bundled" if has_snapshot else None
    if has_origin:
        return "independent"
    return "bundled" if has_snapshot else None


def _basis_refusal(requested: str) -> str:
    if requested == "independent":
        return "The author baseline has no independently acquirable source origin"
    if requested == "bundled":
        return "This REE carries no source snapshot to reproduce from"
    # auto only refuses when it had nothing at all to choose between.
    return "The author baseline has neither an acquirable source origin nor a bundled snapshot"


def _stage_acquisition(
    ree_layout: ReeLayout,
    review_layout: ReviewLayout,
    intent: ReeIntent,
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
        review_layout.acquire_script.write_bytes(build_acquire_sh(swhid=intent.swhid))
        return
    review_layout.snapshot_archive.unlink(missing_ok=True)
    review_layout.acquire_script.write_bytes(
        build_acquire_sh(
            origin_url=intent.origin_url,
            source_type=intent.source_type,
            revision=intent.revision,
            swhid=intent.swhid,
        )
    )
