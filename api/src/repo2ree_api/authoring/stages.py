"""The run-starting authoring steps, in step order.

One route per step ``ree steps`` lists that advances by
*running something in the workbench*: hbom, the working environment check, evaluate, build, sbom,
crosscheck, activation, experiments. They are one family and differ only in the command they
dispatch and the words their run logs carry, so they live together — the shape
they share is visible here, and the reviewer's mirror of these same steps sits
in :mod:`repo2ree_api.review.stages`.

Each keeps its own payload model even where it has no fields: the class name and
docstring are the schema name and description in the published contract, so a
shared model would flatten seven distinct operations into one anonymous body.

Steps that advance by *declaring* rather than running (source, metadata, seal)
are in the sibling modules named for them.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from repo2ree_api.contracts import ERROR_RESPONSES, CreateRunPayload, RunSummary
from repo2ree_api.contracts.runs import runs
from repo2ree_api.control.run_orchestration import run_summary, start_single_command_run
from repo2ree_api.deps import command_dispatcher
from repo2ree_api.storage.author_actions import author_api_action
from repo2ree_api.workbench.commands import require_handle
from repo2ree_protocol.command import (
    ActivateExperimentEnvironmentArgs,
    ActivateExperimentEnvironmentCommand,
    BuildExperimentEnvironmentCommand,
    CheckWorkingEnvironmentCommand,
    CrossCheckSbomArgs,
    CrossCheckSbomCommand,
    EvaluateReproducibilityArgs,
    EvaluateReproducibilityCommand,
    GenerateSbomCommand,
    ObserveHardwareCommand,
    RunExperimentArgs,
    RunExperimentCommand,
)
from repo2ree_ree.reproducibility import ReproducibilityReport
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT

stages_router = APIRouter(tags=["runs"])


# ================================================
# Hardware BOM
# ================================================


class CreateGenerateHbomRunPayload(CreateRunPayload):
    """Profile the workbench host's hardware. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/generate-hbom",
    operation_id="observeHardware",
    openapi_extra=runs("observe_hardware"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_generate_hbom_run(ree_id: str, payload: CreateGenerateHbomRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="observe_hardware",
                command=ObserveHardwareCommand(),
                run_id_prefix="hbom",
                request_payload={},
                canceled_message="HBOM run canceled",
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# Reproducibility readiness
# ================================================


class CreateEvaluateRunPayload(CreateRunPayload):
    strict: bool = False


@stages_router.post(
    "/api/v1/rees/{ree_id}/evaluate",
    operation_id="evaluateReproducibility",
    openapi_extra=runs("evaluate_reproducibility"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_evaluate_run(ree_id: str, payload: CreateEvaluateRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="evaluate_reproducibility",
                command=EvaluateReproducibilityCommand(args=EvaluateReproducibilityArgs(strict=payload.strict)),
                run_id_prefix="evaluate",
                request_payload={"strict": bool(payload.strict)},
                canceled_message="Evaluate run canceled",
                idempotency_key=payload.idempotency_key,
            )
        )
    )


_REPORT_FILENAME = "reproducibility-report.json"


@stages_router.get(
    "/api/v1/rees/{ree_id}/evaluate/report",
    operation_id="getEvaluateReport",
    response_model=ReproducibilityReport,
    responses=ERROR_RESPONSES,
)
def get_ree_evaluate_report(ree_id: str) -> dict[str, Any]:
    """The persisted evaluate-run report artifact.

    A threat's ``blocking`` means it holds its axis at its current level. Nothing
    refuses to run or seal because of one.
    """
    with author_api_action("view_evaluation_report", ree_id):
        return _evaluation_report(ree_id)


def _evaluation_report(ree_id: str) -> dict[str, Any]:
    # An unknown or unreachable REE is resolved first, so "no report yet" is
    # never how a caller learns their REE is gone (404) or its workbench is
    # down (503).
    handle = require_handle(ree_id)
    try:
        data = command_dispatcher.read_ree_file_bytes(handle, f"artifacts/{_REPORT_FILENAME}")
        report: dict[str, Any] = json.loads(data)
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail="No reproducibility report; run evaluate first",
        ) from exc


# ================================================
# Build experiment environment
# ================================================


class CreateBuildExperimentEnvironmentRunPayload(CreateRunPayload):
    """Run the reserved build script. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/build-experiment-environment",
    operation_id="buildExperimentEnvironment",
    openapi_extra=runs("build_experiment_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_build_experiment_environment_run(
    ree_id: str, payload: CreateBuildExperimentEnvironmentRunPayload
) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="build_experiment_environment",
                command=BuildExperimentEnvironmentCommand(),
                run_id_prefix="build_experiment_environment",
                request_payload={
                    "build_experiment_environment_script_path": RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
                },
                canceled_message="Build run canceled",
                fallback_outputs={
                    "build_experiment_environment_script_path": RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT
                },
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# Software BOM
# ================================================


class CreateGenerateSbomRunPayload(CreateRunPayload):
    """Scan the declared experiment environment artifact. Takes no parameters of its own.

    Which artifact gets scanned is the build recipe's ``experiment_environment_path``, which
    the author declared before the build ran and the build receipt binds. The
    handler reads it there; a client cannot name a different one.
    """


@stages_router.post(
    "/api/v1/rees/{ree_id}/generate-sbom",
    operation_id="generateSbom",
    openapi_extra=runs("generate_sbom"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_generate_sbom_run(ree_id: str, payload: CreateGenerateSbomRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="generate_sbom",
                command=GenerateSbomCommand(),
                run_id_prefix="sbom",
                request_payload={},
                canceled_message="SBOM run canceled",
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# SBOM cross-check
# ================================================


class CreateCrossCheckSbomRunPayload(CreateRunPayload):
    """Cross-check the recorded SBOM against the built experiment environment. No parameters."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/cross-check-sbom",
    operation_id="crossCheckSbom",
    openapi_extra=runs("cross_check_sbom"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_cross_check_sbom_run(ree_id: str, payload: CreateCrossCheckSbomRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="cross_check_sbom",
                command=CrossCheckSbomCommand(args=CrossCheckSbomArgs()),
                run_id_prefix="crosscheck",
                request_payload={},
                canceled_message="SBOM cross-check run canceled",
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# Activation test
# ================================================


class CreateActivationTestRunPayload(CreateRunPayload):
    """Run the activate experiment environment script alone. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/activation-test",
    operation_id="activateExperimentEnvironment",
    openapi_extra=runs("activate_experiment_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_activation_test_run(ree_id: str, payload: CreateActivationTestRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="activate_experiment_environment",
                command=ActivateExperimentEnvironmentCommand(args=ActivateExperimentEnvironmentArgs()),
                run_id_prefix="activation",
                request_payload={},
                canceled_message="Activation run canceled",
                fallback_outputs={"subject_name": "activation"},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# Check working environment
# ================================================


class CreateCheckWorkingEnvironmentRunPayload(CreateRunPayload):
    """Run the REE's check script in its working environment. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/check-working-environment",
    operation_id="checkWorkingEnvironment",
    openapi_extra=runs("check_working_environment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_check_working_environment_run(ree_id: str, payload: CreateCheckWorkingEnvironmentRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="check_working_environment",
                command=CheckWorkingEnvironmentCommand(),
                run_id_prefix="check",
                request_payload={},
                canceled_message="Working environment check canceled",
                fallback_outputs={"subject_name": "working environment"},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# Experiments
# ================================================


class CreateExperimentRunPayload(CreateRunPayload):
    """No fields of its own yet — the extension point for future run options."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/experiments/{experiment_name}:run",
    operation_id="runExperiment",
    openapi_extra=runs("run_experiment"),
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_experiment_run(
    ree_id: str,
    experiment_name: str,
    payload: CreateExperimentRunPayload,
) -> RunSummary:
    # No host-side resolution preflight: reading the intent costs a synchronous
    # round-trip into the workbench (~600ms on the click path) to re-check rules
    # the in-workbench handler applies authoritatively anyway — the intent can
    # change between the two, so only the workbench's verdict ever counted. An
    # unresolvable experiment surfaces as a failed run carrying the same
    # message, exactly as the activation route already behaved.
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                action="run_experiment",
                command=RunExperimentCommand(args=RunExperimentArgs(experiment_name=experiment_name)),
                run_id_prefix="experiment",
                request_payload={"experiment_name": experiment_name},
                canceled_message="Experiment run canceled",
                fallback_outputs={"subject_name": experiment_name},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
