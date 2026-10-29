from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_ree.primitives import Digest, ReePath, RunId, SourceType, Swhid, UtcInstant, WorkspacePath

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
