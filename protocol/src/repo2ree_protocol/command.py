"""Typed command envelope for repo2ree operations.

The Command union is the wire form between the control plane (api) and the
execution plane (in-container CLI). Each variant carries fully-typed args
for one operation. The discriminator field ``operation`` is the stable
identifier; ``repo2ree_protocol.verbs`` spells each command as the ``ree`` argv
that runs it, from the markers on these fields.

Add new operations by:
  1. Defining a new ``*Args`` + ``*Command`` pair below.
  2. Extending the ``Command`` union annotation.
  3. Adding a branch in ``run_command``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from repo2ree_protocol.argv import POSITIONAL, STDIN
from repo2ree_ree.review import ReviewLaunch
from repo2ree_ree.signature import SignatureClaim

# Every operation the specification's catalogue names (assurance/spec/vocabulary/operation.toml): each command's
# ``operation`` is one of them, and initialize_ree is the one a workbench runs without a command.
OperationName = Literal[
    "initialize_ree",
    "acquire_source",
    "remove_source",
    "load_ree_bundle",
    "patch_ree_definition",
    "write_script",
    "suggest_scripts",
    "lint_scripts",
    "evaluate_reproducibility",
    "observe_hardware",
    "check_working_environment",
    "materialize_workspace",
    "build_experiment_environment",
    "generate_sbom",
    "cross_check_sbom",
    "activate_experiment_environment",
    "run_experiment",
    "seal_ree",
    "sign_ree",
    "sign_review",
    "review_acquire_source",
    "review_build_experiment_environment",
    "review_activate_experiment_environment",
    "review_run_experiment",
]

# What a review step is allowed to reproduce *from*.
#
# ``independent`` is the strong form: fetch the source from its recorded origin,
# rebuild the experiment environment from that source. ``bundled`` uses what the REE already
# carries — the frozen snapshot, the shipped experiment environment artifact — which makes a
# review possible with no network and no live origin, at the cost of being an
# integrity check rather than an independent reproduction. ``auto`` picks the
# strong form whenever the baseline supports it and falls back to ``bundled``.
ReviewBasis = Literal["auto", "independent", "bundled"]


class ReviewAcquireSourceArgs(BaseModel):
    """Acquire the author-pinned source into one isolated review attempt."""

    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]
    # ``independent`` fetches the recorded origin; ``bundled`` extracts the REE's
    # own snapshot.tar.gz, which is what makes a bundle-only REE reviewable.
    basis: ReviewBasis = Field(
        default="auto",
        description="independent fetches the recorded origin; bundled extracts the REE's own snapshot; "
        "auto takes independent where the REE allows it.",
    )
    launch: ReviewLaunch = Field(
        default_factory=ReviewLaunch,
        description="How every script of the review is launched: the author's launch with the reviewer's options, "
        "or natively.",
    )


class ReviewAcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_acquire_source"] = "review_acquire_source"
    args: ReviewAcquireSourceArgs


class ReviewBuildExperimentEnvironmentArgs(BaseModel):
    """Rebuild the experiment environment inside an existing review attempt and certify it.

    Joins an attempt the source step already created rather than opening a new
    one: the build is reproduced from *that* attempt's independently acquired
    source, and its verdict is only meaningful next to that source verdict.
    """

    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]
    # ``independent`` runs the author's build script over the reviewer's own
    # source; ``bundled`` certifies the experiment environment artifact the REE already ships
    # instead of building one, for baselines whose build cannot run here.
    basis: ReviewBasis = Field(
        default="auto",
        description="independent runs the author's build over the review's source; bundled certifies the "
        "experiment environment the REE ships; auto takes independent where it can.",
    )


class ReviewBuildExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_build_experiment_environment"] = "review_build_experiment_environment"
    args: ReviewBuildExperimentEnvironmentArgs


class ReviewActivateExperimentEnvironmentArgs(BaseModel):
    """Probe the experiment environment an attempt certified, inside that attempt's workspace.

    No ``basis``: activation runs *in* the workspace the build step left behind
    and cannot tell how the experiment environment got there — deliberately, so the author's
    scripts run unchanged on either basis. What the resulting pass is worth is
    therefore not this step's to choose; it is inherited from the bases the
    source and build steps already settled (see ``reviews.attempt_basis``).
    """

    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]


class ReviewActivateExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_activate_experiment_environment"] = "review_activate_experiment_environment"
    args: ReviewActivateExperimentEnvironmentArgs


class ReviewRunExperimentArgs(BaseModel):
    """Reproduce one named experiment inside an attempt whose experiment environment came up.

    One experiment per command, mirroring the author's ``run_experiment``: each
    reproduction gets its own run, its own log, and its own receipt, and a
    reviewer who cares about one experiment should not have to sit through the
    others. Running them all is the caller issuing this command in sequence.

    No ``basis``, for the same reason activation takes none: the experiment runs
    in the workspace the build left behind and inherits what that evidence is
    worth.
    """

    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review, an attempt of its own beside the REE.")]
    experiment_name: Annotated[str, POSITIONAL, Field(description="The experiment to reproduce.")]


class ReviewRunExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_run_experiment"] = "review_run_experiment"
    args: ReviewRunExperimentArgs


class MaterializeWorkspaceArgs(BaseModel):
    """No args: lays out ``workspace/`` from the source and the overlay, a view for people that no step reads."""

    model_config = ConfigDict(extra="forbid")


class MaterializeWorkspaceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["materialize_workspace"] = "materialize_workspace"
    args: MaterializeWorkspaceArgs = MaterializeWorkspaceArgs()


class AcquireSourceArgs(BaseModel):
    """Acquire a REE source from an origin or a staged upload.

    An REE holds at most one source, and acquisition is only legal into an
    empty slot. There is no replace: a source already there is the author's,
    and giving it up is a separate act they perform with ``remove_source``.
    Acquiring into an occupied slot is a precondition failure, never a reset —
    a reset here would erase every condition the acquisition could refuse on,
    which is exactly how a sealed REE used to get silently unsealed.
    """

    model_config = ConfigDict(extra="forbid")

    mode: Literal["download", "upload"] = Field(
        description="download fetches --origin-url; upload takes an archive staged in the REE."
    )
    origin_url: str = Field(default="", description="Where to download the source from.")
    source_type: Literal["git", "tarball", "zip"] | None = Field(
        default=None, description="What the origin serves; by default read off the URL."
    )
    # The concrete commit it resolves to is observed off the acquired tree and recorded on the source receipt.
    revision: str = Field(default="", description="The git commit, branch or tag; by default the origin's HEAD.")
    upload_token: str = Field(default="", description="The staged archive's token.")
    archive_name: str = Field(default="", description="The staged archive's file name.")


class AcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["acquire_source"] = "acquire_source"
    args: AcquireSourceArgs


class LoadReeBundleArgs(BaseModel):
    """Restore an uploaded REE bundle from /ree/upload-staging/<upload_token>.bin.

    The bundle is a previously downloaded REE ZIP (sealed or draft). Loading it
    replaces the whole REE — intent, session, snapshot, overlay, artifacts,
    results, and author receipts — with what the bundle recorded.
    """

    model_config = ConfigDict(extra="forbid")

    upload_token: str = Field(description="The staged bundle's token.")
    archive_name: str = Field(description="The staged bundle's file name.")


class LoadReeBundleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["load_ree_bundle"] = "load_ree_bundle"
    args: LoadReeBundleArgs


class WriteScriptArgs(BaseModel):
    """Write content into /ree/overlay/<path> and mirror to /ree/workspace/<path>."""

    model_config = ConfigDict(extra="forbid")

    path: Annotated[str, POSITIONAL, Field(description="The script's path in the REE, or its KIND[:EXPERIMENT].")]
    content: Annotated[str, STDIN, Field(description="The script.")]
    # The handler verifies it against the current bytes right before writing, under the REE's lock, so the
    # compare-and-write is atomic.
    expected_etag: str = Field(
        default="",
        description="Write only if the script is still this digest (sha256:...), as `ree status` reports it.",
    )


class WriteScriptCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["write_script"] = "write_script"
    args: WriteScriptArgs


class PatchReeDefinitionArgs(BaseModel):
    """Apply a top-level patch to the portable REE definition."""

    model_config = ConfigDict(extra="forbid")

    patch: Annotated[dict[str, Any], STDIN, Field(description="The definition's top-level fields to replace, as JSON.")]
    # Checked immediately before the mutation, under the REE's lock, so the compare-and-write is atomic.
    expected_version: str = Field(
        default="", description="Change only if the REE is still at this revision, as `ree status` reports it."
    )


class PatchReeDefinitionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["patch_ree_definition"] = "patch_ree_definition"
    args: PatchReeDefinitionArgs


class RemoveSourceArgs(BaseModel):
    """Clear source content and reset source metadata in /ree/ree.json."""

    model_config = ConfigDict(extra="forbid")


class RemoveSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["remove_source"] = "remove_source"
    args: RemoveSourceArgs = RemoveSourceArgs()


class BuildExperimentEnvironmentArgs(BaseModel):
    """Build with the reserved, REE-owned build script, unless the build's evidence is current already."""

    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class BuildExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["build_experiment_environment"] = "build_experiment_environment"
    args: BuildExperimentEnvironmentArgs = BuildExperimentEnvironmentArgs()


