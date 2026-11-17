"""Every command as the words a caller runs: a ``ree`` verb, its arguments, and its stdin.

The command line is the one interface into an REE, for a person at a terminal as much as for a workbench, so a
``Command`` and its argv are two spellings of one value. ``to_argv`` writes the argv a caller runs; ``ree`` reads it
back with options generated from the same command models (``repo2ree_cli.options``), so the spellings cannot drift.

The steps an REE's reproduction shares with its bundle's ``run.sh`` keep the names they have there
(``materialize-workspace``, ``build-experiment-environment``, ``test-activation``, ``experiment``).
"""

from __future__ import annotations

from typing import get_args

from pydantic import BaseModel

from repo2ree_protocol.argv import encode_args
from repo2ree_protocol.command import (
    AcquireSourceCommand,
    ActivateExperimentEnvironmentCommand,
    BuildExperimentEnvironmentCommand,
    CheckWorkingEnvironmentCommand,
    Command,
    CrossCheckSbomCommand,
    EvaluateReproducibilityCommand,
    GenerateSbomCommand,
    LintScriptsCommand,
    LoadReeBundleCommand,
    MaterializeWorkspaceCommand,
    ObserveHardwareCommand,
    PatchReeDefinitionCommand,
    RemoveSourceCommand,
    ReviewAcquireSourceCommand,
    ReviewActivateExperimentEnvironmentCommand,
    ReviewBuildExperimentEnvironmentCommand,
    ReviewRunExperimentCommand,
    RunExperimentCommand,
    SealReeCommand,
    SuggestScriptsCommand,
    WriteScriptCommand,
)

REVIEW = "review"

VERBS: dict[type[BaseModel], tuple[str, ...]] = {
    AcquireSourceCommand: ("acquire-source",),
    RemoveSourceCommand: ("remove-source",),
    LoadReeBundleCommand: ("load-bundle",),
    SuggestScriptsCommand: ("infer",),
    LintScriptsCommand: ("lint",),
    WriteScriptCommand: ("write",),
    PatchReeDefinitionCommand: ("define",),
    MaterializeWorkspaceCommand: ("materialize-workspace",),
    CheckWorkingEnvironmentCommand: ("check-working-environment",),
    BuildExperimentEnvironmentCommand: ("build-experiment-environment",),
    ActivateExperimentEnvironmentCommand: ("test-activation",),
    RunExperimentCommand: ("experiment",),
    GenerateSbomCommand: ("sbom",),
    CrossCheckSbomCommand: ("sbom-check",),
    EvaluateReproducibilityCommand: ("evaluate",),
    ObserveHardwareCommand: ("hbom",),
    SealReeCommand: ("seal",),
    ReviewAcquireSourceCommand: (REVIEW, "acquire-source"),
    ReviewBuildExperimentEnvironmentCommand: (REVIEW, "build-experiment-environment"),
    ReviewActivateExperimentEnvironmentCommand: (REVIEW, "test-activation"),
    ReviewRunExperimentCommand: (REVIEW, "experiment"),
}

# What each command does, in a line of its help. The steps shared with run.sh say what they say there.
SUMMARIES: dict[type[BaseModel], str] = {
    AcquireSourceCommand: "Acquire the REE's source from an origin (--origin-url) or an archive (--archive)",
    RemoveSourceCommand: "Remove the REE's source, keeping its scripts and definition",
    LoadReeBundleCommand: "Replace the REE with a bundle (--archive), sealed or draft",
    SuggestScriptsCommand: "Propose scripts for the REE from its source and this machine",
    LintScriptsCommand: "Check the REE's scripts",
    WriteScriptCommand: "Write one of the REE's scripts from stdin",
    PatchReeDefinitionCommand: "Declare the REE's name, catalog entry, experiment environment and experiments",
    MaterializeWorkspaceCommand: "Assemble a clean workspace from the source and the REE overlay",
    CheckWorkingEnvironmentCommand: "Run the REE's check script in its working environment",
    BuildExperimentEnvironmentCommand: "Build the experiment environment from the REE build script",
    ActivateExperimentEnvironmentCommand: (
        "Run the activation alone: it enters the experiment environment and hands over"
    ),
    RunExperimentCommand: "Run a named experiment and verify its result",
    GenerateSbomCommand: "List the software in the experiment environment (SBOM)",
    CrossCheckSbomCommand: "Check the SBOM against the dependencies the source declares",
    EvaluateReproducibilityCommand: "Score how fully the source pins its dependencies",
    ObserveHardwareCommand: "Record the hardware this machine offers (HBOM)",
    SealReeCommand: "Seal the REE: freeze it and its evidence under one digest",
    ReviewAcquireSourceCommand: "Open a review: acquire the source into an attempt of its own",
    ReviewBuildExperimentEnvironmentCommand: "Rebuild the experiment environment in the review, or certify the REE's",
    ReviewActivateExperimentEnvironmentCommand: "Test the activation in the review",
    ReviewRunExperimentCommand: "Reproduce one experiment in the review and compare it with the author's",
}


def command_types() -> tuple[type[BaseModel], ...]:
    """Every member of the ``Command`` union."""
    return get_args(get_args(Command)[0])


def to_argv(cmd: Command) -> tuple[list[str], bytes | None]:
    """The argv after ``ree`` that runs ``cmd``, and what it reads on stdin."""
    words, stdin = encode_args(cmd.args)
    return [*VERBS[type(cmd)], *words], stdin
