"""The Phase 1 activation-run decision DAG.

Resolve the logical project root, then the shared runtime-contract + command
subgraph. Phase 1 has no author-facing activation-command declaration, so a
resolved runtime always yields a confirmation-required candidate (the fail-closed
scaffold), never an automatic activation.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.decision_graphs._runtime_contract import (
    ENTRY,
    runtime_contract_and_command_nodes,
)
from repo2ree_core.authoring.script_inference.models import CheckNode, DecisionDag

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
        *runtime_contract_and_command_nodes(
            docker_rule="docker-runtime-activation-v1",
            docker_render="docker_activation_v1",
            venv_rule="venv-runtime-activation-v1",
            venv_render="venv_activation_v1",
        ),
    ],
)
