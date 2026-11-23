from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from repo2ree_core.digests import digest_file, digest_tree
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_core.evidence.review.records import attempt_basis, step_state, with_step
from repo2ree_core.evidence.review.store import read_review_record, write_review_record
from repo2ree_core.execution.experiment.run import ExperimentRunOutcome, run_runnable
from repo2ree_core.execution.experiment.spec import RunnableSpec
from repo2ree_core.execution.launch import Launch, declared_launch
from repo2ree_core.execution.process import CancelCheck
from repo2ree_core.persistence.directory import UNREADABLE_DOCUMENT, ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.time_utils import OperationTimer, OperationTiming, format_duration_ms
from repo2ree_core.workspace.attempt import environment_in_workspace, fresh, overlay_onto
from repo2ree_protocol.frames import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_ree.digest import Digest
from repo2ree_ree.model import Ree, ReeDefinition
from repo2ree_ree.review import (
    ActivationVerdict,
    ComparisonVerdict,
    EvidenceBasis,
    ExperimentEnvironmentVerdict,
    ExperimentVerdict,
    ReviewBuildExperimentEnvironmentReceipt,
    ReviewRecord,
    ReviewStatus,
    ReviewStepKey,
)
from repo2ree_ree.signature import review_signature_path
from repo2ree_telemetry.spans import ReviewStepAttrs

ReviewHalt = Callable[[ReviewStatus, str], ActionResult]

ReviewVerdict = ComparisonVerdict | ExperimentEnvironmentVerdict | ActivationVerdict | ExperimentVerdict


class ReviewSettle(Protocol):
    def __call__(
        self,
        record: ReviewRecord,
        timing: OperationTiming,
        *,
        verdict: ReviewVerdict | None = None,
        basis: EvidenceBasis | None = None,
        experiment_environment_digest: str | None = None,
    ) -> None: ...


@dataclass(frozen=True)
class ReviewStep:
    record: ReviewRecord
    stop: ReviewHalt
    settle: ReviewSettle


def require_ree_baseline(ree_layout: ReeLayout, *, log: LogSink) -> Ree | ActionResult:
    store = ReeDirectory(ree_layout)
    if not store.manifest_exists():
        message = "This workbench holds no REE to review"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)
    try:
        return store.read_ree()
    except UNREADABLE_DOCUMENT as exc:
        message = f"The REE under review has unreadable metadata: {exc}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)


def require_review_record(review_layout: ReviewLayout, review_id: str, log: LogSink) -> ReviewRecord | ActionResult:
    record = read_review_record(review_layout)
    if record is None:
        message = f"No review attempt named {review_id}"
        log("system", "error", message)
        return ActionResult.failed("precondition", message)
    if (refused := refuse_signed_review(review_layout, review_id, log)) is not None:
        return refused
    return record


def refuse_signed_review(review_layout: ReviewLayout, review_id: str, log: LogSink) -> ActionResult | None:
    if not (review_layout.root / review_signature_path()).is_file():
        return None
    message = f"Review {review_id} is signed, and a signed review changes no more: open a new review"
    log("system", "error", message)
    return ActionResult.failed("precondition", message)


def begin_review_step(
    review_layout: ReviewLayout,
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    review_id: str,
    timer: OperationTimer,
    log: LogSink,
    noun: str,
) -> ReviewStep:
    started = with_step(record, step, status="running", at=timer.started_at)
    write_review_record(review_layout, started)
    ReviewStepAttrs(review_id=review_id, step=step).apply_current()
    return ReviewStep(
        record=started,
        stop=_review_step_halt(
            review_layout=review_layout,
            record=started,
            step=step,
            review_id=review_id,
            timer=timer,
            log=log,
            noun=noun,
        ),
        settle=_review_step_settle(
            review_layout=review_layout,
            step=step,
            log=log,
            noun=noun,
        ),
    )


