"""Derive evidence freshness and payload availability from one REE subject."""

from __future__ import annotations

from collections.abc import Iterable

from repo2ree_core.domain.primitives import Digest, RunId
from repo2ree_core.domain.ree.model import (
    ExperimentAssessment,
    PayloadStatus,
    Ree,
    ReeAssessment,
    ReproducibilityLevels,
    StepAssessment,
)


def _payload(digest: Digest | None, content_digests: set[Digest], *, applicable: bool = True) -> PayloadStatus:
    if not applicable:
        return "not_applicable"
    if digest is None:
        return "omitted"
    return "present" if digest in content_digests else "omitted"


def _step(
    receipt_run_id: RunId | None,
    reasons: Iterable[str] = (),
    *,
    applicable: bool = True,
    payload: PayloadStatus = "not_applicable",
) -> StepAssessment:
    reason_tuple = tuple(reasons)
    if not applicable:
        return StepAssessment(evidence="not_applicable", payload="not_applicable")
    if receipt_run_id is None:
        return StepAssessment(evidence="missing", payload=payload, reasons=reason_tuple)
    return StepAssessment(
        evidence="stale" if reason_tuple else "current",
        payload=payload,
        receipt_run_id=receipt_run_id,
        reasons=reason_tuple,
    )


def assess(ree: Ree) -> ReeAssessment:
    definition = ree.subject.definition
    receipts = ree.subject.receipts
    content_digests = {entry.digest for entry in ree.subject.contents.entries}
    bundle_settled = ree.seal is not None

    source_reasons: list[str] = []
    if definition.source is not None and receipts.source is not None:
        if receipts.source.origin_url != definition.source.origin_url:
            source_reasons.append("source origin changed")
        if receipts.source.source_type != definition.source.source_type:
            source_reasons.append("source type changed")
        if receipts.source.requested_ref != definition.source.requested_ref:
            source_reasons.append("requested source reference changed")
    source = _step(
        receipts.source.run_id if receipts.source else None,
        source_reasons or (() if receipts.source else ("source has not been acquired",)),
        applicable=definition.source is not None,
        payload=_payload(
            receipts.source.snapshot_digest if receipts.source else None,
            content_digests,
            applicable=bundle_settled,
        ),
    )

    evaluation_reasons: list[str] = []
    if (
        receipts.evaluation
        and receipts.source
        and receipts.evaluation.snapshot_digest != receipts.source.snapshot_digest
    ):
        evaluation_reasons.append("source snapshot changed")
    evaluation = _step(
        receipts.evaluation.run_id if receipts.evaluation else None,
        evaluation_reasons or (() if receipts.evaluation else ("reproducibility has not been evaluated",)),
        applicable=definition.source is not None,
        payload=_payload(
            receipts.evaluation.report_digest if receipts.evaluation else None,
            content_digests,
            applicable=bundle_settled,
        ),
    )

    hardware = _step(
        receipts.hardware_observation.run_id if receipts.hardware_observation else None,
        () if receipts.hardware_observation else ("hardware has not been observed",),
        applicable=definition.hardware is not None,
    )

    build_reasons: list[str] = []
    if receipts.build:
        if receipts.source and receipts.build.snapshot_digest != receipts.source.snapshot_digest:
            build_reasons.append("source snapshot changed")
        if definition.build_runtime is None:
            build_reasons.append("runtime build definition was removed")
        elif receipts.build.build_runtime_script_digest != definition.build_runtime.build_runtime_script_digest:
            build_reasons.append("runtime build script changed")
        if definition.runtime is None:
            build_reasons.append("runtime definition was removed")
        elif receipts.build.runtime_path != definition.runtime.runtime_path:
            build_reasons.append("runtime path changed")
        elif (
            definition.runtime.expected_runtime_digest is not None
            and receipts.build.produced_runtime_digest != definition.runtime.expected_runtime_digest
        ):
            build_reasons.append("produced runtime does not match the expected digest")
    runtime_applicable = definition.runtime is not None and definition.build_runtime is not None
    runtime = _step(
        receipts.build.run_id if receipts.build else None,
        build_reasons or (() if receipts.build else ("runtime has not been built",)),
        applicable=runtime_applicable,
        payload=_payload(
            receipts.build.produced_runtime_digest if receipts.build else None,
            content_digests,
            applicable=bundle_settled,
        ),
    )

    sbom_reasons: list[str] = []
    if receipts.sbom and receipts.build and receipts.sbom.runtime_digest != receipts.build.produced_runtime_digest:
        sbom_reasons.append("runtime changed")
    sbom = _step(
        receipts.sbom.run_id if receipts.sbom else None,
        sbom_reasons or (() if receipts.sbom else ("SBOM has not been generated",)),
        applicable=definition.runtime is not None,
        payload=_payload(
            receipts.sbom.sbom_digest if receipts.sbom else None,
            content_digests,
            applicable=bundle_settled,
        ),
    )

    activation_reasons: list[str] = []
    if receipts.test_activation:
        if receipts.source and receipts.test_activation.snapshot_digest != receipts.source.snapshot_digest:
            activation_reasons.append("source snapshot changed")
        if definition.test_activation is None:
            activation_reasons.append("activation definition was removed")
        else:
            if receipts.test_activation.run_script_digest != definition.test_activation.run_script_digest:
                activation_reasons.append("activation script changed")
            if receipts.test_activation.verify_script_digest != definition.test_activation.verify_script_digest:
                activation_reasons.append("activation verification script changed")
        if receipts.build and receipts.test_activation.runtime_digest != receipts.build.produced_runtime_digest:
            activation_reasons.append("runtime changed")
    test_activation = _step(
        receipts.test_activation.run_id if receipts.test_activation else None,
        activation_reasons or (() if receipts.test_activation else ("activation has not been tested",)),
        applicable=definition.test_activation is not None,
    )

    experiment_assessments: list[ExperimentAssessment] = []
    for experiment in definition.experiments:
        receipt = receipts.experiments.get(experiment.name)
        reasons: list[str] = []
        if receipt:
            if receipts.source and receipt.snapshot_digest != receipts.source.snapshot_digest:
                reasons.append("source snapshot changed")
            if receipt.run_script_digest != experiment.run_script_digest:
                reasons.append("experiment run script changed")
            if receipt.verify_script_digest != experiment.verify_script_digest:
                reasons.append("experiment verification script changed")
            if receipts.build and receipt.runtime_digest != receipts.build.produced_runtime_digest:
                reasons.append("runtime changed")
        experiment_assessments.append(
            ExperimentAssessment(
                name=experiment.name,
                run=_step(
                    receipt.run_id if receipt else None,
                    reasons or (() if receipt else ("experiment has not been run",)),
                    payload=_payload(
                        receipt.produced_output_digest if receipt else None,
                        content_digests,
                        applicable=bundle_settled and bool(experiment.output_paths),
                    ),
                ),
            )
        )

    levels = ReproducibilityLevels()
    if receipts.evaluation:
        levels = ReproducibilityLevels(
            dependency=receipts.evaluation.dependency_level,
            environment=receipts.evaluation.environment_level,
            machine=receipts.evaluation.machine_level,
        )
    return ReeAssessment(
        source=source,
        evaluation=evaluation,
        hardware=hardware,
        runtime=runtime,
        sbom=sbom,
        test_activation=test_activation,
        experiments=tuple(experiment_assessments),
        reproducibility=levels,
    )
