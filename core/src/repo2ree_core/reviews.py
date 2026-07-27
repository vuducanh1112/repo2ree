"""Persistent reviewer evidence sets and the comparisons that certify them.

A *review attempt* is one independent reproduction of an author's REE, kept in
its own namespace so it can never write to author evidence. It advances through
the reviewer-facing lifecycle — source, build, activation, experiments — one
step at a time, and each step contributes two things: a receipt (what the
reviewer's machine did) and a verdict (what that settles). The attempt's own
``status`` is derived from its steps; it is never set directly, so "the attempt
failed" can never disagree with "which step failed".

A step that ran to completion and found something unwelcome is ``completed``
with an unwelcome verdict, never ``failed``: the reviewer's machine did its job,
and losing that distinction would collapse "the review could not run" into "the
review has news" — the second being the whole point of running one.

What settles a verdict differs per step, because the certifiable property does:

* source — SWHID identity, which *is* reproducible bit for bit;
* build — SBOM closure equivalence, because container builds are routinely not
  bit-reproducible even from identical inputs (see
  :mod:`repo2ree_core.sbom.equivalence`). A digest match is the stronger
  verdict where it happens, not the only acceptable one.
* activation — no comparison at all. There is no author artifact to reproduce
  here: the author's own activation is a precondition of a credible baseline,
  not a baseline to diff against, so "theirs passed and so did mine" would
  certify nothing beyond the second half. The reviewer's own probe is the whole
  claim, and it is recorded as an :class:`ActivationOutcome` rather than a
  comparison to keep that distinction visible in the type.
* experiments — the author's own verify script, re-run against the reviewer's
  results. Output bytes are the wrong bar: a run that stamps a timestamp or
  draws a seed produces different bytes on every honest reproduction, so
  demanding equality would report a red verdict for a result that reproduced
  perfectly. The author already declared what counts as a correct result — the
  verify script — so a pass is the verdict, and matching output digests are
  recorded as the stronger tier where they happen (see
  :func:`compare_experiment_results`).
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.receipts import (
    AcquireSourceReceipt,
    ActivationTestReceipt,
    BuildRuntimeReceipt,
    RunExperimentReceipt,
)
from repo2ree_core.reserved_paths import experiment_slug
from repo2ree_core.sbom.cyclonedx import ObservedPackage
from repo2ree_core.sbom.equivalence import (
    PackageDelta,
    closure_verdict,
    compare_sbom_closures,
)
from repo2ree_core.storage.layout import ReeLayout, ReviewLayout

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
    that no longer exists — the same binding the author-side scorecard makes
    when it only counts activation against the runtime that was built.

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
    criterion rather than the artifact, which is why ``verify_script_digest`` is
    carried: ``reproduced`` is worth exactly as much as the script that granted
    it, and a reader who cannot see which script ran cannot audit the verdict.

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
    source_receipt: AcquireSourceReceipt | None = None
    source_comparison: SourceComparison | None = None
    build_receipt: BuildRuntimeReceipt | None = None
    build_comparison: BuildComparison | None = None
    activation_receipt: ActivationTestReceipt | None = None
    activation_outcome: ActivationOutcome | None = None
    # Plural where the other three steps are singular: an REE declares a list of
    # experiments and a reviewer reproduces them one at a time, so this step's
    # evidence is a set keyed by experiment name rather than one document. The
    # single ``ReviewStepState`` for ``experiments`` still records where the
    # lifecycle stands; which experiments settled, and how, is read from here.
    experiment_receipts: list[RunExperimentReceipt] = Field(default_factory=list)
    experiment_comparisons: list[ExperimentComparison] = Field(default_factory=list)
    failure: str | None = None


class ReviewSet(_ReviewModel):
    reviews: list[ReviewRecord] = Field(default_factory=list)


# ================================================
# Comparison Construction
# ================================================


def compare_source_swhids(
    expected: str,
    observed: str,
    *,
    basis: EvidenceBasis = "independent",
) -> SourceComparison:
    """Compare the author's source identity with the tree the reviewer holds.

    The comparison is the same either way — a SWHID is a SWHID — but what it
    settles depends on ``basis``: an independently fetched tree agreeing with
    the recorded identity means the origin still serves the authored source,
    while an extracted snapshot agreeing means the bundle is intact.
    """
    normalized_expected = expected.strip() or None
    normalized_observed = observed.strip() or None
    if normalized_expected is None or normalized_observed is None:
        verdict: ComparisonVerdict = "inconclusive"
    elif normalized_expected == normalized_observed:
        verdict = "identical"
    else:
        verdict = "different"
    return SourceComparison(
        basis=basis,
        expected_swhid=normalized_expected,
        observed_swhid=normalized_observed,
        verdict=verdict,
    )


def compare_build_runtimes(
    *,
    expected_runtime_digest: str | None,
    observed_runtime_digest: str | None,
    expected_packages: list[ObservedPackage],
    observed_packages: list[ObservedPackage],
    expected_sbom_digest: str | None = None,
    observed_sbom_digest: str | None = None,
    sbom_tool_version: str | None = None,
    basis: EvidenceBasis = "independent",
) -> BuildComparison:
    """Certify a runtime against the author's record, digests first.

    The ladder, strongest first: equal runtime digests mean the build is bit
    reproducible (``identical``); otherwise the dependency closures decide
    (``equivalent`` / ``different``); a closure that cannot be compared at all
    — no author SBOM, or a scan that yielded nothing — is ``inconclusive``
    rather than a pass, because an absent baseline is not agreement.

    The ladder is basis-blind on purpose: a ``bundled`` runtime is scanned and
    diffed by exactly the same rules, so a shipped artifact that does *not*
    match the author's own receipt still comes back ``different``. What the
    resulting agreement is worth is carried by ``basis``, not by the verdict.
    """
    delta = compare_sbom_closures(expected_packages, observed_packages)
    if expected_runtime_digest and expected_runtime_digest == observed_runtime_digest:
        verdict: BuildVerdict = "identical"
    else:
        verdict = closure_verdict(delta)
    return BuildComparison(
        basis=basis,
        verdict=verdict,
        expected_runtime_digest=expected_runtime_digest,
        observed_runtime_digest=observed_runtime_digest,
        expected_sbom_digest=expected_sbom_digest,
        observed_sbom_digest=observed_sbom_digest,
        sbom_tool_version=sbom_tool_version,
        expected_package_total=delta.expected_total,
        observed_package_total=delta.observed_total,
        matched=delta.matched,
        missing_count=delta.missing_count,
        extra_count=delta.extra_count,
        version_mismatch_count=delta.version_mismatch_count,
        advisory_count=delta.advisory_count,
        missing=_delta_records(delta.missing),
        extra=_delta_records(delta.extra),
        version_mismatches=_delta_records(delta.version_mismatches),
        advisory=_delta_records(delta.advisory),
    )


def compare_experiment_results(
    *,
    experiment_name: str,
    basis: EvidenceBasis,
    verify_script_path: str,
    verify_script_digest: str | None,
    expected_verify_exit_code: int | None,
    observed_verify_exit_code: int | None,
    run_exit_code: int | None,
    expected_output_digest: str | None = None,
    observed_output_digest: str | None = None,
    runtime_digest: str | None = None,
) -> ExperimentComparison:
    """Settle whether one experiment reproduced, by the author's own criterion.

    The ladder, in the order it is decided:

    * No verify script declared — ``inconclusive``. All that remains is "the run
      script exited 0", which for a script whose last act is to write a results
      file says only that something ran. Reporting that as a reproduction would
      make the verdict free, and a free verdict certifies nothing.
    * The author never ran this experiment themselves — ``inconclusive``. There
      is no baseline claim to have reproduced, and an absent baseline is not
      agreement (the same rule :func:`compare_build_runtimes` applies to a
      missing SBOM).
    * Verify exited nonzero — ``different``. The author's own criterion, applied
      to the reviewer's results, rejected them. This is the step working.
    * Verify exited 0 — ``reproduced``, upgraded to ``identical`` when both
      sides recorded an output digest and the two agree.

    Note what is deliberately *not* here: a digest mismatch never downgrades a
    passing verify. Timestamps, seeds, and hostnames land in output files on
    every honest re-run, and the author already said what correctness means.
    """
    if not verify_script_path.strip():
        verdict: ExperimentVerdict = "inconclusive"
    elif expected_verify_exit_code is None:
        verdict = "inconclusive"
    elif observed_verify_exit_code != 0:
        verdict = "different"
    elif expected_output_digest is not None and expected_output_digest == observed_output_digest:
        verdict = "identical"
    else:
        verdict = "reproduced"
    return ExperimentComparison(
        basis=basis,
        verdict=verdict,
        experiment_name=experiment_name,
        verify_script_path=verify_script_path,
        verify_script_digest=verify_script_digest,
        expected_verify_exit_code=expected_verify_exit_code,
        observed_verify_exit_code=observed_verify_exit_code,
        run_exit_code=run_exit_code,
        expected_output_digest=expected_output_digest,
        observed_output_digest=observed_output_digest,
        runtime_digest=runtime_digest,
    )


def _delta_records(deltas: list[PackageDelta]) -> list[PackageDeltaRecord]:
    return [
        PackageDeltaRecord(
            ecosystem=delta.ecosystem,
            name=delta.name,
            expected_version=delta.expected_version,
            observed_version=delta.observed_version,
        )
        for delta in deltas
    ]


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
    receipt: RunExperimentReceipt,
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


# ================================================
# Persistence
# ================================================


def write_review_record(layout: ReviewLayout, record: ReviewRecord) -> None:
    _atomic_write_json(layout.metadata, record.model_dump(mode="json"))


def read_review_record(layout: ReviewLayout) -> ReviewRecord | None:
    """The persisted attempt, or None when this namespace holds no review."""
    with suppress(Exception):
        return ReviewRecord.model_validate_json(layout.metadata.read_text(encoding="utf-8"))
    return None


def write_review_source_evidence(
    layout: ReviewLayout,
    receipt: AcquireSourceReceipt,
    comparison: SourceComparison,
) -> None:
    _write_review_evidence(layout, receipt, "source", comparison.model_dump(mode="json"))


def write_review_build_evidence(
    layout: ReviewLayout,
    receipt: BuildRuntimeReceipt,
    comparison: BuildComparison,
) -> None:
    _write_review_evidence(layout, receipt, "build", comparison.model_dump(mode="json"))


def write_review_activation_evidence(
    layout: ReviewLayout,
    receipt: ActivationTestReceipt,
    outcome: ActivationOutcome,
) -> None:
    """Persist the activation probe beside the other steps' evidence.

    Filed under ``comparisons/activation.json`` despite not being a comparison:
    the directory is the attempt's per-step verdict store, and giving activation
    its own would split one lookup into two for a distinction the reader already
    gets from the document's ``policy``.
    """
    _write_review_evidence(layout, receipt, "activation", outcome.model_dump(mode="json"))


def write_review_experiment_evidence(
    layout: ReviewLayout,
    receipt: RunExperimentReceipt,
    comparison: ExperimentComparison,
) -> None:
    """Persist one experiment's evidence under its own slug.

    Unlike the other three steps, the per-operation slot cannot be
    ``receipts/run_experiment.json``: every experiment shares that operation, so
    a second one would overwrite the first's receipt and the attempt would end
    up holding one experiment's evidence for all of them. The author side hit
    this first and answered it by keying experiments under a slug directory
    (:func:`repo2ree_core.receipts.author_receipt_path`); this mirrors that so
    both sides of the same REE are laid out the same way.
    """
    slug = experiment_slug(receipt.experiment_name)
    payload = receipt.model_dump(mode="json")
    _atomic_write_json(layout.run_receipt(receipt.run_id), payload)
    _atomic_write_json(layout.experiment_receipt(slug), payload)
    _atomic_write_json(layout.experiment_comparison(slug), comparison.model_dump(mode="json"))


def _write_review_evidence(
    layout: ReviewLayout,
    receipt: AcquireSourceReceipt | BuildRuntimeReceipt | ActivationTestReceipt,
    step: ReviewStepKey,
    comparison: dict[str, object],
) -> None:
    """Persist one step's receipt twice (by run, by operation) and its comparison.

    The same selection rule the author side uses: ``runs/`` keeps the immutable
    history, ``receipts/<operation>.json`` keeps the latest per operation.
    """
    payload = receipt.model_dump(mode="json")
    _atomic_write_json(layout.run_receipt(receipt.run_id), payload)
    _atomic_write_json(layout.operation_receipt(receipt.operation), payload)
    _atomic_write_json(layout.comparison(step), comparison)


def load_reviews(layout: ReeLayout) -> ReviewSet:
    records: list[ReviewRecord] = []
    if not layout.reviews.is_dir():
        return ReviewSet()
    for path in layout.reviews.glob("*/review.json"):
        with suppress(Exception):
            records.append(ReviewRecord.model_validate_json(path.read_text(encoding="utf-8")))
    records.sort(key=lambda record: (record.created_at, record.review_id), reverse=True)
    return ReviewSet(reviews=records)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