class GenerateSbomArgs(BaseModel):
    """Scans the experiment environment the build recipe declares, unless its SBOM is current already."""

    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as to check a scanner's answer again.",
    )


class GenerateSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["generate_sbom"] = "generate_sbom"
    args: GenerateSbomArgs = GenerateSbomArgs()


class CrossCheckSbomArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CrossCheckSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    args: CrossCheckSbomArgs = CrossCheckSbomArgs()


class EvaluateReproducibilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = Field(default=False, description="Count an unpinned dependency as a failure.")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as after the analyzer itself changed.",
    )


class EvaluateReproducibilityCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["evaluate_reproducibility"] = "evaluate_reproducibility"
    args: EvaluateReproducibilityArgs = EvaluateReproducibilityArgs()


class RunExperimentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_name: Annotated[str, POSITIONAL, Field(description="The experiment, as the definition names it.")]
    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class RunExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["run_experiment"] = "run_experiment"
    args: RunExperimentArgs


class ObserveHardwareArgs(BaseModel):
    """No args — profiles the workbench container's hardware and writes to ree.json."""

    model_config = ConfigDict(extra="forbid")


class ObserveHardwareCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["observe_hardware"] = "observe_hardware"
    args: ObserveHardwareArgs = ObserveHardwareArgs()


