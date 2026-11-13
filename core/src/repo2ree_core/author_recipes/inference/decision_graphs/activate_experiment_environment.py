"""The activate experiment environment decision DAG: the shared experiment environment contract subgraph."""

from __future__ import annotations

from repo2ree_core.author_recipes.inference.decision_graphs._experiment_environment_contract import (
    ENTRY,
    experiment_environment_contract_and_command_nodes,
)
from repo2ree_protocol.inference import CheckNode, DecisionDag

ACTIVATE_EXPERIMENT_ENVIRONMENT_DAG = DecisionDag(
    key="activate-experiment-environment-inference",
    version=1,
    root="project-root",
    nodes=[
        CheckNode(
            id="project-root",
            check="logical_project_root",
            branches={"root": ENTRY, "wrapper": ENTRY},
        ),
        *experiment_environment_contract_and_command_nodes(
            docker_rule="docker-activate-experiment-environment-v1",
            docker_render="docker_activate_experiment_environment_v1",
            venv_rule="venv-activate-experiment-environment-v1",
            venv_render="venv_activate_experiment_environment_v1",
            podman=("podman-activate-experiment-environment", "podman_activate_experiment_environment"),
        ),
    ],
)
