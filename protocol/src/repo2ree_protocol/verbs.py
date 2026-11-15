"""Every command as the words a caller runs: a ``ree`` verb, its arguments, and its stdin.

The command line is the one interface into an REE, for a person at a terminal as much as for a workbench, so a
``Command`` and its argv are two spellings of one value. ``to_argv`` writes the argv a caller runs and
``from_argv`` reads it back; both follow from the command models (``repo2ree_protocol.argv``), so
``from_argv(*to_argv(cmd)) == cmd`` for every command, and the spellings cannot drift apart.

The steps an REE's reproduction shares with its bundle's ``run.sh`` keep the names they have there
(``materialize-workspace``, ``build-experiment-environment``, ``test-activation``, ``experiment``).
"""

from __future__ import annotations

from typing import cast, get_args

from pydantic import BaseModel

from repo2ree_protocol.argv import ArgvError, decode_args, encode_args
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    ActivationTestCommand,
    BuildExperimentEnvironmentCommand,
    CheckWorkingEnvironmentCommand,
    Command,
    CrossCheckSbomCommand,
    DeleteFileCommand,
    EvaluateDependencyScoreCommand,
    GenerateHbomCommand,
    GenerateSbomCommand,
    GenerateScriptCandidatesCommand,
    LintScriptsCommand,
    LoadReeBundleCommand,
    MaterializeWorkspaceCommand,
    PatchReeDefinitionCommand,
    RemoveSourceCommand,
    ReviewAcquireSourceCommand,
    ReviewActivationTestCommand,
    ReviewBuildExperimentEnvironmentCommand,
    ReviewRunExperimentCommand,
    RunExperimentCommand,
    SealReeCommand,
    WriteFileCommand,
)

REVIEW = "review"

VERBS: dict[type[BaseModel], tuple[str, ...]] = {
    AcquireSourceCommand: ("acquire-source",),
    RemoveSourceCommand: ("remove-source",),
    LoadReeBundleCommand: ("load-bundle",),
    GenerateScriptCandidatesCommand: ("infer",),
    LintScriptsCommand: ("lint",),
    WriteFileCommand: ("write",),
    DeleteFileCommand: ("rm",),
    PatchReeDefinitionCommand: ("define",),
    MaterializeWorkspaceCommand: ("materialize-workspace",),
    CheckWorkingEnvironmentCommand: ("check-working-environment",),
    BuildExperimentEnvironmentCommand: ("build-experiment-environment",),
    ActivationTestCommand: ("test-activation",),
    RunExperimentCommand: ("experiment",),
    GenerateSbomCommand: ("sbom",),
    CrossCheckSbomCommand: ("sbom-check",),
    EvaluateDependencyScoreCommand: ("evaluate",),
    GenerateHbomCommand: ("hbom",),
    SealReeCommand: ("seal",),
    ReviewAcquireSourceCommand: (REVIEW, "acquire-source"),
    ReviewBuildExperimentEnvironmentCommand: (REVIEW, "build-experiment-environment"),
    ReviewActivationTestCommand: (REVIEW, "test-activation"),
    ReviewRunExperimentCommand: (REVIEW, "experiment"),
}

# What each command does, in a line of its help. The steps shared with run.sh say what they say there.
SUMMARIES: dict[type[BaseModel], str] = {
    AcquireSourceCommand: "Acquire the REE's source from an origin (--origin-url) or an archive (--archive)",
    RemoveSourceCommand: "Remove the REE's source, keeping its scripts and definition",
    LoadReeBundleCommand: "Replace the REE with a bundle (--archive), sealed or draft",
    GenerateScriptCandidatesCommand: "Propose scripts for the REE from its source and this machine",
    LintScriptsCommand: "Check the REE's scripts",
    WriteFileCommand: "Write one of the REE's scripts from stdin",
    DeleteFileCommand: "Delete one of the REE's scripts",
    PatchReeDefinitionCommand: "Change the REE's definition by a JSON patch on stdin",
    MaterializeWorkspaceCommand: "Assemble a clean workspace from the source and the REE overlay",
    CheckWorkingEnvironmentCommand: "Run the REE's check script in its working environment",
    BuildExperimentEnvironmentCommand: "Build the experiment environment from the REE build script",
    ActivationTestCommand: "Run the activation alone: it enters the experiment environment and hands over",
    RunExperimentCommand: "Run a named experiment and verify its result",
    GenerateSbomCommand: "List the software in the experiment environment (SBOM)",
    CrossCheckSbomCommand: "Check the SBOM against the dependencies the source declares",
    EvaluateDependencyScoreCommand: "Score how fully the source pins its dependencies",
    GenerateHbomCommand: "Record the hardware this machine offers (HBOM)",
    SealReeCommand: "Seal the REE: freeze it and its evidence under one digest",
    ReviewAcquireSourceCommand: "Open a review: acquire the source into an attempt of its own",
    ReviewBuildExperimentEnvironmentCommand: "Rebuild the experiment environment in the review, or certify the REE's",
    ReviewActivationTestCommand: "Test the activation in the review",
    ReviewRunExperimentCommand: "Reproduce one experiment in the review and compare it with the author's",
}

COMMANDS: dict[tuple[str, ...], type[BaseModel]] = {verb: command for command, verb in VERBS.items()}


def command_types() -> tuple[type[BaseModel], ...]:
    """Every member of the ``Command`` union."""
    return get_args(get_args(Command)[0])


def to_argv(cmd: Command) -> tuple[list[str], bytes | None]:
    """The argv after ``ree`` that runs ``cmd``, and what it reads on stdin."""
    words, stdin = encode_args(cmd.args)
    return [*VERBS[type(cmd)], *words], stdin


def from_argv(argv: list[str], stdin: bytes | None = None) -> Command:
    """The command an argv after ``ree`` spells, reading ``stdin`` for the field that is read from it."""
    for length in (2, 1):
        command = COMMANDS.get(tuple(argv[:length]))
        if command is not None:
            args_model = cast(type[BaseModel], command.model_fields["args"].annotation)
            args = decode_args(args_model, argv[length:], stdin)
            return command.model_validate({"args": args})  # type: ignore[return-value]
    raise ArgvError(f"no command {' '.join(argv[:2])!r}")
