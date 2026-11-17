"""The reviewer's reproduction steps, in step order.

The mirror of :mod:`repo2ree_api.authoring.stages`: the same four stages an
author ran — source, build, activation, experiments — re-run inside an isolated
attempt. Each is a background run like its author-side twin, so a reviewer
watching a slow step can cancel that one without discarding verdicts already
settled.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import Field

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.contracts.runs import runs
from repo2ree_api.control.run_orchestration import run_summary, start_single_command_run
from repo2ree_protocol.command import (
    ReviewAcquireSourceArgs,
    ReviewAcquireSourceCommand,
    ReviewActivateExperimentEnvironmentArgs,
    ReviewActivateExperimentEnvironmentCommand,
    ReviewBasis,
    ReviewBuildExperimentEnvironmentArgs,
    ReviewBuildExperimentEnvironmentCommand,
    ReviewRunExperimentArgs,
    ReviewRunExperimentCommand,
)
from repo2ree_ree.review import ReviewLaunch

review_stages_router = APIRouter(tags=["reviews"])


class CreateSourceReviewPayload(CreateRunPayload):
    """Start a fresh isolated review attempt at source acquisition.

    ``basis`` chooses what to reproduce from: the recorded origin, or the
    snapshot the REE carries. The default settles it from what the baseline
    has, preferring the origin (see :data:`ReviewBasis`).
    """

    basis: ReviewBasis = "auto"
    # How the attempt launches the author's scripts: the author's launch, with options of the reviewer's own added,
    # or directly. Kept for every step of the attempt.
    launch: ReviewLaunch = Field(default_factory=ReviewLaunch)


class CreateBuildExperimentEnvironmentReviewPayload(CreateRunPayload):
    """Reproduce the experiment environment build inside an existing review attempt."""

    # The rebuilt workspace is kept, because activation and the experiments run
    # in it and the experiment environment exists nowhere else (see ReviewBuildExperimentEnvironmentArgs).
    # A reviewer who wants only a build verdict passes true to reclaim it.
    prune_workspace: bool = False
    basis: ReviewBasis = "auto"


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/source:reproduce",
    operation_id="reviewAcquireSource",
    openapi_extra=runs("review_acquire_source"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_source_review(ree_id: str, payload: CreateSourceReviewPayload) -> RunSummary:
    review_id = f"review-{uuid4().hex[:12]}"
    command = ReviewAcquireSourceCommand(
        args=ReviewAcquireSourceArgs(review_id=review_id, basis=payload.basis, launch=payload.launch)
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action=None,
                command=command,
                run_id_prefix="review-source",
                request_payload={},
                canceled_message="Source review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/build-experiment-environment:reproduce",
    operation_id="reviewBuildExperimentEnvironment",
    openapi_extra=runs("review_build_experiment_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_build_review(
    ree_id: str, review_id: str, payload: CreateBuildExperimentEnvironmentReviewPayload
) -> RunSummary:
    """Rebuild the experiment environment inside an attempt whose source was already reproduced.

    Addressed by review id rather than minting a new one: the build is only
    meaningful against the source *this* attempt fetched for itself, and the
    workbench rejects the command outright when that step has not settled.
    """
    command = ReviewBuildExperimentEnvironmentCommand(
        args=ReviewBuildExperimentEnvironmentArgs(
            review_id=review_id,
            prune_workspace=payload.prune_workspace,
            basis=payload.basis,
        )
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action=None,
                command=command,
                run_id_prefix="review-build",
                request_payload={"review_id": review_id},
                canceled_message="Build review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/activation:reproduce",
    operation_id="reviewActivateExperimentEnvironment",
    openapi_extra=runs("review_activate_experiment_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_activation_review(ree_id: str, review_id: str, payload: CreateRunPayload) -> RunSummary:
    """Run the author's activation alone in the experiment environment this attempt certified.

    Takes no ``basis``, unlike the two steps before it: activation runs in the
    workspace the build left behind and inherits what that evidence is worth
    rather than choosing (see :class:`ReviewActivateExperimentEnvironmentArgs`).
    """
    command = ReviewActivateExperimentEnvironmentCommand(
        args=ReviewActivateExperimentEnvironmentArgs(review_id=review_id)
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action=None,
                command=command,
                run_id_prefix="review-activation",
                request_payload={"review_id": review_id},
                canceled_message="Activation review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/experiments/{experiment_name}:reproduce",
    operation_id="reviewRunExperiment",
    openapi_extra=runs("review_run_experiment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def start_experiment_review(
    ree_id: str,
    review_id: str,
    experiment_name: str,
    payload: CreateRunPayload,
) -> RunSummary:
    """Reproduce one experiment's result inside an attempt whose experiment environment came up.

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
                action=None,
                command=command,
                run_id_prefix="review-experiment",
                request_payload={"review_id": review_id, "experiment_name": experiment_name},
                canceled_message="Experiment review canceled",
                fallback_outputs={"review_id": review_id, "subject_name": experiment_name},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
