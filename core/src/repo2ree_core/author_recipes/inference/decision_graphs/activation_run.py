"""The Phase 1 activation-run decision DAG.

Resolve the logical project root, then the shared runtime-contract + command
subgraph. Phase 1 has no author-facing activation-command declaration, so a
resolved experiment environment always yields a confirmation-required candidate (the fail-closed
scaffold), never an automatic activation.
"""

from __future__ import annotations

from repo2ree_core.author_recipes.inference.decision_graphs._experiment_environment_contract import (
    ENTRY,
    experiment_environment_contract_and_command_nodes,
)
from repo2ree_protocol.inference import CheckNode, DecisionDag

ACTIVATION_RUN_DAG = DecisionDag(
    key="activation-run-inference",
    version=1,
    root="project-root",
    nodes=[
        CheckNode(
            id="project-root",
            check="logical_project_root",
            branches={"root": ENTRY, "wrapper": ENTRY},
        ),
        *experiment_environment_contract_and_command_nodes(
            docker_rule="docker-runtime-activation-v1",
            docker_render="docker_activation_v1",
            venv_rule="venv-runtime-activation-v1",
            venv_render="venv_activation_v1",
        ),
    ],
)
