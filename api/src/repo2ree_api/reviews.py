from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.deps import workbench_manager
from repo2ree_api.ree_commands import require_handle
from repo2ree_api.run_management import run_summary, start_single_command_run
from repo2ree_core.reviews import ReviewRecord, ReviewSet
from repo2ree_protocol.command import (
    ReviewAcquireSourceArgs,
    ReviewAcquireSourceCommand,
    ReviewActivationTestArgs,
    ReviewActivationTestCommand,
    ReviewBasis,
    ReviewBuildRuntimeArgs,
    ReviewBuildRuntimeCommand,
    ReviewRunExperimentArgs,
    ReviewRunExperimentCommand,
)

reviews_router = APIRouter(tags=["reviews"])


class CreateSourceReviewPayload(CreateRunPayload):
    """Start a fresh isolated review attempt at source acquisition.

    ``basis`` chooses what to reproduce from: the recorded origin, or the
    snapshot the REE carries. The default settles it from what the baseline
    has, preferring the origin (see :data:`ReviewBasis`).
    """

    basis: ReviewBasis = "auto"


class CreateBuildReviewPayload(CreateRunPayload):
    """Reproduce the runtime build inside an existing review attempt."""

    # The rebuilt workspace is kept, because activation and the experiments run
    # in it and the runtime exists nowhere else (see ReviewBuildRuntimeArgs).
    # A reviewer who wants only a build verdict passes true to reclaim it.
    prune_workspace: bool = False
    basis: ReviewBasis = "auto"


def _reviews(ree_id: str) -> ReviewSet:
    """Every persisted attempt for an REE, or the workbench failure to report."""
    handle = require_handle(ree_id)
    try:
        return ReviewSet.model_validate(workbench_manager.get_reviews(handle))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Workbench review query failed: {exc}") from exc


@reviews_router.get(
    "/api/v1/rees/{ree_id}/reviews",
    operation_id="listReviews",
    response_model=ReviewSet,
    responses=ERROR_RESPONSES,
)
def list_reviews(ree_id: str) -> ReviewSet:
    return _reviews(ree_id)


@reviews_router.get(
    "/api/v1/rees/{ree_id}/reviews/{review_id}",
    operation_id="getReview",
    response_model=ReviewRecord,
    responses=ERROR_RESPONSES,
)
def get_review(ree_id: str, review_id: str) -> ReviewRecord:
    for record in _reviews(ree_id).reviews:
        if record.review_id == review_id:
            return record
    raise HTTPException(status_code=404, detail="Review not found")


@reviews_router.post(
    "/api/v1/rees/{ree_id}/reviews/source:reproduce",
    operation_id="startSourceReview",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_source_review(ree_id: str, payload: CreateSourceReviewPayload) -> RunSummary:
    review_id = f"review-{uuid4().hex[:12]}"
    command = ReviewAcquireSourceCommand(args=ReviewAcquireSourceArgs(review_id=review_id, basis=payload.basis))
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="source",
                command=command,
                run_id_prefix="review-source",
                request_payload={},
                canceled_message="Source review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@reviews_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/build:reproduce",
    operation_id="startBuildReview",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_build_review(ree_id: str, review_id: str, payload: CreateBuildReviewPayload) -> RunSummary:
    """Rebuild the runtime inside an attempt whose source was already reproduced.

    Addressed by review id rather than minting a new one: the build is only
    meaningful against the source *this* attempt fetched for itself, and the
    workbench rejects the command outright when that step has not settled.
    """
    command = ReviewBuildRuntimeCommand(
        args=ReviewBuildRuntimeArgs(
            review_id=review_id,
            prune_workspace=payload.prune_workspace,
            basis=payload.basis,
        )
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="build",
                command=command,
                run_id_prefix="review-build",
                request_payload={"review_id": review_id},
                canceled_message="Build review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@reviews_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/activation:reproduce",
    operation_id="startActivationReview",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_activation_review(ree_id: str, review_id: str, payload: CreateRunPayload) -> RunSummary:
    """Probe whether the runtime this attempt certified is inhabitable.

    Takes no ``basis``, unlike the two steps before it: activation runs in the
    workspace the build left behind and inherits what that evidence is worth
    rather than choosing (see :class:`ReviewActivationTestArgs`).
    """
    command = ReviewActivationTestCommand(args=ReviewActivationTestArgs(review_id=review_id))
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="activation",
                command=command,
                run_id_prefix="review-activation",
                request_payload={"review_id": review_id},
                canceled_message="Activation review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@reviews_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/experiments/{experiment_name}:reproduce",
    operation_id="startExperimentReview",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_experiment_review(
    ree_id: str,
    review_id: str,
    experiment_name: str,
    payload: CreateRunPayload,
) -> RunSummary:
    """Reproduce one experiment's result inside an attempt whose runtime came up.

    One experiment per call, addressed by name — the same shape as the author's
    ``experiments/{name}:run``. Reproducing every experiment is the client
    issuing this in sequence rather than a batch route: each run then has its own
    log, receipt, and cancel point, and a reviewer watching a slow experiment can
    stop that one without discarding the verdicts already settled.

    Like the activation route it takes no ``basis`` (the run inherits what the
    workspace it happens in is worth), and like the author's route it does no
    host-side resolution preflight: an unknown experiment name surfaces as a
    failed run carrying the workbench's own message.
    """
    command = ReviewRunExperimentCommand(
        args=ReviewRunExperimentArgs(review_id=review_id, experiment_name=experiment_name)
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="experiment",
                command=command,
                run_id_prefix="review-experiment",
                request_payload={"review_id": review_id, "experiment_name": experiment_name},
                canceled_message="Experiment review canceled",
                fallback_outputs={"review_id": review_id, "subject_name": experiment_name},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
