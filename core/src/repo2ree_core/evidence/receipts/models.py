"""Compatibility imports for the receipt domain vocabulary.

Receipt schemas moved to :mod:`repo2ree_core.domain.receipt` because they are
immutable facts about an REE.  Keep this module as a stable import path while
callers migrate; it deliberately contains no second schema or behaviour.
"""

from repo2ree_core.domain.receipt import (
    RECEIPT_SCHEMA_VERSION,
    AcquireSourceReceipt,
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    DriftStatus,
    GenerateSbomReceipt,
    ReceiptEnvelopeFields,
    RunExperimentReceipt,
    RunnableStepFields,
    RunReceipt,
    SnapshotUpstreamReceipt,
    WorkspaceDrift,
    experiment_step_key,
    latest_successful_receipts,
    receipt_adapter,
    receipt_envelope,
    receipt_run_id,
    receipt_step_key,
)

__all__ = [
    "RECEIPT_SCHEMA_VERSION",
    "AcquireSourceReceipt",
    "ActivationTestReceipt",
    "BuildRuntimeReceipt",
    "CrossCheckSbomReceipt",
    "DriftStatus",
    "GenerateSbomReceipt",
    "ReceiptEnvelopeFields",
    "RunExperimentReceipt",
    "RunReceipt",
    "RunnableStepFields",
    "SnapshotUpstreamReceipt",
    "WorkspaceDrift",
    "experiment_step_key",
    "latest_successful_receipts",
    "receipt_adapter",
    "receipt_envelope",
    "receipt_run_id",
    "receipt_step_key",
]
