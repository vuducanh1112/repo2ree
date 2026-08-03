"""Pure transitions over the portable REE aggregate."""

from __future__ import annotations

from repo2ree_core.domain.primitives import Digest, UtcInstant
from repo2ree_core.domain.ree.model import (
    BundleContents,
    Ree,
    ReeDefinition,
    ReeReceipts,
    ReeSeal,
    ReeSubject,
    Signature,
    canonical_subject_digest,
)
from repo2ree_core.domain.ree.receipt import (
    AcquireSourceReceipt,
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    EvaluateReproducibilityReceipt,
    GenerateSbomReceipt,
    ObserveHardwareReceipt,
    RunReceipt,
    TestActivationReceipt,
)


class ReePreconditionError(ValueError):
    """The requested transition is not legal for the current aggregate."""


def subject_digest(subject: ReeSubject) -> Digest:
    """Versioned, domain-separated identity of one portable REE subject."""
    return canonical_subject_digest(subject)


def revision_of(ree: Ree) -> Digest:
    """Optimistic-concurrency identity of the mutable REE head."""
    return subject_digest(ree.subject)


def replace_definition(ree: Ree, definition: ReeDefinition) -> Ree:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot be authored")

    old_names = {experiment.name for experiment in ree.subject.definition.experiments}
    new_names = {experiment.name for experiment in definition.experiments}
    retained_experiments = {
        name: receipt for name, receipt in ree.subject.receipts.experiments.items() if name in old_names & new_names
    }
    receipts = ree.subject.receipts.model_copy(update={"experiments": retained_experiments})
    return ree.model_copy(
        update={"subject": ree.subject.model_copy(update={"definition": definition, "receipts": receipts})}
    )


def replace_contents(ree: Ree, contents: BundleContents) -> Ree:
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE's content inventory is frozen")
    return ree.model_copy(update={"subject": ree.subject.model_copy(update={"contents": contents})})


def commit_receipt(ree: Ree, receipt: RunReceipt) -> Ree:
    """Replace the successful receipt slot owned by ``receipt``."""
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot accept new receipts")
    updates: dict[str, object]
    if isinstance(receipt, AcquireSourceReceipt):
        updates = {"source": receipt}
    elif isinstance(receipt, EvaluateReproducibilityReceipt):
        updates = {"evaluation": receipt}
    elif isinstance(receipt, ObserveHardwareReceipt):
        updates = {"hardware_observation": receipt}
    elif isinstance(receipt, BuildRuntimeReceipt):
        updates = {"build": receipt}
    elif isinstance(receipt, GenerateSbomReceipt):
        updates = {"sbom": receipt}
    elif isinstance(receipt, CrossCheckSbomReceipt):
        updates = {"sbom_cross_check": receipt}
    elif isinstance(receipt, TestActivationReceipt):
        updates = {"test_activation": receipt}
    else:
        experiments = dict(ree.subject.receipts.experiments)
        experiments[receipt.experiment_name] = receipt
        updates = {"experiments": experiments}
    receipts = ree.subject.receipts.model_copy(update=updates)
    return ree.model_copy(update={"subject": ree.subject.model_copy(update={"receipts": receipts})})


def clear_source(ree: Ree) -> Ree:
    """Remove source evidence and the complete downstream evidence chain."""
    if ree.seal is not None:
        raise ReePreconditionError("a sealed REE cannot remove its source")
    definition = ree.subject.definition.model_copy(update={"source": None})
    receipts = ReeReceipts(hardware_observation=ree.subject.receipts.hardware_observation)
    contents = BundleContents()
    subject = ree.subject.model_copy(update={"definition": definition, "receipts": receipts, "contents": contents})
    return ree.model_copy(update={"subject": subject})


def record_seal(
    ree: Ree,
    *,
    sealed_at: UtcInstant,
    signature: Signature | None = None,
) -> Ree:
    if ree.seal is not None:
        raise ReePreconditionError("REE is already sealed")
    seal = ReeSeal(sealed_at=sealed_at, ree_digest=subject_digest(ree.subject), signature=signature)
    return ree.model_copy(update={"seal": seal})


def validate_seal(ree: Ree) -> None:
    if ree.seal is not None and ree.seal.ree_digest != subject_digest(ree.subject):
        raise ValueError("REE seal digest does not match its subject")
