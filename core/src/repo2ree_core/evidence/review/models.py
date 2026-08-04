"""The reviewer's evidence record: what an attempt is and what it holds.

A *review attempt* is one independent reproduction of an author's REE, kept in
its own namespace so it can never write to author evidence. It advances through
the reviewer-facing lifecycle — source, build, activation, experiments — one
step at a time, and each step contributes two things: a receipt (what the
reviewer's machine did) and a verdict (what that settles). The attempt's own
``status`` is derived from its steps; it is never set directly, so "the attempt
failed" can never disagree with "which step failed".

A step that ran to completion and found something unwelcome is ``completed``
with an unwelcome verdict, never ``failed`` — "the review could not run" and
"the review has news" must stay distinguishable.

Schemas plus the pure record algebra over them. How a verdict is *reached* is
``comparison``; where the record lives is ``store``.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.domain.primitives import (
    Digest,
    ReePath,
    RunId,
    SourceType,
    Swhid,
    UtcInstant,
    WorkspacePath,
)
from repo2ree_core.domain.ree.receipt import receipt_run_id
from repo2ree_core.time_utils import OperationTiming
from repo2ree_protocol.command import ReviewBasis

ReviewStatus = Literal["running", "completed", "failed", "canceled"]
ReviewStepKey = Literal["source", "build", "activation", "experiments"]
ComparisonVerdict = Literal["identical", "different", "inconclusive"]
BuildVerdict = Literal["identical", "equivalent", "different", "inconclusive"]
# Activation has no middle ground: the runtime either came up under the author's
# own script or it did not. There is no ``inconclusive`` because the conditions
# that would produce one — no workspace, no activation script, a runtime the
# build step did not certify — stop the step before it probes anything, and are
# reported as step failures rather than as a verdict about the runtime.
ActivationVerdict = Literal["passed", "failed"]
# What one experiment's reproduction settled. ``reproduced`` is the ordinary
# pass: the author's own verify script accepted the reviewer's results.
# ``identical`` adds that the declared outputs came out byte for byte the same,
# which is more than the author claimed and worth recording where it happens.
# ``inconclusive`` covers an experiment with no verify script and one the author
# never ran themselves — in both cases there is no criterion to have met, and an
# absent criterion is not agreement.
ExperimentVerdict = Literal["identical", "reproduced", "different", "inconclusive"]

# What the reviewer's side of a comparison was produced from, and therefore how
# much the verdict is worth. ``independent`` means the reviewer's machine
# derived it from the outside world — the origin was fetched, the build was run.
# ``bundled`` means it came out of the REE itself, so the verdict certifies that
# the shipped bytes are the ones the author's evidence describes, and nothing
# about whether the world still produces them. Never collapse the two: a
# ``bundled`` verdict compared against the author's own record is expected to
# agree, so reading it as a reproduction would overstate it every time.
EvidenceBasis = Literal["independent", "bundled"]

# Attempt status resolution, most urgent first: a running step outranks a
# failure (the attempt is still moving), and any failure outranks a success.
_STATUS_PRECEDENCE: tuple[ReviewStatus, ...] = ("running", "failed", "canceled", "completed")


class _ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ================================================
# Review execution receipts
# ================================================


ReviewExecutionStatus = Literal["succeeded", "failed"]


class ReviewReceiptEnvelope(_ReviewModel):
    schema_version: Literal[1] = 1
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int = Field(ge=0)
    recorded_at: UtcInstant
    status: ReviewExecutionStatus


class ReviewAcquireSourceReceipt(ReviewReceiptEnvelope):
    operation: Literal["acquire_source"] = "acquire_source"
    origin_url: str | None = None
    source_type: SourceType
    requested_ref: str | None = None
    expected_swhid: Swhid | None = None
    observed_swhid: Swhid | None = None


class ReviewBuildRuntimeReceipt(ReviewReceiptEnvelope):
    operation: Literal["build_runtime"] = "build_runtime"
    build_runtime_script_path: ReePath | None = None
    build_runtime_script_digest: Digest | None = None
    runtime_path: WorkspacePath
    produced_runtime_digest: Digest


class ReviewActivationReceipt(ReviewReceiptEnvelope):
    operation: Literal["test_activation"] = "test_activation"
    run_script_path: ReePath
    run_script_digest: Digest
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None
    runtime_path: WorkspacePath
    runtime_digest: Digest


class ReviewExperimentReceipt(ReviewReceiptEnvelope):
    operation: Literal["run_experiment"] = "run_experiment"
    experiment_name: str = Field(min_length=1)
    run_script_path: ReePath
    run_script_digest: Digest
    verify_script_path: ReePath | None = None
    verify_script_digest: Digest | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None
    runtime_path: WorkspacePath | None = None
    runtime_digest: Digest | None = None
    produced_output_digest: Digest | None = None


class ReviewReceiptEnvelopeFields(TypedDict):
    run_id: RunId
    started_at: UtcInstant
    finished_at: UtcInstant
    duration_ms: int
    recorded_at: UtcInstant
    status: ReviewExecutionStatus


def review_receipt_envelope(
    run_id: str,
    timing: OperationTiming,
    status: ReviewExecutionStatus,
) -> ReviewReceiptEnvelopeFields:
    return ReviewReceiptEnvelopeFields(
        run_id=receipt_run_id(run_id),
        started_at=timing.started_at,
        finished_at=timing.finished_at,
        duration_ms=timing.duration_ms,
        recorded_at=timing.finished_at,
        status=status,
    )


# ================================================
# Comparisons
# ================================================


class SourceComparison(_ReviewModel):
    policy: Literal["swhid"] = "swhid"
    basis: EvidenceBasis = "independent"
    expected_swhid: str | None = None
    observed_swhid: str | None = None
    verdict: ComparisonVerdict


class PackageDeltaRecord(_ReviewModel):
    """One package the author's and the reviewer's runtimes disagree about."""

    ecosystem: str
    name: str
    expected_version: str | None = None
    observed_version: str | None = None


class BuildComparison(_ReviewModel):
    """How a reviewer's rebuilt runtime compares to the author's.

    Carries both tiers of evidence: the runtime digests (which settle
    ``identical`` when a build happens to be bit-reproducible) and the SBOM
    closure delta (which settles the rest). The listed deltas are capped
    samples — the ``*_count`` fields are the whole truth.
    """

    policy: Literal["sbom-closure"] = "sbom-closure"
    basis: EvidenceBasis = "independent"
    verdict: BuildVerdict
    # Runtime artifact tier.
    expected_runtime_digest: str | None = None
    observed_runtime_digest: str | None = None
    # Closure tier: which documents were compared, and by what.
    expected_sbom_digest: str | None = None
    observed_sbom_digest: str | None = None
    sbom_tool_version: str | None = None
    # Closure aggregates.
    expected_package_total: int = 0
    observed_package_total: int = 0
    matched: int = 0
    missing_count: int = 0
    extra_count: int = 0
    version_mismatch_count: int = 0
    advisory_count: int = 0
    # Capped samples.
    missing: list[PackageDeltaRecord] = Field(default_factory=list)
    extra: list[PackageDeltaRecord] = Field(default_factory=list)
    version_mismatches: list[PackageDeltaRecord] = Field(default_factory=list)
    advisory: list[PackageDeltaRecord] = Field(default_factory=list)


class ActivationOutcome(_ReviewModel):
    """Whether the runtime this attempt certified is inhabitable.

    Deliberately not a ``*Comparison``: nothing here is diffed against the
    author (see the module docstring). What the pass is *worth* is carried by
    ``basis``, which activation inherits rather than chooses — it runs in the
    workspace the build left behind and cannot tell whether the runtime there
    was rebuilt or unpacked from the bundle.

    ``runtime_digest`` is what the pass is *about*: the artifact actually
    probed, which the step requires to equal the one the build step certified.
    Without it a re-run build would silently leave a pass attached to a runtime
    that no longer exists — the same binding the aggregate audit applies
    when it evaluates activation against the runtime that was built.

    The exit codes separate the two failures that read alike but are not: a
    runtime that would not come up, and one that came up and was rejected by
    the author's own verify script.
    """

    policy: Literal["activation-probe"] = "activation-probe"
    basis: EvidenceBasis
    verdict: ActivationVerdict
    runtime_digest: str | None = None
    run_exit_code: int | None = None
    verify_exit_code: int | None = None


class ExperimentComparison(_ReviewModel):
    """Whether one experiment's result reproduced, by the author's own criterion.

    A comparison rather than an outcome, unlike activation: the author *does*
    have a recorded baseline here — their own run's verify verdict and output
    digest — so there is something to disagree with. What is compared is the
    criterion rather than the artifact, which is why both the author's expected
    verify-script digest and the reviewer's observed digest are carried:
    ``reproduced`` is worth exactly as much as the script that granted it, and a
    reader who cannot establish that the same script ran cannot audit the
    verdict.

    ``basis`` is inherited from the steps before, for the same reason activation
    inherits it: the experiment runs in the workspace the build left behind and
    cannot tell whether the runtime there was rebuilt or unpacked.
    """

    policy: Literal["verify-script"] = "verify-script"
    basis: EvidenceBasis
    verdict: ExperimentVerdict
    experiment_name: str
    # The criterion this verdict rests on.
    verify_script_path: str = ""
    # The author receipt binds the baseline claim to one criterion; the
    # reviewer digest names the script actually run. A reproduction verdict is
    # available only when both exist and agree.
    expected_verify_script_digest: str | None = None
    verify_script_digest: str | None = None
    expected_verify_exit_code: int | None = None
    observed_verify_exit_code: int | None = None
    run_exit_code: int | None = None
    # The stronger tier: byte equality of the declared outputs, when both sides
    # recorded one. Never decisive on its own — a mismatch here with a passing
    # verify script is still a reproduction.
    expected_output_digest: str | None = None
    observed_output_digest: str | None = None
    # What the run happened inside, bound for the same reason activation binds it.
    runtime_digest: str | None = None


# ================================================
# Records
# ================================================


class ReviewStepState(_ReviewModel):
    """The lifecycle state of one step within a review attempt."""

    step: ReviewStepKey
    status: ReviewStatus
    started_at: str
    updated_at: str
    failure: str | None = None


class ReviewRecord(_ReviewModel):
    """One independent review attempt: its lifecycle plus its evidence.

    ``status`` and ``failure`` are derived from ``steps`` — write through
    :func:`with_step` rather than setting them.
    """

    review_id: str
    created_at: str
    updated_at: str
    status: ReviewStatus
    steps: list[ReviewStepState] = Field(default_factory=list)
    source_receipt: ReviewAcquireSourceReceipt | None = None
    source_comparison: SourceComparison | None = None
    build_receipt: ReviewBuildRuntimeReceipt | None = None
    build_comparison: BuildComparison | None = None
    activation_receipt: ReviewActivationReceipt | None = None
    activation_outcome: ActivationOutcome | None = None
    # Plural where the other three steps are singular: an REE declares a list of
    # experiments and a reviewer reproduces them one at a time, so this step's
    # evidence is a set keyed by experiment name rather than one document. The
    # single ``ReviewStepState`` for ``experiments`` still records where the
    # lifecycle stands; which experiments settled, and how, is read from here.
    experiment_receipts: list[ReviewExperimentReceipt] = Field(default_factory=list)
    experiment_comparisons: list[ExperimentComparison] = Field(default_factory=list)
    failure: str | None = None


class ReviewSet(_ReviewModel):
    reviews: list[ReviewRecord] = Field(default_factory=list)


# ================================================
# Record Transitions
# ================================================


def new_review_record(review_id: str, *, at: str) -> ReviewRecord:
    """A fresh attempt with no steps taken yet."""
    return ReviewRecord(review_id=review_id, created_at=at, updated_at=at, status="running")


def with_step(
    record: ReviewRecord,
    step: ReviewStepKey,
    *,
    status: ReviewStatus,
    at: str,
    failure: str | None = None,
) -> ReviewRecord:
    """The record with one step's state written and the attempt re-derived.

    Re-running a step replaces its previous state: an attempt records where its
    lifecycle *stands*, while the per-run history stays in the review's
    ``runs/`` directory.
    """
    existing = step_state(record, step)
    state = ReviewStepState(
        step=step,
        status=status,
        started_at=at if existing is None or status == "running" else existing.started_at,
        updated_at=at,
        failure=failure,
    )
    steps = [other for other in record.steps if other.step != step] + [state]
    steps.sort(key=_step_order)
    return record.model_copy(
        update={
            "steps": steps,
            "updated_at": at,
            "status": derive_attempt_status(steps),
            "failure": _latest_failure(steps),
        }
    )


def with_experiment(
    record: ReviewRecord,
    receipt: ReviewExperimentReceipt,
    comparison: ExperimentComparison,
) -> ReviewRecord:
    """The record with one experiment's evidence written, replacing any prior run.

    Keyed by experiment name for the same reason :func:`with_step` is keyed by
    step: the attempt records where each part of its lifecycle *stands*, and the
    per-run history lives in ``runs/``. Re-running one experiment must not
    disturb the verdicts of its siblings, which is the whole reason this is a
    keyed replace rather than an append.
    """
    name = comparison.experiment_name
    receipts = [other for other in record.experiment_receipts if other.experiment_name != name] + [receipt]
    comparisons = [other for other in record.experiment_comparisons if other.experiment_name != name] + [comparison]
    receipts.sort(key=lambda entry: entry.experiment_name)
    comparisons.sort(key=lambda entry: entry.experiment_name)
    return record.model_copy(update={"experiment_receipts": receipts, "experiment_comparisons": comparisons})


def experiment_comparison(record: ReviewRecord, experiment_name: str) -> ExperimentComparison | None:
    """This attempt's verdict for one experiment, or None when it has not run."""
    for comparison in record.experiment_comparisons:
        if comparison.experiment_name == experiment_name:
            return comparison
    return None


