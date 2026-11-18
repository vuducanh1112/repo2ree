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

from repo2ree_protocol.audit import EvidenceStatus, ExperimentAudit, PayloadStatus, ReeAudit, StepAudit
from repo2ree_ree.model import Ree, ReeDefinition, ReeReceipts
from repo2ree_ree.primitives import Digest, RunId

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
    content_paths: frozenset[str]
    bundle_settled: bool

    @classmethod
    def of(cls, ree: Ree) -> _Subject:
        return cls(
            definition=ree.subject.definition,
            receipts=ree.subject.receipts,
            content_digests=frozenset(entry.digest for entry in ree.subject.contents.entries),
            content_paths=frozenset(str(entry.path) for entry in ree.subject.contents.entries),
            # A draft's inventory is empty by construction, so asking whether a
            # payload travels in the bundle has no answer until the seal.
            bundle_settled=ree.seal is not None,
        )

    def payload(self, digest: Digest | None, *, applicable: bool = True) -> PayloadStatus:
        if not (applicable and self.bundle_settled):
            return "not_applicable"
        return "present" if digest is not None and digest in self.content_digests else "omitted"

    def experiment_payload(self, name: str, *, applicable: bool) -> PayloadStatus:
        """An experiment's outputs have one digest over them all, so they are found by where they travel."""
        if not (applicable and self.bundle_settled):
            return "not_applicable"
        return "present" if any(path.startswith(f"results/{name}/") for path in self.content_paths) else "omitted"


# ================================================
# Per-Step Audits
# ================================================


# The complaint a receipt earns by outliving what it was about. No per-step
# comparison produces this one: there is nothing left to compare it against,
# which is exactly the point. Phrased for the subject rather than the step,
# because the declaration that went away is often another step's — dropping the
# experiment environment recipe orphans the SBOM scanned off it, and the SBOM step never had a
# declaration of its own to lose.
_ORPHANED_RECEIPT_REASON = "the REE no longer declares what this evidence is about"


def _evidence_standing(*, applicable: bool, has_receipt: bool, complaints: bool) -> EvidenceStatus:
    """Whether a step's receipt still speaks for the REE, as one table.

    ``applicable`` is whether the REE declares anything for this step's evidence
    to be *about*, which is not always the step's own declaration. Source,
    hardware, experiment environment and activation each answer for themselves. Evaluation,
    SBOM and cross-check declare nothing of their own and answer for what they
    describe: a source to evaluate, an experiment environment to scan, both to reconcile. So a
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
    """The one step whose receipt needs no declaration to mean something.

    Every other receipt attests that a *declared* thing was done, so it is
    orphaned once that declaration goes. A hardware observation is not evidence
    for a declaration at all — it is a record of the machine the work ran on,
    complete in itself. ``definition.hbom`` is a separate, optional
    statement about what the REE *requires*, and an author may observe without
    requiring, or require without having observed yet.

    So the step is applicable when either exists. Tying it to the declaration
    alone made an observed-but-undeclared REE report ``not_applicable`` while
    holding a receipt — harmless while that verdict hid the receipt, and a
    refused seal once it stopped.
    """
    receipt = subject.receipts.observe_hardware
    return _step(
        receipt.run_id if receipt else None,
        () if receipt else ("hardware has not been observed",),
        applicable=subject.definition.hbom is not None or receipt is not None,
    )


def _audit_check_working_environment(subject: _Subject) -> StepAudit:
    """The author's check, as it last passed: against the check script and working environment declared now."""
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
    """Whether the step ran under another launch than the one the REE declares, or under none."""
    return ran_under != subject.definition.launch.launch_script_digest


def _experiment_environment_is_declared(subject: _Subject) -> bool:
    """Whether the build has been told where to leave the experiment environment: the build and its SBOM turn on it."""
    return subject.definition.experiment_environment.artifact_path is not None


def _audit_generate_sbom(subject: _Subject) -> StepAudit:
    receipt, build = subject.receipts.generate_sbom, subject.receipts.build_experiment_environment
    reasons: list[str] = []
    if receipt and build and receipt.experiment_environment_digest != build.produced_artifact_digest:
        reasons.append("experiment environment changed")
    return _step(
        receipt.run_id if receipt else None,
        reasons or (() if receipt else ("SBOM has not been generated",)),
        # An SBOM describes a built experiment environment, so it is applicable on exactly the
        # terms the experiment environment step is: a declared experiment environment with no recipe to build
        # it is nothing for a scanner to read.
        applicable=_experiment_environment_is_declared(subject),
        payload=subject.payload(receipt.sbom_digest if receipt else None),
    )


def _audit_cross_check_sbom(subject: _Subject) -> StepAudit:
    """The cross-check rests on two documents, and both can move under it.

    Reconciling an experiment environment SBOM against the source's declared dependencies is a
    statement about one *pair* of documents. Regenerate either — a rebuilt
    experiment environment rescanned, a re-run evaluation — and the counts this receipt
    carries describe a comparison nobody made.
    """
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
        # It needs both sides: a declared-dependency report (which needs a
        # source) and an experiment environment SBOM to reconcile against.
        applicable=subject.definition.source is not None and _experiment_environment_is_declared(subject),
    )


def _audit_activate_experiment_environment(subject: _Subject) -> StepAudit:
    """The activation, run alone: what it ran with, against what the REE now declares and was built from."""
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


# ================================================
# Entry point
# ================================================


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
