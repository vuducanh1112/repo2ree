"""Registries of checks, resolvers, renderers, and decision DAGs.

The registry is the deployment surface: adding an ecosystem means registering
its checks and renderer and attaching a versioned strategy branch to a DAG here.
Every registered DAG is validated at import time, so a structurally broken graph
fails the process at startup rather than at request time.
"""

from __future__ import annotations

from repo2ree_core.author_recipes.inference.build_wiring import BUILD_CHECKS, BUILD_RENDERERS, BUILD_RESOLVERS
from repo2ree_core.author_recipes.inference.checks.docker_config import DockerConfigCommandsCheck
from repo2ree_core.author_recipes.inference.checks.experiment import RequestedExperimentCheck
from repo2ree_core.author_recipes.inference.checks.runtime_contract import (
    DeclaredRuntimePathCheck,
    RuntimeArtifactInspectionCheck,
    RuntimeArtifactStateCheck,
    RuntimeContractKindCheck,
    UnchangedGeneratedBuildCheck,
)
from repo2ree_core.author_recipes.inference.decision_graphs.activation_run import ACTIVATION_RUN_DAG
from repo2ree_core.author_recipes.inference.decision_graphs.build import BUILD_INFERENCE_DAG
from repo2ree_core.author_recipes.inference.decision_graphs.experiment_run import EXPERIMENT_RUN_DAG
from repo2ree_core.author_recipes.inference.engine import validate_dag
from repo2ree_core.author_recipes.inference.models import Check, DecisionDag, Renderer, Resolver
from repo2ree_core.author_recipes.inference.renderers.docker_activation import DockerActivationRenderer
from repo2ree_core.author_recipes.inference.renderers.docker_experiment import DockerExperimentRenderer
from repo2ree_core.author_recipes.inference.renderers.venv_activation import VenvActivationRenderer
from repo2ree_core.author_recipes.inference.renderers.venv_experiment import VenvExperimentRenderer

# The build wiring is shared with ``build_regeneration`` (see ``build_wiring``) so
# the two can never drift; the run-side checks/renderers are layered on top here.
CHECKS: dict[str, Check] = {
    **BUILD_CHECKS,
    **{
        check.code: check
        for check in (
            DeclaredRuntimePathCheck(),
            RuntimeArtifactStateCheck(),
            RuntimeArtifactInspectionCheck(),
            UnchangedGeneratedBuildCheck(),
            RuntimeContractKindCheck(),
            DockerConfigCommandsCheck(),
            RequestedExperimentCheck(),
        )
    },
}

RESOLVERS: dict[str, Resolver] = dict(BUILD_RESOLVERS)

RENDERERS: dict[str, Renderer] = {
    **BUILD_RENDERERS,
    **{
        renderer.code: renderer
        for renderer in (
            DockerActivationRenderer(),
            VenvActivationRenderer(),
            DockerExperimentRenderer(),
            VenvExperimentRenderer(),
        )
    },
}

DECISION_DAGS: dict[str, DecisionDag] = {
    BUILD_INFERENCE_DAG.key: BUILD_INFERENCE_DAG,
    ACTIVATION_RUN_DAG.key: ACTIVATION_RUN_DAG,
    EXPERIMENT_RUN_DAG.key: EXPERIMENT_RUN_DAG,
}

# Which DAG serves each target kind. Verify targets are deferred (they need an
# explicit author verification claim that has no field on ReeDefinition yet), so
# they stay unregistered and return a well-formed not_inferred result.
DAG_FOR_TARGET_KIND: dict[str, str] = {
    "build": BUILD_INFERENCE_DAG.key,
    "activation_run": ACTIVATION_RUN_DAG.key,
    "experiment_run": EXPERIMENT_RUN_DAG.key,
}


def validate_all() -> None:
    for dag in DECISION_DAGS.values():
        validate_dag(dag, checks=CHECKS, resolvers=RESOLVERS, renderers=RENDERERS)


# Fail fast at import: a broken DAG is a deployment defect, not a runtime error.
validate_all()