def _review_step_halt(
    *,
    review_layout: ReviewLayout,
    record: ReviewRecord,
    step: ReviewStepKey,
    review_id: str,
    timer: OperationTimer,
    log: LogSink,
    noun: str,
) -> ReviewHalt:
    def halt(status: ReviewStatus, message: str) -> ActionResult:
        timing = timer.finish()
        write_review_record(
            review_layout,
            with_step(record, step, status=status, at=timing.finished_at, failure=message),
        )
        ReviewStepAttrs(step=step, status=status).apply_current()
        log("system", "warn" if status == "canceled" else "error", f"{noun} {status}: {message}")
        if status == "canceled":
            return ActionResult(status="canceled", outputs={"review_id": review_id})
        return ActionResult.failed("precondition", message)

    return halt


def _review_step_settle(
    *,
    review_layout: ReviewLayout,
    step: ReviewStepKey,
    log: LogSink,
    noun: str,
) -> ReviewSettle:
    def settle(
        record: ReviewRecord,
        timing: OperationTiming,
        *,
        verdict: ReviewVerdict | None = None,
        basis: EvidenceBasis | None = None,
        experiment_environment_digest: str | None = None,
    ) -> None:
        write_review_record(
            review_layout,
            with_step(record, step, status="completed", at=timing.finished_at),
        )
        ReviewStepAttrs(
            step=step,
            status="completed",
            verdict=verdict,
            basis=basis,
            experiment_environment_digest=experiment_environment_digest,
        ).apply_current()
        log(
            "system",
            "info",
            f"{noun} completed in {format_duration_ms(timing.duration_ms)} (duration_ms={timing.duration_ms})",
        )

    return settle


def require_completed_step(
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    stop: ReviewHalt,
    message: str,
) -> ActionResult | None:
    state = step_state(record, step)
    if state is None or state.status != "completed":
        return stop("failed", message)
    return None


@dataclass(frozen=True)
class CertifiedExperimentEnvironment:
    basis: EvidenceBasis
    experiment_environment_receipt: ReviewBuildExperimentEnvironmentReceipt
    experiment_environment_path: str
    experiment_environment_digest: Digest


def require_certified_experiment_environment(
    record: ReviewRecord,
    *,
    stop: ReviewHalt,
    purpose: str,
) -> CertifiedExperimentEnvironment | ActionResult:
    basis = attempt_basis(record)
    receipt = record.receipts.build_experiment_environment
    if basis is None or receipt is None:
        return stop("failed", f"This attempt has recorded no experiment environment {purpose}")
    return CertifiedExperimentEnvironment(
        basis=basis,
        experiment_environment_receipt=receipt,
        experiment_environment_path=str(receipt.artifact_path),
        experiment_environment_digest=receipt.produced_artifact_digest,
    )


def _review_source(review: ReviewLayout, record: ReviewRecord, workspace: Path) -> None:
    receipt = record.receipts.acquire_source
    if receipt is None or receipt.observed_swhid is None:
        raise ReePreconditionError("this review has recorded no source it acquired")
    if not review.upstream.is_dir() or directory_swhid(review.upstream) != receipt.observed_swhid:
        raise ReePreconditionError("the source in this review is not the one its acquisition observed")
    shutil.copytree(review.upstream, workspace, symlinks=True, dirs_exist_ok=True)


def _review_overlay(review: ReviewLayout, record: ReviewRecord) -> None:
    build = record.receipts.build_experiment_environment
    if build is None:
        raise ReePreconditionError("this review has certified no experiment environment")
    if digest_tree(review.overlay) != build.overlay_digest:
        raise ReePreconditionError("the overlay in this review is not the one its build copied")


def _review_environment(review: ReviewLayout, record: ReviewRecord, workspace: Path) -> None:
    build = record.receipts.build_experiment_environment
    if build is None:
        raise ReePreconditionError("this review has certified no experiment environment")
    declared = str(build.artifact_path)
    kept = review.kept_environment(declared)
    if not kept.is_file():
        raise ReePreconditionError(f"the experiment environment this review certified is missing: {declared}")
    if digest_file(kept) != build.produced_artifact_digest:
        raise ReePreconditionError(f"the experiment environment at {declared} is not the one this review certified")
    target = environment_in_workspace(workspace, declared)[-1]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kept, target)


