from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from repo2ree_protocol.audit import EvidenceStatus, ExperimentAudit, PayloadStatus, ReeAudit, StepAudit
from repo2ree_ree.model import Ree, ReeDefinition, ReeReceipts
from repo2ree_ree.primitives import Digest, RunId


@dataclass(frozen=True)
class _Subject:
    definition: ReeDefinition
    receipts: ReeReceipts
    content_digests: frozenset[Digest]
    content_paths: frozenset[str]
    bundle_settled: bool

    @classmethod
    def of(cls, ree: Ree) -> _Subject:
        return cls(
            definition=ree.subject.definition,
            receipts=ree.subject.receipts,
            content_digests=frozenset(entry.digest for entry in ree.subject.contents.entries),
            content_paths=frozenset(str(entry.path) for entry in ree.subject.contents.entries),
            bundle_settled=ree.seal is not None,
        )

    def payload(self, digest: Digest | None, *, applicable: bool = True) -> PayloadStatus:
        if not (applicable and self.bundle_settled):
            return "not_applicable"
        return "present" if digest is not None and digest in self.content_digests else "omitted"

    def experiment_payload(self, name: str, *, applicable: bool) -> PayloadStatus:
        if not (applicable and self.bundle_settled):
            return "not_applicable"
        return "present" if any(path.startswith(f"results/{name}/") for path in self.content_paths) else "omitted"


_ORPHANED_RECEIPT_REASON = "the REE no longer declares what this evidence is about"


def _evidence_standing(*, applicable: bool, has_receipt: bool, complaints: bool) -> EvidenceStatus:
    if not has_receipt:
        return "missing" if applicable else "not_applicable"
    return "stale" if complaints or not applicable else "current"


def _step(
    receipt_run_id: RunId | None,
    reasons: Iterable[str] = (),
    *,
    applicable: bool = True,
    payload: PayloadStatus = "not_applicable",
) -> StepAudit:
    if not applicable and receipt_run_id is None:
        return StepAudit(evidence="not_applicable", payload="not_applicable")
    complaints = tuple(reasons) or (() if applicable else (_ORPHANED_RECEIPT_REASON,))
    return StepAudit(
        evidence=_evidence_standing(
            applicable=applicable,
            has_receipt=receipt_run_id is not None,
            complaints=bool(complaints),
        ),
        payload=payload,
        receipt_run_id=receipt_run_id,
        reasons=complaints,
    )


def _audit_acquire_source(subject: _Subject) -> StepAudit:
    declared, receipt = subject.definition.source, subject.receipts.acquire_source
    reasons: list[str] = []
    if declared is not None and receipt is not None:
        if receipt.origin_url != declared.origin_url:
            reasons.append("source origin changed")
        if receipt.source_type != declared.source_type:
            reasons.append("source type changed")
        if receipt.requested_ref != declared.requested_ref:
            reasons.append("requested source reference changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("source has not been acquired",)),
        applicable=declared is not None,
        payload=subject.payload(receipt.snapshot_digest if receipt else None),
    )


def _audit_evaluate_reproducibility(subject: _Subject) -> StepAudit:
    receipt, source = subject.receipts.evaluate_reproducibility, subject.receipts.acquire_source
    reasons: list[str] = []
    if receipt and source and receipt.snapshot_digest != source.snapshot_digest:
        reasons.append("source snapshot changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("reproducibility has not been evaluated",)),
        applicable=subject.definition.source is not None,
        payload=subject.payload(receipt.report_digest if receipt else None),
    )


def _audit_observe_hardware(subject: _Subject) -> StepAudit:
    receipt = subject.receipts.observe_hardware
    hbom = subject.definition.hbom
    declared = hbom is not None and _declares_something(hbom.model_dump(mode="json"))
    return _step(
        receipt.run_id if receipt else None,
        () if receipt else ("hardware has not been observed",),
        applicable=declared or receipt is not None,
    )


def _declares_something(value: object) -> bool:
    if isinstance(value, dict):
        return any(_declares_something(inner) for inner in value.values())
    return value not in (None, "", [])


def _audit_check_working_environment(subject: _Subject) -> StepAudit:
    declared, receipt = subject.definition.check_working_environment, subject.receipts.check_working_environment
    reasons: list[str] = []
    if receipt:
        if receipt.check_working_environment_script_digest != declared.check_working_environment_script_digest:
            reasons.append("check script changed")
        if _launch_changed(subject, receipt.launch_script_digest):
            reasons.append("launch script changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("the working environment has not been checked",)),
        applicable=True,
    )


def _audit_build_experiment_environment(subject: _Subject) -> StepAudit:
    build, receipt = subject.definition.experiment_environment, subject.receipts.build_experiment_environment
    reasons: list[str] = []
    if receipt:
        if (
            subject.receipts.acquire_source
            and receipt.snapshot_digest != subject.receipts.acquire_source.snapshot_digest
        ):
            reasons.append("source snapshot changed")
        if receipt.build_experiment_environment_script_digest != build.build_experiment_environment_script_digest:
            reasons.append("build experiment environment script changed")
        if receipt.artifact_path != build.artifact_path:
            reasons.append("experiment environment artifact path changed")
        if _launch_changed(subject, receipt.launch_script_digest):
            reasons.append("launch script changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("experiment environment has not been built",)),
        applicable=_experiment_environment_is_declared(subject),
        payload=subject.payload(receipt.produced_artifact_digest if receipt else None),
    )


