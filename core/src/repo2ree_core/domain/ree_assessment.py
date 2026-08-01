"""Pure assessment of current authored inputs against immutable receipts."""

from __future__ import annotations

from repo2ree_core.domain.receipt import (
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    RunExperimentReceipt,
    RunReceipt,
    SnapshotUpstreamReceipt,
    experiment_step_key,
)
from repo2ree_core.domain.ree import (
    ExperimentCapability,
    Ree,
    ReeAssessment,
    ReeCapability,
)
from repo2ree_core.domain.ree_structure import experiments_of, runtime_of, scripts_of, selected_receipt


def _missing_or_stale(receipt: RunReceipt | None, reasons: list[str]) -> ReeCapability:
    if receipt is None:
        return ReeCapability(status="missing", reasons=tuple(reasons))
    return ReeCapability(status="stale" if reasons else "ready", receipt_run_id=receipt.run_id, reasons=tuple(reasons))


def assess(ree: Ree) -> ReeAssessment:
    """Derive current capabilities by matching selected receipts to the head."""

    authored = ree.authored
    evidence = ree.evidence
    session = evidence.session_projection
    snapshot = selected_receipt(evidence, "snapshot_upstream")
    snapshot_receipt = snapshot if isinstance(snapshot, SnapshotUpstreamReceipt) else None
    current_snapshot_digest = session.source_snapshot_digest
    if current_snapshot_digest is None and snapshot_receipt is not None:
        current_snapshot_digest = snapshot_receipt.snapshot_digest

    source_reasons: list[str] = []
    if not (session.source_available or current_snapshot_digest):
        source_reasons.append("source has not been acquired")
    source = ReeCapability(status="ready" if not source_reasons else "missing", reasons=tuple(source_reasons))

    build = selected_receipt(evidence, "build_runtime")
    build_receipt = build if isinstance(build, BuildRuntimeReceipt) else None
    build_reasons: list[str] = []
    build_script = scripts_of(authored).build_runtime
    if build_receipt is not None:
        if build_receipt.snapshot_digest != current_snapshot_digest:
            build_reasons.append("source snapshot changed")
        current_build_digest = build_script.digest if build_script else None
        if build_receipt.build_script_digest != current_build_digest:
            build_reasons.append("runtime build script changed")
    runtime_definition = runtime_of(authored)
    if runtime_definition.artifact_path:
        runtime = _missing_or_stale(
            build_receipt,
            build_reasons or ([] if build_receipt else ["runtime has not been built"]),
        )
    else:
        runtime = ReeCapability(status="not_applicable")

    activation_receipt = selected_receipt(evidence, "activation_test")
    activation_run = activation_receipt if isinstance(activation_receipt, ActivationTestReceipt) else None
    activation_reasons: list[str] = []
    activation = runtime_definition.activation
    if activation_run is not None:
        if activation_run.snapshot_digest != current_snapshot_digest:
            activation_reasons.append("source snapshot changed")
        run_script = next((file for file in authored.files if file.path == activation.run_script), None)
        verify_script = next((file for file in authored.files if file.path == activation.verify_script), None)
        if activation_run.run_script_digest != (run_script.digest if run_script else None):
            activation_reasons.append("activation script changed")
        if activation_run.verify_script_digest != (verify_script.digest if verify_script else None):
            activation_reasons.append("activation verification script changed")
        produced_runtime = build_receipt.produced_runtime_digest if build_receipt else None
        if (
            activation_run.declared_runtime_digest
            and produced_runtime
            and activation_run.declared_runtime_digest != produced_runtime
        ):
            activation_reasons.append("runtime changed")
    if runtime_definition.artifact_path:
        activation_capability = _missing_or_stale(
            activation_run,
            activation_reasons or ([] if activation_run else ["activation has not been tested"]),
        )
    else:
        activation_capability = ReeCapability(status="not_applicable")

    experiment_capabilities: list[ExperimentCapability] = []
    for experiment in experiments_of(authored):
        receipt = selected_receipt(evidence, experiment_step_key(experiment.name))
        run = receipt if isinstance(receipt, RunExperimentReceipt) else None
        reasons: list[str] = []
        if run is not None:
            if run.snapshot_digest != current_snapshot_digest:
                reasons.append("source snapshot changed")
            run_script = next((file for file in authored.files if file.path == experiment.run_script), None)
            verify_script = next((file for file in authored.files if file.path == experiment.verify_script), None)
            if run.run_script_digest != (run_script.digest if run_script else None):
                reasons.append("experiment run script changed")
            if run.verify_script_digest != (verify_script.digest if verify_script else None):
                reasons.append("experiment verification script changed")
            produced_runtime = build_receipt.produced_runtime_digest if build_receipt else None
            if run.declared_runtime_digest and produced_runtime and run.declared_runtime_digest != produced_runtime:
                reasons.append("runtime changed")
        capability = _missing_or_stale(run, reasons or ([] if run else ["experiment has not been run"]))
        experiment_capabilities.append(ExperimentCapability(experiment_name=experiment.name, capability=capability))

    return ReeAssessment(
        source=source,
        runtime=runtime,
        activation=activation_capability,
        experiments=tuple(experiment_capabilities),
    )
