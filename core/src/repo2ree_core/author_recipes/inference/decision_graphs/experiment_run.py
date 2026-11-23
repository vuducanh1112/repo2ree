from __future__ import annotations

from repo2ree_core.author_recipes.inference.decision_graphs._experiment_environment_contract import (
    ENTRY,
    NOT_INFERRED,
    experiment_environment_contract_and_command_nodes,
)
from repo2ree_protocol.inference import CheckNode, DecisionDag

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
        *experiment_environment_contract_and_command_nodes(
            docker_rule="docker-runtime-experiment-v1",
            docker_render="docker_experiment_v1",
            venv_rule="venv-runtime-experiment-v1",
            venv_render="venv_experiment_v1",
        ),
    ],
)
