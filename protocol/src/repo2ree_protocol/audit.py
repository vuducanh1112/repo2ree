from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_ree.primitives import RunId

# ================================================
# Vocabulary
# ================================================

# Whether a step's receipt still speaks for the REE as it now stands. The
# words are not temporal: a receipt recorded a year ago is ``current`` while
# nothing it rests on has moved, and one recorded a minute ago is ``stale`` the
# moment an author edits the script it ran. :func:`_evidence_standing` is the
# single definition; see its table before adding a caller.
EvidenceStatus = Literal["missing", "current", "stale", "not_applicable"]
# Whether the bytes a receipt attests to travel inside the sealed bundle.
# Only meaningful once sealed: a draft's inventory is empty by construction, so
# every payload reads ``not_applicable`` until the bundle settles.
PayloadStatus = Literal["present", "omitted", "not_applicable"]


# ================================================
# Data Models
# ================================================


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
    source: StepAudit
    evaluation: StepAudit
    hardware: StepAudit
    runtime: StepAudit
    sbom: StepAudit
    sbom_cross_check: StepAudit
    test_activation: StepAudit
    experiments: tuple[ExperimentAudit, ...] = ()

    def stale_steps(self) -> tuple[tuple[str, StepAudit], ...]:
        """Every step whose receipt no longer speaks for this REE, named.

        The one query with a caller that must not miss a case: sealing turns
        the aggregate into a citable artifact, so a stale receipt that slipped
        through would be published as though it held. Adding a step to
        :class:`ReeAudit` without adding it here is the mistake this method
        exists to make hard, which is why it walks the model's own fields
        rather than a hand-written list.
        """
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