class ActivateExperimentEnvironmentArgs(BaseModel):
    """Activation runs the REE's stored Activation through its experiment environment entry, unless its evidence is
    current already; there is no per-run script path."""

    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class ActivateExperimentEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["activate_experiment_environment"] = "activate_experiment_environment"
    args: ActivateExperimentEnvironmentArgs = ActivateExperimentEnvironmentArgs()


class CheckWorkingEnvironmentArgs(BaseModel):
    """Runs the REE's check script in its working environment, launched as every script is, unless it passed on this
    host already and its evidence is current."""

    model_config = ConfigDict(extra="forbid")

    again: bool = Field(
        default=False,
        description="Run it although its evidence is current, as for a fresh run of a stochastic experiment.",
    )


class CheckWorkingEnvironmentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["check_working_environment"] = "check_working_environment"
    args: CheckWorkingEnvironmentArgs = CheckWorkingEnvironmentArgs()


# The kinds of author-facing script inference can be asked about. Declared here,
# on the wire type, because all three layers that name it must agree by
# construction: the HTTP payload validating a client's request, this command
# crossing to the workbench, and core's inference models resolving it to a
# reserved path. Spelled once, adding a kind is one edit rather than three that
# nothing checks are in sync.
TargetKind = Literal[
    "build_experiment_environment",
    "activate_experiment_environment",
    "experiment_run",
    "experiment_verify",
    "launch",
    "check_working_environment",
]


class ScriptTargetSelectorArg(BaseModel):
    """One target a caller asks inference about: a kind, never a path.

    The workbench resolves the reserved path from the kind (and, for
    experiments, the reserved slug convention); a caller cannot redirect
    inference at an arbitrary workspace file.
    """

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None

    @model_validator(mode="after")
    def _named_only_for_experiments(self) -> ScriptTargetSelectorArg:
        if self.kind in ("experiment_run", "experiment_verify"):
            if not self.experiment_name:
                raise ValueError(f"{self.kind} requires an experiment_name")
        elif self.experiment_name:
            raise ValueError(f"{self.kind} must not carry an experiment_name")
        return self


