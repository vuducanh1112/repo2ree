"""The reproduction commands the executor CLI shares with a bundle's run.sh, their words and one-line summaries.

Each is an operation of the catalogue, spelled as the CLI spells it: its name in kebab case. run.sh adds only
helpers that run no operation of their own (``all``, ``list``, ``verify``).

Leaf module: it imports nothing from ``repo2ree_core``, so the run.sh generator and the CLI can both depend on it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReproductionCommand:
    operation: str
    summary: str

    @property
    def name(self) -> str:
        return self.operation.replace("_", "-")


ACQUIRE_SOURCE = ReproductionCommand(
    "acquire_source",
    "Acquire the source, verifying it against the recorded SWHID",
)
MATERIALIZE_WORKSPACE = ReproductionCommand(
    "materialize_workspace",
    "Assemble a clean workspace from the source and the REE overlay",
)
CHECK_WORKING_ENVIRONMENT = ReproductionCommand(
    "check_working_environment",
    "Run the author's check that this machine offers what the scripts need",
)
BUILD_EXPERIMENT_ENVIRONMENT = ReproductionCommand(
    "build_experiment_environment",
    "Build the experiment environment from the REE build script",
)
ACTIVATE_EXPERIMENT_ENVIRONMENT = ReproductionCommand(
    "activate_experiment_environment",
    "Run the activation alone: it enters the experiment environment and hands over",
)
RUN_EXPERIMENT = ReproductionCommand(
    "run_experiment",
    "Run a named experiment and verify its result",
)

REPRODUCTION_COMMANDS: tuple[ReproductionCommand, ...] = (
    ACQUIRE_SOURCE,
    MATERIALIZE_WORKSPACE,
    CHECK_WORKING_ENVIRONMENT,
    BUILD_EXPERIMENT_ENVIRONMENT,
    ACTIVATE_EXPERIMENT_ENVIRONMENT,
    RUN_EXPERIMENT,
)