def lay_out_review(review: ReviewLayout, record: ReviewRecord, run_id: str, *, after_build: bool) -> Path:
    workspace = fresh(review, run_id)
    _review_source(review, record, workspace)
    if after_build:
        _review_overlay(review, record)
    overlay_onto(review, workspace)
    if after_build:
        _review_environment(review, record, workspace)
    return workspace


ReviewAdmission = Callable[[ReviewRecord, CertifiedExperimentEnvironment], str | None]


def review_launch(record: ReviewRecord, ree: Ree, workspace: Path) -> Launch | None:
    if record.launch.mode == "native":
        return None
    return declared_launch(ree.subject.definition.launch, workspace, record.launch.options)


def launch_digest(ree: Ree, launch: Launch | None) -> Digest | None:
    return ree.subject.definition.launch.launch_script_digest if launch is not None else None


@dataclass(frozen=True)
class ReviewRunnableStep:
    step: ReviewStepKey
    noun: str
    subject: str
    requires: ReviewStepKey
    requires_message: str
    experiment_environment_purpose: str
    admit: ReviewAdmission
    select: Callable[[ReeDefinition], tuple[RunnableSpec, str]]
    unresolvable: str
    script_noun: str


@dataclass(frozen=True)
class ReviewRun:
    ree_layout: ReeLayout
    review_layout: ReviewLayout
    workspace: Path
    step: ReviewStep
    timer: OperationTimer
    certified: CertifiedExperimentEnvironment
    runnable: RunnableSpec
    label: str
    outcome: ExperimentRunOutcome
    launch_script_digest: Digest | None


def open_review_run(
    step: ReviewRunnableStep,
    *,
    layout: ReeLayout,
    review_id: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
) -> ReviewRun | ActionResult:
    review_layout = layout.review(review_id)
    timer = OperationTimer.start()

    ree = require_ree_baseline(layout, log=log)
    if isinstance(ree, ActionResult):
        return ree

    record = require_review_record(review_layout, review_id, log)
    if isinstance(record, ActionResult):
        return record

    started = begin_review_step(
        review_layout,
        record,
        step.step,
        review_id=review_id,
        timer=timer,
        log=log,
        noun=step.noun,
    )

    if is_canceled():
        return started.stop("canceled", f"canceled before {step.subject}")

    halted = require_completed_step(started.record, step.requires, stop=started.stop, message=step.requires_message)
    if halted is not None:
        return halted

    certified = require_certified_experiment_environment(
        started.record,
        stop=started.stop,
        purpose=step.experiment_environment_purpose,
    )
    if isinstance(certified, ActionResult):
        return certified

    refusal = step.admit(started.record, certified)
    if refusal is not None:
        return started.stop("failed", refusal)

    try:
        runnable, label = step.select(ree.subject.definition)
    except ValueError as exc:
        return started.stop("failed", f"{step.unresolvable}: {exc}")

    try:
        workspace = lay_out_review(review_layout, started.record, run_id, after_build=True)
    except ReePreconditionError as exc:
        return started.stop("failed", f"cannot lay out a workspace {step.experiment_environment_purpose}: {exc}")

    script = runnable.run_script or runnable.activate_script
    if not (workspace / script).is_file():
        return started.stop(
            "failed",
            f"the author baseline declares {step.script_noun} that is not there: {script}",
        )

    try:
        launch = review_launch(started.record, ree, workspace)
    except ReePreconditionError as exc:
        return started.stop("failed", f"cannot launch the author's scripts: {exc}")
    runnable = replace(runnable, launch=launch)

    outcome = run_runnable(
        workspace=workspace.resolve(),
        runnable=runnable,
        label=label,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
    )
    if outcome.status == "canceled" or is_canceled():
        return started.stop("canceled", f"{step.subject} was canceled")

    return ReviewRun(
        ree_layout=layout,
        review_layout=review_layout,
        workspace=workspace,
        step=started,
        timer=timer,
        certified=certified,
        runnable=runnable,
        label=label,
        outcome=outcome,
        launch_script_digest=launch_digest(ree, launch),
    )