def resolve_basis(requested: ReviewBasis, *, available: Collection[EvidenceBasis]) -> EvidenceBasis | None:
    """Settle a reviewer's requested basis against what a step can actually offer.

    Every step that takes a basis asks this same question, and the answer has to
    be the same one twice over. ``auto`` prefers the independent path and falls
    back, so a reviewer who states no preference always gets the strongest
    evidence on offer. An explicit request is never silently downgraded — handing
    back an integrity check to someone who asked for a reproduction is the one
    failure a review cannot afford — so it returns ``None`` instead, and the
    caller says why in the vocabulary of its own step.

    Only *what is on offer* differs between steps (an acquirable origin and a
    snapshot for source; a runnable recipe and a shipped artifact for the
    runtime), which is why that is the parameter and the rule above is not.
    """
    if requested != "auto":
        return requested if requested in available else None
    if "independent" in available:
        return "independent"
    return "bundled" if "bundled" in available else None


def attempt_basis(record: ReviewRecord) -> EvidenceBasis | None:
    """What this attempt's evidence as a whole is worth: its weakest link.

    A step that derives nothing from the outside world itself — activation runs
    the author's script in a workspace it did not assemble — has no basis of its
    own to report. It inherits this one, and inheriting the *weakest* settled
    basis is the only safe rule: an attempt that fetched the origin but then
    certified the runtime the bundle ships has not independently reproduced
    anything downstream of that runtime, whatever the source verdict says.

    ``None`` when nothing has settled yet, which is a precondition failure for
    any step that would have to inherit it rather than a basis to assume.
    """
    settled = [
        comparison.basis for comparison in (record.source_comparison, record.build_comparison) if comparison is not None
    ]
    if not settled:
        return None
    return "bundled" if "bundled" in settled else "independent"


def step_state(record: ReviewRecord, step: ReviewStepKey) -> ReviewStepState | None:
    """The recorded state of one step, or None when it has not been run."""
    for state in record.steps:
        if state.step == step:
            return state
    return None


def derive_attempt_status(steps: list[ReviewStepState]) -> ReviewStatus:
    """The attempt's status, as implied by the steps it has taken."""
    present = {state.status for state in steps}
    for status in _STATUS_PRECEDENCE:
        if status in present:
            return status
    return "running"


def _latest_failure(steps: list[ReviewStepState]) -> str | None:
    """The message of the most recently updated unsuccessful step."""
    unsuccessful = [state for state in steps if state.failure]
    if not unsuccessful:
        return None
    return max(unsuccessful, key=lambda state: state.updated_at).failure


def _step_order(state: ReviewStepState) -> int:
    """Lifecycle order, so a persisted record always reads front to back."""
    order: list[ReviewStepKey] = ["source", "build", "activation", "experiments"]
    return order.index(state.step)