def _launch_changed(subject: _Subject, ran_under: Digest | None) -> bool:
    return ran_under != subject.definition.launch.launch_script_digest


def _experiment_environment_is_declared(subject: _Subject) -> bool:
    return subject.definition.experiment_environment.artifact_path is not None


def _audit_generate_sbom(subject: _Subject) -> StepAudit:
    receipt, build = subject.receipts.generate_sbom, subject.receipts.build_experiment_environment
    reasons: list[str] = []
    if receipt and build and receipt.experiment_environment_digest != build.produced_artifact_digest:
        reasons.append("experiment environment changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("SBOM has not been generated",)),
        applicable=_experiment_environment_is_declared(subject),
        payload=subject.payload(receipt.sbom_digest if receipt else None),
    )


def _audit_cross_check_sbom(subject: _Subject) -> StepAudit:
    receipt = subject.receipts.cross_check_sbom
    sbom, evaluation = subject.receipts.generate_sbom, subject.receipts.evaluate_reproducibility
    reasons: list[str] = []
    if receipt:
        if sbom and receipt.sbom_digest != sbom.sbom_digest:
            reasons.append("SBOM changed")
        if evaluation and receipt.report_digest != evaluation.report_digest:
            reasons.append("reproducibility report changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("SBOM has not been cross-checked",)),
        applicable=subject.definition.source is not None and _experiment_environment_is_declared(subject),
    )


def _audit_activate_experiment_environment(subject: _Subject) -> StepAudit:
    receipt = subject.receipts.activate_experiment_environment
    reasons: list[str] = []
    if receipt:
        if (
            subject.receipts.acquire_source
            and receipt.snapshot_digest != subject.receipts.acquire_source.snapshot_digest
        ):
            reasons.append("source snapshot changed")
        reasons.extend(_activation_reasons(subject, receipt.activate_experiment_environment_script_digest))
        if _launch_changed(subject, receipt.launch_script_digest):
            reasons.append("launch script changed")
        if (
            subject.receipts.build_experiment_environment
            and receipt.experiment_environment_digest
            != subject.receipts.build_experiment_environment.produced_artifact_digest
        ):
            reasons.append("experiment environment changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("the activation has not been tested",)),
        applicable=True,
    )


def _activation_reasons(subject: _Subject, ran_with: Digest) -> tuple[str, ...]:
    declared = subject.definition.activate_experiment_environment
    if ran_with != declared.activate_experiment_environment_script_digest:
        return ("activate experiment environment script changed",)
    return ()


def _audit_experiments(subject: _Subject) -> tuple[ExperimentAudit, ...]:
    audits: list[ExperimentAudit] = []
    for experiment in subject.definition.experiments:
        receipt = subject.receipts.experiments.get(experiment.name)
        reasons: list[str] = []
        if receipt:
            if (
                subject.receipts.acquire_source
                and receipt.snapshot_digest != subject.receipts.acquire_source.snapshot_digest
            ):
                reasons.append("source snapshot changed")
            if receipt.run_script_digest != experiment.run_script_digest:
                reasons.append("experiment run script changed")
            if receipt.verify_script_digest != experiment.verify_script_digest:
                reasons.append("experiment verification script changed")
            reasons.extend(_activation_reasons(subject, receipt.activate_experiment_environment_script_digest))
            if _launch_changed(subject, receipt.launch_script_digest):
                reasons.append("launch script changed")
            if (
                subject.receipts.build_experiment_environment
                and receipt.experiment_environment_digest
                != subject.receipts.build_experiment_environment.produced_artifact_digest
            ):
                reasons.append("experiment environment changed")
            if (activation := subject.receipts.activate_experiment_environment) and (
                receipt.activate_experiment_environment_script_digest
                != activation.activate_experiment_environment_script_digest
                or receipt.experiment_environment_digest != activation.experiment_environment_digest
            ):
                reasons.append("activation changed")
        audits.append(
            ExperimentAudit(
                name=experiment.name,
                run=_step(
                    receipt.run_id if receipt else None,
                    reasons or (() if receipt else ("experiment has not been run",)),
                    payload=subject.experiment_payload(experiment.name, applicable=bool(experiment.output_paths)),
                ),
            )
        )
    return tuple(audits)


def audit(ree: Ree) -> ReeAudit:
    subject = _Subject.of(ree)

    acquire_source_audit = _audit_acquire_source(subject)
    evaluate_reproducibility_audit = _audit_evaluate_reproducibility(subject)
    observe_hardware_audit = _audit_observe_hardware(subject)
    check_working_environment_audit = _audit_check_working_environment(subject)
    build_experiment_environment_audit = _audit_build_experiment_environment(subject)
    generate_sbom_audit = _audit_generate_sbom(subject)
    cross_check_sbom_audit = _audit_cross_check_sbom(subject)
    activate_experiment_environment_audit = _audit_activate_experiment_environment(subject)
    experiments_audit = _audit_experiments(subject)

    return ReeAudit(
        acquire_source=acquire_source_audit,
        evaluate_reproducibility=evaluate_reproducibility_audit,
        observe_hardware=observe_hardware_audit,
        check_working_environment=check_working_environment_audit,
        build_experiment_environment=build_experiment_environment_audit,
        generate_sbom=generate_sbom_audit,
        cross_check_sbom=cross_check_sbom_audit,
        activate_experiment_environment=activate_experiment_environment_audit,
        experiments=experiments_audit,
    )
