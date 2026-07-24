"""Typed command envelope for repo2ree operations.

The Command union is the wire form between the control plane (api) and the
execution plane (in-container CLI). Each variant carries fully-typed args
for one operation. The discriminator field ``operation`` is the stable
identifier; argv subcommands are sugar that construct the same types.

Add new operations by:
  1. Defining a new ``*Args`` + ``*Command`` pair below.
  2. Extending the ``Command`` union annotation.
  3. Adding a branch in ``run_command``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class AcquireSourceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Origin/type are absent for an upload-acquired source: it has no origin and
    # is populated from the snapshot the upload ingest produced.
    origin_url: str = ""
    source_type: Literal["git", "tarball", "zip"] | None = None
    # The git ref to fetch: a user-supplied commit, branch, or tag during
    # authoring; the resolved concrete commit once acquisition has settled it and
    # a re-fetch is being pinned (e.g. in a sealed bundle). Empty means the
    # origin's default branch HEAD; the resolved commit is recorded afterward
    # either way. See ``ReeIntent.revision`` for the same value once persisted.
    revision: str = ""
    # Force a fresh pull from origin even when a snapshot is present (origin
    # sources only; an upload has nothing to re-fetch).
    refetch: bool = False


class AcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["acquire_source"] = "acquire_source"
    args: AcquireSourceArgs


class ReviewAcquireSourceArgs(BaseModel):
    """Acquire the author-pinned source into one isolated review attempt."""

    model_config = ConfigDict(extra="forbid")

    review_id: str


class ReviewAcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["review_acquire_source"] = "review_acquire_source"
    args: ReviewAcquireSourceArgs


class SnapshotUpstreamArgs(BaseModel):
    """No args — operates on /ree/upstream → /ree/snapshot.tar.gz."""

    model_config = ConfigDict(extra="forbid")


class SnapshotUpstreamCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["snapshot_upstream"] = "snapshot_upstream"
    args: SnapshotUpstreamArgs = SnapshotUpstreamArgs()


class MaterializeWorkspaceArgs(BaseModel):
    """No args — merges /ree/upstream + /ree/overlay into /ree/workspace."""

    model_config = ConfigDict(extra="forbid")


class MaterializeWorkspaceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["materialize_workspace"] = "materialize_workspace"
    args: MaterializeWorkspaceArgs = MaterializeWorkspaceArgs()


class UpdateSourceMetadataArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["download", "upload"] = "download"
    # download fields
    origin_url: str = ""
    source_type: str = ""
    # upload fields
    archive_name: str = ""
    upload_token: str = ""


class UpdateSourceMetadataCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["update_source_metadata"] = "update_source_metadata"
    args: UpdateSourceMetadataArgs


class ExtractUploadArgs(BaseModel):
    """Extract /ree/upload-staging/<upload_token>.bin into /ree/upstream/."""

    model_config = ConfigDict(extra="forbid")

    upload_token: str
    archive_name: str


class ExtractUploadCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["extract_upload"] = "extract_upload"
    args: ExtractUploadArgs


class WriteFileArgs(BaseModel):
    """Write content into /ree/overlay/<path> and mirror to /ree/workspace/<path>."""

    model_config = ConfigDict(extra="forbid")

    path: str
    content: str
    # Optimistic-concurrency guard: "sha256:<hex>" of the workspace file the
    # caller last read. The handler verifies it against the current bytes right
    # before writing — inside the per-REE dispatch serialization — so the
    # compare-and-write is atomic. Empty/omitted skips the check.
    expected_etag: str = ""


class WriteFileCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["write_file"] = "write_file"
    args: WriteFileArgs


class DeleteFileArgs(BaseModel):
    """Remove <path> from /ree/overlay/ and restore from upstream or remove from workspace."""

    model_config = ConfigDict(extra="forbid")

    path: str
    # Same optimistic-concurrency guard as WriteFileArgs.expected_etag.
    expected_etag: str = ""


class DeleteFileCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["delete_file"] = "delete_file"
    args: DeleteFileArgs


class PatchReeIntentArgs(BaseModel):
    """Apply a partial patch to reeIntent in /ree/.workspace.json."""

    model_config = ConfigDict(extra="forbid")

    patch: dict[str, Any]


class PatchReeIntentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["patch_ree_intent"] = "patch_ree_intent"
    args: PatchReeIntentArgs


class RemoveSourceArgs(BaseModel):
    """Clear source content and reset source metadata in /ree/.workspace.json."""

    model_config = ConfigDict(extra="forbid")


class RemoveSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["remove_source"] = "remove_source"
    args: RemoveSourceArgs = RemoveSourceArgs()


class ResetForSourceChangeArgs(BaseModel):
    """Clear source-derived state before acquiring a replacement source."""

    model_config = ConfigDict(extra="forbid")


class ResetForSourceChangeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["reset_for_source_change"] = "reset_for_source_change"
    args: ResetForSourceChangeArgs = ResetForSourceChangeArgs()


class BuildRuntimeArgs(BaseModel):
    """No args — the build always runs the reserved, REE-owned build script."""

    model_config = ConfigDict(extra="forbid")


class BuildRuntimeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["build_runtime"] = "build_runtime"
    args: BuildRuntimeArgs = BuildRuntimeArgs()


class GenerateSbomArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produced_runtime_path: str


class GenerateSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["generate_sbom"] = "generate_sbom"
    args: GenerateSbomArgs


class CrossCheckSbomArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CrossCheckSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["cross_check_sbom"] = "cross_check_sbom"
    args: CrossCheckSbomArgs = CrossCheckSbomArgs()


class EvaluateDependencyScoreArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strict: bool = False


class EvaluateDependencyScoreCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["evaluate_dependency_score"] = "evaluate_dependency_score"
    args: EvaluateDependencyScoreArgs = EvaluateDependencyScoreArgs()


class RunExperimentArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_name: str


class RunExperimentCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["run_experiment"] = "run_experiment"
    args: RunExperimentArgs


class GenerateHbomArgs(BaseModel):
    """No args — profiles the workbench container's hardware and writes to .workspace.json."""

    model_config = ConfigDict(extra="forbid")


class GenerateHbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["generate_hbom"] = "generate_hbom"
    args: GenerateHbomArgs = GenerateHbomArgs()


class ActivationTestArgs(BaseModel):
    """No args — activation runs the REE's stored Activation through its
    runtime entry; there is no per-run script path."""

    model_config = ConfigDict(extra="forbid")


class ActivationTestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["activation_test"] = "activation_test"
    args: ActivationTestArgs = ActivationTestArgs()


class ScriptTargetSelectorArg(BaseModel):
    """One target a caller asks inference about: a kind, never a path.

    The workbench resolves the reserved path from the kind (and, for
    experiments, the reserved slug convention); a caller cannot redirect
    inference at an arbitrary workspace file.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "build",
        "activation_run",
        "activation_verify",
        "experiment_run",
        "experiment_verify",
    ]
    experiment_name: str | None = None


class GenerateScriptCandidatesArgs(BaseModel):
    """Read-only inference of author-facing shell scripts.

    Synchronous and always recomputed from the current upstream tree, intent,
    policy, and DAG version; it persists nothing and never writes. Writing a
    chosen candidate stays on the existing ``write_file`` path.
    """

    model_config = ConfigDict(extra="forbid")

    targets: list[ScriptTargetSelectorArg]


class GenerateScriptCandidatesCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["generate_script_candidates"] = "generate_script_candidates"
    args: GenerateScriptCandidatesArgs


class SealReeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_included: bool = False
    runtime_included: bool = False
    results_included: bool = False


class SealReeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["seal_ree"] = "seal_ree"
    args: SealReeArgs = SealReeArgs()


# Tagged union discriminated on 'operation'.
Command = Annotated[
    AcquireSourceCommand
    | ReviewAcquireSourceCommand
    | SnapshotUpstreamCommand
    | MaterializeWorkspaceCommand
    | UpdateSourceMetadataCommand
    | ExtractUploadCommand
    | WriteFileCommand
    | DeleteFileCommand
    | PatchReeIntentCommand
    | RemoveSourceCommand
    | ResetForSourceChangeCommand
    | BuildRuntimeCommand
    | GenerateSbomCommand
    | CrossCheckSbomCommand
    | EvaluateDependencyScoreCommand
    | RunExperimentCommand
    | GenerateHbomCommand
    | ActivationTestCommand
    | GenerateScriptCandidatesCommand
    | SealReeCommand,
    Field(discriminator="operation"),
]

command_adapter: TypeAdapter[Command] = TypeAdapter(Command)
