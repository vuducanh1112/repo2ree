"""The reproduction commands shared by the executor CLI and the bundle run.sh.

These are the phases of reproducing an REE — acquire the source, assemble a
clean workspace, build the runtime, test activation, run experiments. They are
the single source of truth for the run vocabulary so ``repo2ree --help`` and
``sh run.sh --help`` expose the same verbs and one-line summaries and cannot
drift.

The executor CLI is a superset: it also exposes *authoring* commands (seal,
write-file, patch-ree-definition, …) that are not reproduction commands and live
outside this registry. The bundle ``run.sh`` exposes exactly these verbs plus a
couple of orchestration helpers (``all``, ``list``).

Leaf module: it imports nothing from ``repo2ree_core`` so both the run.sh
generator (``ree_scripts.reproducer``) and the executor CLI can depend on it
without an import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReproductionCommand:
    """A verb shared by the executor CLI and the bundle reproducer.

    ``name`` is the subcommand token on both surfaces; ``summary`` is the
    one-line help rendered verbatim in both ``--help`` outputs.
    """

    name: str
    summary: str


# Ordered by lifecycle phase: acquire -> assemble -> build -> activate -> run.
ACQUIRE_SOURCE = ReproductionCommand(
    "acquire-source",
    "Acquire the source, verifying it against the recorded SWHID",
)
MATERIALIZE_WORKSPACE = ReproductionCommand(
    "materialize-workspace",
    "Assemble a clean workspace from the source and the REE overlay",
)
BUILD_RUNTIME = ReproductionCommand(
    "build-runtime",
    "Build the runtime from the REE build script",
)
TEST_ACTIVATION = ReproductionCommand(
    "test-activation",
    "Run activation to prove the runtime is inhabitable",
)
EXPERIMENT = ReproductionCommand(
    "experiment",
    "Run a named experiment and verify its result",
)

REPRODUCTION_COMMANDS: tuple[ReproductionCommand, ...] = (
    ACQUIRE_SOURCE,
    MATERIALIZE_WORKSPACE,
    BUILD_RUNTIME,
    TEST_ACTIVATION,
    EXPERIMENT,
)
