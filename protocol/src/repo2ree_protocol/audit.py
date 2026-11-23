from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_ree.primitives import RunId

EvidenceStatus = Literal["missing", "current", "stale", "not_applicable"]
PayloadStatus = Literal["present", "omitted", "not_applicable"]


class _AuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StepAudit(_AuditModel):
    evidence: EvidenceStatus
    payload: PayloadStatus
    receipt_run_id: RunId | None = None
    reasons: tuple[str, ...] = ()


class ExperimentAudit(_AuditModel):
    name: str
    run: StepAudit


class ReeAudit(_AuditModel):
    acquire_source: StepAudit
    evaluate_reproducibility: StepAudit
    observe_hardware: StepAudit
    check_working_environment: StepAudit
    build_experiment_environment: StepAudit
    generate_sbom: StepAudit
    cross_check_sbom: StepAudit
    activate_experiment_environment: StepAudit
    experiments: tuple[ExperimentAudit, ...] = ()

    def stale_steps(self) -> tuple[tuple[str, StepAudit], ...]:
        named = [
            (name, step)
            for name, step in ((field, getattr(self, field)) for field in _STEP_FIELDS)
            if step.evidence == "stale"
        ]
        named.extend(
            (f"experiment '{experiment.name}'", experiment.run)
            for experiment in self.experiments
            if experiment.run.evidence == "stale"
        )
        return tuple(named)


_STEP_FIELDS: tuple[str, ...] = tuple(
    name for name, field in ReeAudit.model_fields.items() if field.annotation is StepAudit
)