class ScriptTarget(BaseModel):
    """A resolved executable target. ``path`` is output-only."""

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    experiment_name: str | None = None
    path: str


class SuggestScriptsArgs(BaseModel):
    """Read-only inference of author-facing shell scripts.

    Synchronous and always recomputed from the current upstream tree, intent,
    policy, and DAG version; it persists nothing and never writes. Writing a
    chosen candidate stays on the existing ``write_script`` path.
    """

    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorArg] = Field(description="The scripts to propose, each KIND[:EXPERIMENT].")


class SuggestScriptsCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["suggest_scripts"] = "suggest_scripts"
    args: SuggestScriptsArgs


class LintScriptsArgs(BaseModel):
    """Targets for read-only checks of persisted REE scripts."""

    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorArg] = Field(description="The scripts to check, each KIND[:EXPERIMENT].")


class LintScriptsCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["lint_scripts"] = "lint_scripts"
    args: LintScriptsArgs


class SealReeArgs(BaseModel):
    """What the sealed REE carries besides its scripts and evidence: by default everything it holds, so that a
    bundle reproduces offline; ``--no-source-included`` and the like leave a part out."""

    model_config = ConfigDict(extra="forbid")

    source_included: bool = Field(default=True, description="Carry the source snapshot.")
    experiment_environment_included: bool = Field(default=True, description="Carry the experiment environment.")
    results_included: bool = Field(default=True, description="Carry the experiments' results.")


class SealReeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["seal_ree"] = "seal_ree"
    args: SealReeArgs = SealReeArgs()


class SignReeArgs(BaseModel):
    """Add a Sigstore bundle, staged at /ree/upload-staging/<upload_token>.bin, as the sealed REE's signature
    under ``claim``: its statement must name the seal's digest under the claim's predicate type."""

    model_config = ConfigDict(extra="forbid")

    claim: SignatureClaim = Field(default="author_approval", description="What the signature claims.")
    upload_token: str = Field(description="The staged bundle's token.")
    archive_name: str = Field(description="The staged bundle's file name.")


class SignReeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["sign_ree"] = "sign_ree"
    args: SignReeArgs


class SignReviewArgs(BaseModel):
    """Add a Sigstore bundle, staged at /ree/upload-staging/<upload_token>.bin, as the review's signature: its
    statement must name the reviewed REE's seal, under the review predicate type, with the review's record as its
    predicate. Only a review of a sealed REE that is not running is signed, and a signed review changes no more."""

    model_config = ConfigDict(extra="forbid")

    review_id: Annotated[str, Field(description="The review to sign.")]
    upload_token: str = Field(description="The staged bundle's token.")
    archive_name: str = Field(description="The staged bundle's file name.")


class SignReviewCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["sign_review"] = "sign_review"
    args: SignReviewArgs


# Tagged union discriminated on 'operation'.
Command = Annotated[
    ReviewAcquireSourceCommand
    | ReviewBuildExperimentEnvironmentCommand
    | ReviewActivateExperimentEnvironmentCommand
    | ReviewRunExperimentCommand
    | MaterializeWorkspaceCommand
    | AcquireSourceCommand
    | LoadReeBundleCommand
    | WriteScriptCommand
    | PatchReeDefinitionCommand
    | RemoveSourceCommand
    | BuildExperimentEnvironmentCommand
    | GenerateSbomCommand
    | CrossCheckSbomCommand
    | EvaluateReproducibilityCommand
    | RunExperimentCommand
    | ObserveHardwareCommand
    | ActivateExperimentEnvironmentCommand
    | CheckWorkingEnvironmentCommand
    | SuggestScriptsCommand
    | LintScriptsCommand
    | SealReeCommand
    | SignReeCommand
    | SignReviewCommand,
    Field(discriminator="operation"),
]

command_adapter: TypeAdapter[Command] = TypeAdapter(Command)
