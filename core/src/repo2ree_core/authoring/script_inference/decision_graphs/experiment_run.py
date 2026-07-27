"""The Phase 1 experiment-run decision DAG.

Gate on the requested experiment being declared on the REE, then resolve the
project root and the shared runtime-contract + command subgraph. Phase 1 does
not yet recognize a machine-readable reproduction-command format, so a resolved
runtime yields a confirmation-required scaffold candidate, never an automatic
complete. An undeclared experiment short-circuits straight to not_inferred.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.decision_graphs._runtime_contract import (
    ENTRY,
    NOT_INFERRED,
    runtime_contract_and_command_nodes,
)
from repo2ree_core.authoring.script_inference.models import CheckNode, DecisionDag

EXPERIMENT_RUN_DAG = DecisionDag(
    key="experiment-run-inference",
    version=1,
    root="requested-experiment",
    nodes=[
        CheckNode(
            id="requested-experiment",
            check="requested_experiment",
            branches={"absent": NOT_INFERRED, "found": "project-root"},
        ),
        CheckNode(
            id="project-root",
            check="logical_project_root",
            branches={"root": ENTRY, "wrapper": ENTRY},
        ),
        *runtime_contract_and_command_nodes(
            docker_rule="docker-runtime-experiment-v1",
            docker_render="docker_experiment_v1",
            venv_rule="venv-runtime-experiment-v1",
            venv_render="venv_experiment_v1",
        ),
    ],
)
