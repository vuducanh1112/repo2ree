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


class ReviewAcquireSourcePayload(CreateRunPayload):
    basis: ReviewBasis = "auto"
    launch: ReviewLaunch = Field(default_factory=ReviewLaunch)


class ReviewBuildExperimentEnvironmentPayload(CreateRunPayload):
    basis: ReviewBasis = "auto"


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/acquire-source",
    operation_id="reviewAcquireSource",
    openapi_extra=runs("review_acquire_source"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def review_acquire_source_route(ree_id: str, payload: ReviewAcquireSourcePayload) -> RunSummary:
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
                request_payload={},
                canceled_message="Source review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/build-experiment-environment",
    operation_id="reviewBuildExperimentEnvironment",
    openapi_extra=runs("review_build_experiment_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def review_build_experiment_environment_route(
    ree_id: str, review_id: str, payload: ReviewBuildExperimentEnvironmentPayload
) -> RunSummary:
    command = ReviewBuildExperimentEnvironmentCommand(
        args=ReviewBuildExperimentEnvironmentArgs(
            review_id=review_id,
            basis=payload.basis,
        )
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action=None,
                command=command,
                request_payload={"review_id": review_id},
                canceled_message="Build review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/activate-experiment-environment",
    operation_id="reviewActivateExperimentEnvironment",
    openapi_extra=runs("review_activate_experiment_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def review_activate_experiment_environment_route(ree_id: str, review_id: str, payload: CreateRunPayload) -> RunSummary:
    command = ReviewActivateExperimentEnvironmentCommand(
        args=ReviewActivateExperimentEnvironmentArgs(review_id=review_id)
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action=None,
                command=command,
                request_payload={"review_id": review_id},
                canceled_message="Activation review canceled",
                fallback_outputs={"review_id": review_id},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


@review_stages_router.post(
    "/api/v1/rees/{ree_id}/reviews/{review_id}/run-experiment/{experiment_name}",
    operation_id="reviewRunExperiment",
    openapi_extra=runs("review_run_experiment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def review_run_experiment_route(
    ree_id: str,
    review_id: str,
    experiment_name: str,
    payload: CreateRunPayload,
) -> RunSummary:
    command = ReviewRunExperimentCommand(
        args=ReviewRunExperimentArgs(review_id=review_id, experiment_name=experiment_name)
    )
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action=None,
                command=command,
                request_payload={"review_id": review_id, "experiment_name": experiment_name},
                canceled_message="Experiment review canceled",
                fallback_outputs={"review_id": review_id, "subject_name": experiment_name},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
