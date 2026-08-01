"""Receipt schemas: immutable machine-produced facts about an REE.

A receipt binds one executed run to the inputs it ran against (as a
re-runner will have them: the *materialization inputs*, never the live
workspace tree) and to the outputs it produced. Receipts are evidence
against accidents — stale inputs, a wrong artifact wired up — not
attestation against adversarial authors. They are provenance records,
never cache keys.

The envelope fields (schema version, run id, operation, timestamp, status) are
uniform across operations so callers can select "latest successful receipt per
step" without parsing operation-specific bodies; the input/output slices are
operation-specific and typed, so the seal-time check and any later classifier
can match exhaustively instead of probing key conventions.

Receipts are domain vocabulary, not an evidence-store implementation detail.
Schemas and the pure functions over them live here; where receipts live on disk
is :mod:`repo2ree_core.persistence.receipts`, while what their digests mean
against the current REE is :mod:`repo2ree_core.evidence.consistency`.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from repo2ree_core.domain.primitives import (
    ArtifactPath,
    Digest,
    GitRevision,
    ReePath,
    RunId,
    ScriptPath,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_core.time_utils import OperationTiming
from repo2ree_protocol.result import ActionStatus

RECEIPT_SCHEMA_VERSION: Literal[1] = 1

# Paths listed in a drift verdict are capped so a wholesale workspace change
# cannot balloon the receipt; the status alone carries the verdict.


class _ReceiptModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ================================================
# Workspace drift verdict
# ================================================


DriftStatus = Literal["clean", "modified", "unknown"]


class WorkspaceDrift(_ReceiptModel):
    """Whether the workspace still equals ``materialize(snapshot + overlay)``.

    ``unknown`` means there was no materialization marker to check against
    (the workspace was never materialized through the tracked path).
    ``changed_paths`` is capped; ``changed_path_count`` carries the true count.
    """

    status: DriftStatus
    changed_paths: list[ReePath] = Field(default_factory=list)
    changed_path_count: int = 0


# ================================================
# Receipt models — shared envelope + per-operation slices
# ================================================


class _ReceiptEnvelope(_ReceiptModel):
    """Fields uniform across every operation's receipt.

    Selection ("latest successful receipt per step") only ever needs these,
    so scanning ``runs/`` never depends on operation-specific bodies.
    """

    schema_version: Literal[1] = RECEIPT_SCHEMA_VERSION
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int = Field(ge=0)
    recorded_at: UtcInstant
    status: ActionStatus

    @model_validator(mode="after")
    def _ordered_timestamps(self) -> _ReceiptEnvelope:
        if self.finished_at < self.started_at:
            raise ValueError("receipt finished_at must not precede started_at")
        if self.recorded_at < self.finished_at:
            raise ValueError("receipt recorded_at must not precede finished_at")
        return self


class AcquireSourceReceipt(_ReceiptEnvelope):
    """Chain root: no inputs, records what was acquired."""

    operation: Literal["acquire_source"] = "acquire_source"
    origin_url: str = ""
    source_type: str = ""
    revision: GitRevision | None = None
    expected_swhid: Swhid | None = None
    observed_swhid: Swhid | None = None


class SnapshotUpstreamReceipt(_ReceiptEnvelope):
    operation: Literal["snapshot_upstream"] = "snapshot_upstream"
    snapshot_digest: Digest | None = None


class BuildRuntimeReceipt(_ReceiptEnvelope):
    operation: Literal["build_runtime"] = "build_runtime"
    workspace_drift: WorkspaceDrift | None = None
    # Input slice
    snapshot_digest: Digest | None = None
    build_script_path: ScriptPath | None = None
    build_script_digest: Digest | None = None
    # Produced output
    runtime_path: WorkspacePath | None = None
    produced_runtime_digest: Digest | None = None


class GenerateSbomReceipt(_ReceiptEnvelope):
    """Workspace-independent: consumes only the declared runtime artifact."""

    operation: Literal["generate_sbom"] = "generate_sbom"
    # Input slice
    runtime_path: WorkspacePath
    declared_runtime_digest: Digest | None = None
    # Produced output
    sbom_path: ArtifactPath | None = None
    sbom_digest: Digest | None = None
    # Provenance of the scan itself — what "observed" means depends on both.
    sbom_format: str | None = None
    tool_version: str | None = None


class CrossCheckSbomReceipt(_ReceiptEnvelope):
    """Aggregates of the SBOM ↔ declared-inventory cross-check.

    Carries only counts plus the digest of the SBOM it consumed: the digest
    chain (this → ``GenerateSbomReceipt.sbom_digest`` → build receipt) ties
    the verdict to the built runtime; per-dependency detail stays in the
    report artifact.
    """

    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    # Input slice
    sbom_digest: Digest | None = None
    # Aggregates
    declared_direct_total: int = 0
    observed_matched: int = 0
    version_mismatches: int = 0
    undeclared_same_ecosystem: int = 0
    observed_total: int = 0


class _RunnableReceipt(_ReceiptEnvelope):
    """Shared slice for activation and experiments (both are runnables).

    ``declared_runtime_digest`` is the declared tier only: it proves the
    artifact's state at run time, not that the script used it. A pass verdict
    is relative to the verify script, so its digest is part of the input
    slice alongside the run script's.

    The two exit codes are recorded separately because envelope ``status``
    cannot distinguish the failures they name: a run script that never brought
    the runtime up, and a run that came up and was then rejected by the
    author's own verify script. Both read as "failed" and mean different things
    to whoever has to act on them. ``None`` on receipts written before either
    field existed, and on a half that never ran.
    """

    workspace_drift: WorkspaceDrift | None = None
    snapshot_digest: Digest | None = None
    run_script_path: ScriptPath | None = None
    run_script_digest: Digest | None = None
    run_exit_code: int | None = None
    verify_script_path: ScriptPath | None = None
    verify_script_digest: Digest | None = None
    verify_exit_code: int | None = None
    runtime_path: WorkspacePath | None = None
    declared_runtime_digest: Digest | None = None


class ActivationTestReceipt(_RunnableReceipt):
    operation: Literal["activation_test"] = "activation_test"


class RunExperimentReceipt(_RunnableReceipt):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = ""
    # Produced output: digest of the declared outputs captured after a
    # successful run. Parallels ``BuildRuntimeReceipt.produced_runtime_digest``;
    # ``None`` when the experiment declares no outputs or the run did not
    # succeed. Binds the sealed baseline to the bytes verify actually ran over.
    produced_output_digest: Digest | None = None


RunReceipt = Annotated[
    AcquireSourceReceipt
    | SnapshotUpstreamReceipt
    | BuildRuntimeReceipt
    | GenerateSbomReceipt
    | CrossCheckSbomReceipt
    | ActivationTestReceipt
    | RunExperimentReceipt,
    Field(discriminator="operation"),
]


receipt_adapter: TypeAdapter[RunReceipt] = TypeAdapter(RunReceipt)


# ================================================
# Pure functions over receipts
# ================================================


class ReceiptEnvelopeFields(TypedDict):
    """The envelope half of a receipt constructor's arguments.

    A TypedDict rather than a base-class factory so a handler still names its
    operation-specific fields itself: ``Receipt(**receipt_envelope(...), path=…)``
    keeps the call site's shape — every field visible at the constructor — while
    the five fields that are the same everywhere are spelled once.
    """

    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int
    recorded_at: UtcInstant
    status: ActionStatus


def receipt_envelope(run_id: str, timing: OperationTiming, status: ActionStatus) -> ReceiptEnvelopeFields:
    """Derive the uniform receipt envelope from one run's timing and outcome.

    ``recorded_at`` is the run's finish instant rather than "now": a receipt
    records when the run it describes ended, and taking a second clock reading
    here would let the two disagree by however long recording took.
    """
    return ReceiptEnvelopeFields(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status=status,
    )


class RunnableStepFields(ReceiptEnvelopeFields):
    """The envelope plus the slice every runnable step records, as arguments.

    The constructor-argument mirror of :class:`_RunnableReceipt`, for the same
    reason :class:`ReceiptEnvelopeFields` mirrors the envelope: a runnable
    step's receipt is built by the handler that owns the step, from fields the
    shared runner collected. Spreading an untyped mapping into that constructor
    would be the one place a receipt is assembled without the checker watching —
    and a field renamed on the model would then survive to runtime, where an
    ``extra="forbid"`` model rejects it *after* the run it was recording.
    """

    workspace_drift: WorkspaceDrift
    snapshot_digest: Digest | None
    run_script_path: ScriptPath
    run_script_digest: Digest | None
    run_exit_code: int | None
    verify_script_path: ScriptPath | None
    verify_script_digest: Digest | None
    verify_exit_code: int | None
    runtime_path: WorkspacePath | None
    declared_runtime_digest: Digest | None


def receipt_run_id(run_id: str) -> RunId:
    """A run id safe to key a receipt file by.

    Dispatched runs carry a registry-issued unique id; manual CLI runs all
    share the literal ``"manual"``, which would make successive receipts
    overwrite each other — give those a unique suffix instead.
    """
    if run_id and run_id != "manual":
        return RunId(run_id)
    return RunId(f"manual-{uuid4().hex[:12]}")


def experiment_step_key(experiment_name: str) -> str:
    """The selection key for one experiment's evidence.

    Experiments are the one step with more than one subject, so their receipts
    cannot be keyed by operation alone. This composite key is what joins an
    author's recorded run to the reviewer's reproduction of the same experiment,
    which is why it is spelled here and nowhere else: two spellings of a join key
    are two joins, and the one that drifts silently stops matching rather than
    failing.
    """
    return f"experiment:{experiment_name}"


def receipt_step_key(receipt: RunReceipt) -> str:
    """Stable selection key: operation, except experiments are keyed by name."""
    if isinstance(receipt, RunExperimentReceipt):
        return experiment_step_key(receipt.experiment_name)
    return receipt.operation


def latest_successful_receipts(receipts: list[RunReceipt]) -> dict[str, RunReceipt]:
    """Latest successful receipt per step, keyed by operation (per-experiment
    for ``run_experiment``).
    """
    latest: dict[str, RunReceipt] = {}
    for receipt in receipts:
        if receipt.status != "succeeded":
            continue
        key = receipt_step_key(receipt)
        current = latest.get(key)
        # recorded_at is ISO-8601 UTC, so lexicographic order is time order.
        if current is None or receipt.recorded_at >= current.recorded_at:
            latest[key] = receipt
    return latest
