"""Audit an REE: check every receipt it carries against what it now declares.

The question this module answers is not "how good is this REE" but "is what it
records still true of what it holds". An author edits a build script, re-points
a source, renames an experiment; the receipts from before those edits stay on
the aggregate, because deleting evidence is not the domain's call to make. What
*is* the domain's call is saying so — a receipt whose inputs have moved, or
whose declaration has been removed out from under it, is ``stale``, and every
operation that would build on it refuses, by name and with reasons.

Nothing here is stored. An audit is a function of one :class:`Ree` and holds
only for the aggregate it was derived from, which is why callers derive it at
the moment they need it rather than passing one around.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from repo2ree_core.domain.primitives import Digest, RunId
from repo2ree_core.domain.ree.model import Ree, ReeDefinition, ReeReceipts

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


# ================================================
# Audit Inputs
# ================================================


@dataclass(frozen=True)
class _Subject:
    """Everything auditing one step needs, and nothing a step may reach past.

    The steps are audited independently and in any order — each compares its
    own receipt against what the REE declares and against the receipts it was
    derived from, never against another step's *verdict*. Handing every step
    the same value keeps that honest: there is no partially-built audit here
    for one step to read a conclusion out of.
    """

    definition: ReeDefinition
    receipts: ReeReceipts
    content_digests: frozenset[Digest]
    bundle_settled: bool

    @classmethod
    def of(cls, ree: Ree) -> _Subject:
        return cls(
            definition=ree.subject.definition,
            receipts=ree.subject.receipts,
            content_digests=frozenset(entry.digest for entry in ree.subject.contents.entries),
            # A draft's inventory is empty by construction, so asking whether a
            # payload travels in the bundle has no answer until the seal.
            bundle_settled=ree.seal is not None,
        )

    def payload(self, digest: Digest | None, *, applicable: bool = True) -> PayloadStatus:
        if not (applicable and self.bundle_settled):
            return "not_applicable"
        return "present" if digest is not None and digest in self.content_digests else "omitted"


# ================================================
# Per-Step Audits
# ================================================


# The complaint a receipt earns by outliving what it was about. No per-step
# comparison produces this one: there is nothing left to compare it against,
# which is exactly the point. Phrased for the subject rather than the step,
# because the declaration that went away is often another step's — dropping the
# runtime recipe orphans the SBOM scanned off it, and the SBOM step never had a
# declaration of its own to lose.
_ORPHANED_RECEIPT_REASON = "the REE no longer declares what this evidence is about"


def _evidence_standing(*, applicable: bool, has_receipt: bool, complaints: bool) -> EvidenceStatus:
    """Whether a step's receipt still speaks for the REE, as one table.

    ``applicable`` is whether the REE declares anything for this step's evidence
    to be *about*, which is not always the step's own declaration. Source,
    hardware, runtime and activation each answer for themselves. Evaluation,
    SBOM and cross-check declare nothing of their own and answer for what they
    describe: a source to evaluate, a runtime to scan, both to reconcile. So a
    step can stop being applicable without its own definition changing at all.

    ``complaints`` is whether any comparison the step made — against that
    declaration, or against the receipts upstream of it — came back disagreeing.

    ==========  =======  ==========  ================================================
    applicable  receipt  complaints  standing
    ==========  =======  ==========  ================================================
    no          no       --          ``not_applicable``  nothing to be about
    yes         no       --          ``missing``         the step has not run
    yes         yes      no          ``current``         it still speaks for the REE
    yes         yes      yes         ``stale``           something it rests on moved
    no          yes      --          ``stale``           its subject is gone
    ==========  =======  ==========  ================================================

    The last row is the one worth stating separately, because it is the one
    that used to be silent. A receipt with nothing left to be about has nothing
    left to be compared against, so every per-step comparison passes and it
    would read ``current`` on the strength of tests nobody could run. It is
    inapplicable *and* it is present, and of those two facts only the second can
    be published — so the presence wins and the step reports ``stale``.
    """
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
    # Nothing declared and nothing recorded: there is no evidence question
    # here, and the caller's "has not run yet" reason would answer one nobody
    # asked. The only case where reasons and payload are dropped rather than
    # carried.
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


def _audit_source_step(subject: _Subject) -> StepAudit:
    declared, receipt = subject.definition.source, subject.receipts.source
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


def _audit_evaluation_step(subject: _Subject) -> StepAudit:
    receipt, source = subject.receipts.evaluation, subject.receipts.source
    reasons: list[str] = []
    if receipt and source and receipt.snapshot_digest != source.snapshot_digest:
        reasons.append("source snapshot changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("reproducibility has not been evaluated",)),
        applicable=subject.definition.source is not None,
        payload=subject.payload(receipt.report_digest if receipt else None),
    )


def _audit_hardware_step(subject: _Subject) -> StepAudit:
    """The one step whose receipt needs no declaration to mean something.

    Every other receipt attests that a *declared* thing was done, so it is
    orphaned once that declaration goes. A hardware observation is not evidence
    for a declaration at all — it is a record of the machine the work ran on,
    complete in itself. ``definition.hardware`` is a separate, optional
    statement about what the REE *requires*, and an author may observe without
    requiring, or require without having observed yet.

    So the step is applicable when either exists. Tying it to the declaration
    alone made an observed-but-undeclared REE report ``not_applicable`` while
    holding a receipt — harmless while that verdict hid the receipt, and a
    refused seal once it stopped.
    """
    receipt = subject.receipts.hardware_observation
    return _step(
        receipt.run_id if receipt else None,
        () if receipt else ("hardware has not been observed",),
        applicable=subject.definition.hardware is not None or receipt is not None,
    )


def _audit_runtime_step(subject: _Subject) -> StepAudit:
    build, receipt = subject.definition.build_runtime, subject.receipts.build
    reasons: list[str] = []
    if receipt:
        if subject.receipts.source and receipt.snapshot_digest != subject.receipts.source.snapshot_digest:
            reasons.append("source snapshot changed")
        if build is None:
            reasons.append("runtime build definition was removed")
        else:
            if receipt.build_runtime_script_digest != build.build_runtime_script_digest:
                reasons.append("runtime build script changed")
            if receipt.runtime_path != build.runtime_path:
                reasons.append("runtime path changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("runtime has not been built",)),
        applicable=_runtime_is_declared(subject),
        payload=subject.payload(receipt.produced_runtime_digest if receipt else None),
    )


def _runtime_is_declared(subject: _Subject) -> bool:
    """Whether this REE says a runtime should exist and how to produce one.

    One question, asked in one place, because more than one step turns on it —
    the build itself and the SBOM scanned off what it produced. It used to be
    spelled ``runtime is not None and build_runtime is not None`` at each site,
    a conjunction no other step needed, because the two halves of one recipe
    were two optional fields. They are one now, so the remaining check is what
    it always meant: a recipe that has been told where to leave its artifact.
    """
    build = subject.definition.build_runtime
    return build is not None and build.runtime_path is not None


def _audit_sbom_step(subject: _Subject) -> StepAudit:
    receipt, build = subject.receipts.sbom, subject.receipts.build
    reasons: list[str] = []
    if receipt and build and receipt.runtime_digest != build.produced_runtime_digest:
        reasons.append("runtime changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("SBOM has not been generated",)),
        # An SBOM describes a built runtime, so it is applicable on exactly the
        # terms the runtime step is: a declared runtime with no recipe to build
        # it is nothing for a scanner to read.
        applicable=_runtime_is_declared(subject),
        payload=subject.payload(receipt.sbom_digest if receipt else None),
    )


def _audit_sbom_cross_check_step(subject: _Subject) -> StepAudit:
    """The cross-check rests on two documents, and both can move under it.

    Reconciling a runtime SBOM against the source's declared dependencies is a
    statement about one *pair* of documents. Regenerate either — a rebuilt
    runtime rescanned, a re-run evaluation — and the counts this receipt
    carries describe a comparison nobody made.
    """
    receipt = subject.receipts.sbom_cross_check
    sbom, evaluation = subject.receipts.sbom, subject.receipts.evaluation
    reasons: list[str] = []
    if receipt:
        if sbom and receipt.sbom_digest != sbom.sbom_digest:
            reasons.append("SBOM changed")
        if evaluation and receipt.report_digest != evaluation.report_digest:
            reasons.append("reproducibility report changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("SBOM has not been cross-checked",)),
        # It needs both sides: a declared-dependency report (which needs a
        # source) and a runtime SBOM to reconcile against.
        applicable=subject.definition.source is not None and _runtime_is_declared(subject),
    )


def _audit_test_activation_step(subject: _Subject) -> StepAudit:
    declared, receipt = subject.definition.test_activation, subject.receipts.test_activation
    reasons: list[str] = []
    if receipt:
        if subject.receipts.source and receipt.snapshot_digest != subject.receipts.source.snapshot_digest:
            reasons.append("source snapshot changed")
        if declared is None:
            reasons.append("activation definition was removed")
        else:
            if receipt.run_script_digest != declared.run_script_digest:
                reasons.append("activation script changed")
            if receipt.verify_script_digest != declared.verify_script_digest:
                reasons.append("activation verification script changed")
        if subject.receipts.build and receipt.runtime_digest != subject.receipts.build.produced_runtime_digest:
            reasons.append("runtime changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("activation has not been tested",)),
        applicable=declared is not None,
    )


def _audit_experiments_step(subject: _Subject) -> tuple[ExperimentAudit, ...]:
    audits: list[ExperimentAudit] = []
    for experiment in subject.definition.experiments:
        receipt = subject.receipts.experiments.get(experiment.name)
        reasons: list[str] = []
        if receipt:
            if subject.receipts.source and receipt.snapshot_digest != subject.receipts.source.snapshot_digest:
                reasons.append("source snapshot changed")
            if receipt.run_script_digest != experiment.run_script_digest:
                reasons.append("experiment run script changed")
            if receipt.verify_script_digest != experiment.verify_script_digest:
                reasons.append("experiment verification script changed")
            if subject.receipts.build and receipt.runtime_digest != subject.receipts.build.produced_runtime_digest:
                reasons.append("runtime changed")
        audits.append(
            ExperimentAudit(
                name=experiment.name,
                run=_step(
                    receipt.run_id if receipt else None,
                    reasons or (() if receipt else ("experiment has not been run",)),
                    payload=subject.payload(
                        receipt.produced_output_digest if receipt else None,
                        applicable=bool(experiment.output_paths),
                    ),
                ),
            )
        )
    return tuple(audits)


# ================================================
# Entry point
# ================================================


def audit(ree: Ree) -> ReeAudit:
    subject = _Subject.of(ree)

    source_audit = _audit_source_step(subject)
    evaluation_audit = _audit_evaluation_step(subject)
    hardware_audit = _audit_hardware_step(subject)
    runtime_audit = _audit_runtime_step(subject)
    sbom_audit = _audit_sbom_step(subject)
    sbom_cross_check_audit = _audit_sbom_cross_check_step(subject)
    test_activation_audit = _audit_test_activation_step(subject)
    experiments_audit = _audit_experiments_step(subject)

    return ReeAudit(
        source=source_audit,
        evaluation=evaluation_audit,
        hardware=hardware_audit,
        runtime=runtime_audit,
        sbom=sbom_audit,
        sbom_cross_check=sbom_cross_check_audit,
        test_activation=test_activation_audit,
        experiments=experiments_audit,
    )
