"""The acquire-source lifecycle: the one operation that gives an REE a source.

An REE holds at most one source, and acquiring is only legal into an empty
slot. This workflow never clears one — there is no replace. A source already
present is the author's, and giving it up is a separate act they perform with
``remove_source``; only then can another be acquired. That refusal is the
whole reason the preconditions in
:func:`~repo2ree_core.domain.ree.transitions.plan_source_acquisition` can mean
anything: a workflow that reset first — even one asked politely to — would
have erased every condition it might have refused on, which is precisely how
a sealed REE could once be silently unsealed by acquiring over it.

The stages, and why they are in this order::

    hydrate    the whole REE, once
    observe    the source slot on disk (impure)
    decide     plan_source_acquisition — refuses, or names the effect
    perform    fetch/freeze/thaw (impure, uncommitted)
    observe    swhid, resolved commit, snapshot digest (impure)
    settle     the receipts for what ran
    apply      the REE this acquisition leaves behind (pure)
    persist    one save, the commit point
    ---------- the workspace view is rebuilt after the commit

Observation happens twice because acquisition needs it twice: the slot has to
be empty *before* deciding, and everything the acquisition settles — the
identity of the tree it produced — can only be read *after* the effect. What
matters is not that observation happens once, but that it happens nowhere else.

Every partial state this can leave behind is refused by the next acquisition
with one instruction: remove the source first. That is also what makes an
interrupted run detectable at all — an acquisition killed mid-effect leaves the
state saying "no source" while the disk says otherwise, and the slot check
above is what notices.

The two modes converge on the snapshot archive, which is the canonical source;
``upstream/`` is materialized from it::

    download   fetch origin → upstream/,  then freeze upstream/ → snapshot
    upload     freeze staged → snapshot,  then thaw snapshot → upstream/
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.authoring.script_generation.acquire_source import build_acquire_sh
from repo2ree_core.digests import Digest
from repo2ree_core.domain.primitives import GitRevision, ReePath, Swhid
from repo2ree_core.domain.ree.receipt import (
    AcquireSourceReceipt,
    RunReceipt,
    SnapshotUpstreamReceipt,
    receipt_envelope,
)
from repo2ree_core.domain.ree.transitions import (
    AcquiredSource,
    ReePreconditionError,
    SourceAcquired,
    SourcePlan,
    SourceRequest,
    apply_source_acquired,
    plan_source_acquisition,
)
from repo2ree_core.execution.process import (
    CancelCheck,
    StreamingProcessResult,
    format_command,
    run_streaming_process,
)
from repo2ree_core.failures import failed_from_exception
from repo2ree_core.operations.handlers.author.extract_upload import freeze_upload
from repo2ree_core.operations.handlers.author.materialize_workspace import materialize_workspace
from repo2ree_core.operations.handlers.author.snapshot_upstream import SNAPSHOT_FAILURES, freeze_upstream
from repo2ree_core.operations.steps.author import log_step_outcome, open_ree_store
from repo2ree_core.persistence.files import write_atomic
from repo2ree_core.persistence.layout import ACQUIRE_SCRIPT_FILENAME, SNAPSHOT_FILENAME, ReeLayout
from repo2ree_core.persistence.repository import load_ree, observe_source_slot, save_ree
from repo2ree_core.source_repo import directory_swhid, resolved_git_head
from repo2ree_core.time_utils import OperationTimer, OperationTiming, utc_now_instant
from repo2ree_protocol.command import AcquireSourceArgs
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult


class AcquireSourceOutputs(BaseModel):
    """What the workflow acquired, in the vocabulary of the mode it ran in.

    The fields of the other mode stay unset and are dropped on the way out, so
    a client reads back exactly the inputs that were acted on.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["download", "upload"]
    origin_url: str | None = None
    source_type: str | None = None
    revision: str | None = None
    upload_token: str | None = None
    archive_name: str | None = None
    snapshot_digest: str | None = None
    swhid: str | None = None


