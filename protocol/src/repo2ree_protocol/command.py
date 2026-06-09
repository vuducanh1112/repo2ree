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

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class AcquireSourceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_url: str
    source_type: Literal["git", "tarball", "zip"]
    dest: Path


class AcquireSourceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["acquire_source"] = "acquire_source"
    args: AcquireSourceArgs


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
    resolved_commit: str = ""
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


class WriteFileCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["write_file"] = "write_file"
    args: WriteFileArgs


class DeleteFileArgs(BaseModel):
    """Remove <path> from /ree/overlay/ and restore from upstream or remove from workspace."""

    model_config = ConfigDict(extra="forbid")

    path: str


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


class BuildRuntimeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_runtime_script_path: str


class BuildRuntimeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["build_runtime"] = "build_runtime"
    args: BuildRuntimeArgs


class GenerateSbomArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produced_runtime_path: str


class GenerateSbomCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["generate_sbom"] = "generate_sbom"
    args: GenerateSbomArgs


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
    mode: Literal["verify", "snapshot"] = "verify"


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
    model_config = ConfigDict(extra="forbid")

    activation_script_path: str


class ActivationTestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["activation_test"] = "activation_test"
    args: ActivationTestArgs


class SealReeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_included: bool = False
    runtime_included: bool = False


class SealReeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["seal_ree"] = "seal_ree"
    args: SealReeArgs = SealReeArgs()


# Tagged union discriminated on 'operation'.
Command = Annotated[
    AcquireSourceCommand
    | SnapshotUpstreamCommand
    | MaterializeWorkspaceCommand
    | UpdateSourceMetadataCommand
    | ExtractUploadCommand
    | WriteFileCommand
    | DeleteFileCommand
    | PatchReeIntentCommand
    | RemoveSourceCommand
    | BuildRuntimeCommand
    | GenerateSbomCommand
    | EvaluateDependencyScoreCommand
    | RunExperimentCommand
    | GenerateHbomCommand
    | ActivationTestCommand
    | SealReeCommand,
    Field(discriminator="operation"),
]

command_adapter: TypeAdapter[Command] = TypeAdapter(Command)
