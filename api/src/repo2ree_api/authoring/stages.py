"""The run-starting authoring steps, in step order.

One route per step of ``repo2ree_core.evidence.step_graph.REE_STEPS`` that advances by
*running something in the workbench*: hbom, evaluate, build, sbom, crosscheck,
activation, experiments. They are one family and differ only in the command they
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
from repo2ree_api.control.run_orchestration import run_summary, start_single_command_run
from repo2ree_api.deps import workbench_manager
from repo2ree_api.workbench.commands import require_handle
from repo2ree_core.analysis.repository.reproducibility_report import ReproducibilityReport
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_protocol import ActivationTestCommand, GenerateHbomCommand
from repo2ree_protocol.command import (
    ActivationTestArgs,
    BuildRuntimeCommand,
    CrossCheckSbomArgs,
    CrossCheckSbomCommand,
    EvaluateDependencyScoreArgs,
    EvaluateDependencyScoreCommand,
    GenerateSbomCommand,
    RunExperimentArgs,
    RunExperimentCommand,
)

stages_router = APIRouter(tags=["runs"])


# ================================================
# Hardware BOM
# ================================================


class CreateGenerateHbomRunPayload(CreateRunPayload):
    """Profile the workbench host's hardware. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/generate-hbom",
    operation_id="startHbomGeneration",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_generate_hbom_run(ree_id: str, payload: CreateGenerateHbomRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="hbom",
                command=GenerateHbomCommand(),
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
    operation_id="startEvaluate",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_evaluate_run(ree_id: str, payload: CreateEvaluateRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="evaluate",
                command=EvaluateDependencyScoreCommand(args=EvaluateDependencyScoreArgs(strict=payload.strict)),
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
    """The persisted evaluate-run report artifact."""
    # An unknown or unreachable REE is resolved first, so "no report yet" is
    # never how a caller learns their REE is gone (404) or its workbench is
    # down (503).
    handle = require_handle(ree_id)
    try:
        data = workbench_manager.read_ree_file_bytes(handle, f"artifacts/{_REPORT_FILENAME}")
        report: dict[str, Any] = json.loads(data)
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail="No reproducibility report; run evaluate first",
        ) from exc


# ================================================
# Build runtime
# ================================================


class CreateBuildRuntimeRunPayload(CreateRunPayload):
    """Run the reserved build script. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/build-runtime",
    operation_id="startBuild",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_build_runtime_run(ree_id: str, payload: CreateBuildRuntimeRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="build",
                command=BuildRuntimeCommand(),
                run_id_prefix="build",
                request_payload={"build_runtime_script_path": RESERVED_BUILD_SCRIPT},
                canceled_message="Build run canceled",
                fallback_outputs={"build_runtime_script_path": RESERVED_BUILD_SCRIPT},
                idempotency_key=payload.idempotency_key,
            )
        )
    )


# ================================================
# Software BOM
# ================================================


class CreateGenerateSbomRunPayload(CreateRunPayload):
    """Scan the declared runtime artifact. Takes no parameters of its own.

    Which artifact gets scanned is the build recipe's ``runtime_path``, which
    the author declared before the build ran and the build receipt binds. The
    handler reads it there; a client cannot name a different one.
    """


@stages_router.post(
    "/api/v1/rees/{ree_id}/generate-sbom",
    operation_id="startSbomGeneration",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_generate_sbom_run(ree_id: str, payload: CreateGenerateSbomRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="sbom",
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
    """Cross-check the recorded SBOM against the built runtime. No parameters."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/cross-check-sbom",
    operation_id="startSbomCrossCheck",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_cross_check_sbom_run(ree_id: str, payload: CreateCrossCheckSbomRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="crosscheck",
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
    """Run the reserved activation script. Takes no parameters of its own."""


@stages_router.post(
    "/api/v1/rees/{ree_id}/activation-test",
    operation_id="startActivationTest",
    response_model=RunSummary,
    responses=ERROR_RESPONSES,
)
def create_activation_test_run(ree_id: str, payload: CreateActivationTestRunPayload) -> RunSummary:
    return RunSummary.model_validate(
        run_summary(
            start_single_command_run(
                ree_id,
                operation="activation",
                command=ActivationTestCommand(args=ActivationTestArgs()),
                run_id_prefix="activation",
                request_payload={},
                canceled_message="Activation run canceled",
                fallback_outputs={"subject_name": "activation"},
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
    operation_id="startExperiment",
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
                operation="experiment",
                command=RunExperimentCommand(args=RunExperimentArgs(experiment_name=experiment_name)),
                run_id_prefix="experiment",
                request_payload={"experiment_name": experiment_name},
                canceled_message="Experiment run canceled",
                fallback_outputs={"subject_name": experiment_name},
                idempotency_key=payload.idempotency_key,
            )
        )
    )