def handle_acquire_source(
    args: AcquireSourceArgs,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ActionResult:
    opened = open_ree_store(log)
    if isinstance(opened, ActionResult):
        return opened
    layout, store = opened

    ree = load_ree(layout, store)
    slot = observe_source_slot(layout, upload_token=args.upload_token)
    try:
        plan = plan_source_acquisition(
            ree,
            slot,
            _request_from(args),
            snapshot_archive=ReePath(SNAPSHOT_FILENAME),
        )
    except ReePreconditionError as exc:
        log("system", "error", f"cannot acquire a source: {exc}")
        return ActionResult.failed("precondition", f"cannot acquire a source: {exc}")
    except ValueError as exc:
        log("system", "error", f"invalid source request: {exc}")
        return ActionResult.failed("validation", f"invalid source request: {exc}")

    performed = _perform(layout, plan, run_id=run_id, log=log, is_canceled=is_canceled)
    if isinstance(performed, ActionResult):
        # Nothing is committed on the way out, so whatever the effects left on
        # disk is unrecorded — and the next acquisition refuses on exactly that.
        return performed
    snapshot_digest, receipts = performed

    observed = _observe_acquired_source(layout, snapshot_digest=snapshot_digest, log=log)
    updated = apply_source_acquired(
        ree,
        SourceAcquired(plan=plan, observed=observed, receipts=receipts),
    )
    try:
        save_ree(layout, store, updated, expected_revision=plan.before_revision, status="ready", log=log)
    except Exception as exc:
        log("system", "error", f"failed to record the acquired source: {exc}")
        return failed_from_exception(exc, f"failed to record the acquired source: {exc}")

    # Past the commit point. The workspace is a materialized view, outside the
    # transactional scope by design, so a failure here leaves a fully acquired
    # source the author can re-materialize — it does not undo the acquisition.
    materialized = materialize_workspace(
        layout,
        snapshot_digest=snapshot_digest,
        log=log,
        is_canceled=is_canceled,
    )
    outputs = _outputs(plan, observed).model_dump(exclude_none=True)
    if materialized.status != "succeeded":
        log("system", "error", "source acquired, but the workspace could not be materialized")
        return materialized.model_copy(update={"outputs": outputs})
    return ActionResult(status="succeeded", exit_code=0, outputs=outputs)


def _request_from(args: AcquireSourceArgs) -> SourceRequest:
    return SourceRequest(
        mode=args.mode,
        origin_url=args.origin_url,
        source_type=args.source_type or "",
        requested_revision=args.revision,
        upload_token=args.upload_token,
        archive_name=ReePath(args.archive_name) if args.archive_name else None,
    )


def _perform(
    layout: ReeLayout,
    plan: SourcePlan,
    *,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> tuple[Digest, tuple[RunReceipt, ...]] | ActionResult:
    """Run this plan's effects, or the failure to stop the workflow with.

    Returns the snapshot digest and the receipts for the steps that ran. Each
    step is timed on its own and receipted under its own run id: two receipts
    sharing the workflow's run id would land on the same path in ``runs/`` and
    the second would replace the first.
    """
    # Each freeze is timed around itself, never around the acquire beside it: a
    # receipt's duration describes the step it is a receipt for, and one clock
    # spanning both would overstate whichever ran second.
    frozen: tuple[Digest, OperationTiming] | None = None
    if plan.mode == "upload":
        # An upload has no origin, so its snapshot *is* the source: freeze the
        # staged bytes first, then let the acquire script thaw them.
        snapshot_timer = OperationTimer.start()
        try:
            digest = freeze_upload(
                layout,
                upload_token=plan.upload_token,
                archive_name=str(plan.archive_name),
                log=log,
            )
        except Exception as exc:
            log("system", "error", f"upload ingest failed: {exc}")
            return ActionResult.failed("validation", f"upload ingest failed: {exc}")
        frozen = (digest, snapshot_timer.finish())

    acquire_timer = OperationTimer.start()
    acquired = _run_acquire_script(layout, plan, log=log, is_canceled=is_canceled)
    acquire_timing = acquire_timer.finish()
    if acquired.canceled or is_canceled():
        log_step_outcome("acquire_source", "canceled", acquire_timing, log=log)
        return ActionResult(status="canceled")
    if acquired.returncode != 0:
        log_step_outcome("acquire_source", "failed", acquire_timing, log=log)
        return ActionResult.failed(
            "execution",
            f"acquire script exited {acquired.returncode}",
            exit_code=acquired.returncode or 1,
        )
    log_step_outcome("acquire_source", "succeeded", acquire_timing, log=log)

    if frozen is None:
        snapshot_timer = OperationTimer.start()
        try:
            frozen = (freeze_upstream(layout, log=log), snapshot_timer.finish())
        except SNAPSHOT_FAILURES as exc:
            log("system", "error", f"snapshot failed: {exc}")
            return failed_from_exception(exc, f"snapshot failed: {exc}")
    snapshot_digest, snapshot_timing = frozen
    log_step_outcome("snapshot_upstream", "succeeded", snapshot_timing, log=log)

    return snapshot_digest, (
        AcquireSourceReceipt(
            **receipt_envelope(f"{run_id}-acquire", acquire_timing, "succeeded"),
            origin_url=plan.origin_url,
            source_type=plan.source_type,
            revision=GitRevision(plan.requested_revision) if plan.requested_revision else None,
        ),
        SnapshotUpstreamReceipt(
            **receipt_envelope(f"{run_id}-snapshot", snapshot_timing, "succeeded"),
            snapshot_digest=snapshot_digest,
        ),
    )


def _write_acquire_script(plan: SourcePlan, *, log: LogSink, layout: ReeLayout) -> Path:
    """Persist ``acquire_source.sh`` (baked with this source's identity) in the REE.

    Written to the reserved root path so it is sealed into the bundle and run.sh
    can call the very same file. The SWHID is unknown at authoring time (it is
    computed after acquisition); seal regenerates the script with it baked in
    for the bundle.

    An upload bakes in nothing: it carries no origin and no ref, its snapshot is
    already on disk, and the script's snapshot-vs-fetch decision resolves to
    extracting it.
    """
    write_atomic(
        layout.acquire_script,
        build_acquire_sh(
            origin_url=plan.origin_url,
            source_type=plan.source_type,
            revision=plan.requested_revision,
        ),
    )
    log("system", "info", f"wrote acquire script → {ACQUIRE_SCRIPT_FILENAME}")
    return layout.acquire_script


def _run_acquire_script(
    layout: ReeLayout,
    plan: SourcePlan,
    *,
    log: LogSink,
    is_canceled: CancelCheck,
) -> StreamingProcessResult:
    """Write the acquire script for this source and run it into ``upstream/``.

    The script owns the fixed REE layout paths and the snapshot-vs-fetch
    decision — extract the frozen snapshot when there is one, otherwise fetch
    the recorded origin and verify it against the SWHID — so this only bakes in
    the source's identity and drives it. It is the same file ``run.sh`` calls
    from a sealed bundle, which is what keeps the two surfaces from drifting.
    """
    log(
        "system",
        "info",
        f"acquire: {plan.source_type or 'snapshot'} {plan.origin_url} → {layout.upstream}",
    )
    script = _write_acquire_script(plan, log=log, layout=layout)
    cmd = ["sh", str(script)]
    log("system", "info", format_command(cmd))
    return run_streaming_process(cmd, log=log, is_canceled=is_canceled)


def _observe_acquired_source(layout: ReeLayout, *, snapshot_digest: Digest, log: LogSink) -> AcquiredSource:
    """Read the identity of the tree the acquisition produced.

    Both identifiers are best-effort: a missing tree or a hashing failure must
    not lose a source that was genuinely acquired, so an unreadable identity is
    recorded as absent rather than raised. They are the only impure reads this
    workflow makes after its effects, which is what keeps the apply above a
    pure function of values somebody else observed.
    """
    swhid = ""
    try:
        swhid = directory_swhid(layout.upstream)
    except Exception as exc:  # an unhashable tree is not a failed acquisition
        log("system", "warn", f"swhid computation skipped: {exc}")
    if swhid:
        log("system", "info", f"source swhid: {swhid}")

    # Read HEAD from the acquired tree rather than trusting the requested ref:
    # this is the concrete commit a seal pins so a re-fetch lands here again,
    # and it is empty for a tree that carries no git history.
    revision = ""
    try:
        revision = resolved_git_head(layout.upstream)
    except Exception as exc:  # same reasoning as the swhid above
        log("system", "warn", f"revision resolution skipped: {exc}")
    if revision:
        log("system", "info", f"source revision: {revision}")

    return AcquiredSource(
        captured_at=utc_now_instant(),
        snapshot_digest=snapshot_digest,
        resolved_commit=GitRevision(revision) if revision else None,
        swhid=Swhid(swhid) if swhid else None,
    )


def _outputs(plan: SourcePlan, observed: AcquiredSource) -> AcquireSourceOutputs:
    if plan.mode == "download":
        return AcquireSourceOutputs(
            mode="download",
            origin_url=plan.origin_url,
            source_type=plan.source_type,
            revision=str(observed.resolved_commit) if observed.resolved_commit else plan.requested_revision,
            snapshot_digest=str(observed.snapshot_digest),
            swhid=str(observed.swhid) if observed.swhid else None,
        )
    return AcquireSourceOutputs(
        mode="upload",
        upload_token=plan.upload_token,
        archive_name=str(plan.archive_name) if plan.archive_name else None,
        snapshot_digest=str(observed.snapshot_digest),
        swhid=str(observed.swhid) if observed.swhid else None,
    )
