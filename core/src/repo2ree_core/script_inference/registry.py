"""Registries of checks, resolvers, renderers, and decision DAGs.

The registry is the deployment surface: adding an ecosystem means registering
its checks and renderer and attaching a versioned strategy branch to a DAG here.
Every registered DAG is validated at import time, so a structurally broken graph
fails the process at startup rather than at request time.
"""

from __future__ import annotations

from repo2ree_core.script_inference.checks.docker_config import DockerConfigCommandsCheck
from repo2ree_core.script_inference.checks.dockerfile import (
    DockerfilesAtProjectRootCheck,
    NestedDockerfilesCheck,
)
from repo2ree_core.script_inference.checks.experiment import RequestedExperimentCheck
from repo2ree_core.script_inference.checks.project_root import LogicalProjectRootCheck
from repo2ree_core.script_inference.checks.python import RequirementsAtProjectRootCheck
from repo2ree_core.script_inference.checks.runtime_contract import (
    DeclaredRuntimePathCheck,
    RuntimeArtifactInspectionCheck,
    RuntimeArtifactStateCheck,
    RuntimeContractKindCheck,
    UnchangedGeneratedBuildCheck,
)
from repo2ree_core.script_inference.decision_graphs.activation_run import ACTIVATION_RUN_DAG
from repo2ree_core.script_inference.decision_graphs.build import BUILD_INFERENCE_DAG
from repo2ree_core.script_inference.decision_graphs.experiment_run import EXPERIMENT_RUN_DAG
from repo2ree_core.script_inference.engine import validate_dag
from repo2ree_core.script_inference.models import Check, DecisionDag, Renderer, Resolver
from repo2ree_core.script_inference.renderers.docker_activation import DockerActivationRenderer
from repo2ree_core.script_inference.renderers.docker_experiment import DockerExperimentRenderer
from repo2ree_core.script_inference.renderers.docker_runtime import DockerBuildRenderer
from repo2ree_core.script_inference.renderers.python_runtime import PipVenvBuildRenderer
from repo2ree_core.script_inference.renderers.venv_activation import VenvActivationRenderer
from repo2ree_core.script_inference.renderers.venv_experiment import VenvExperimentRenderer
from repo2ree_core.script_inference.resolvers import ScoreFreeViabilityResolver

CHECKS: dict[str, Check] = {
    check.code: check
    for check in (
        LogicalProjectRootCheck(),
        DockerfilesAtProjectRootCheck(),
        NestedDockerfilesCheck(),
        RequirementsAtProjectRootCheck(),
        DeclaredRuntimePathCheck(),
        RuntimeArtifactStateCheck(),
        RuntimeArtifactInspectionCheck(),
        UnchangedGeneratedBuildCheck(),
        RuntimeContractKindCheck(),
        DockerConfigCommandsCheck(),
        RequestedExperimentCheck(),
    )
}

RESOLVERS: dict[str, Resolver] = {resolver.code: resolver for resolver in (ScoreFreeViabilityResolver(),)}

RENDERERS: dict[str, Renderer] = {
    renderer.code: renderer
    for renderer in (
        DockerBuildRenderer(),
        PipVenvBuildRenderer(),
        DockerActivationRenderer(),
        VenvActivationRenderer(),
        DockerExperimentRenderer(),
        VenvExperimentRenderer(),
    )
}

DECISION_DAGS: dict[str, DecisionDag] = {
    BUILD_INFERENCE_DAG.key: BUILD_INFERENCE_DAG,
    ACTIVATION_RUN_DAG.key: ACTIVATION_RUN_DAG,
    EXPERIMENT_RUN_DAG.key: EXPERIMENT_RUN_DAG,
}

# Which DAG serves each target kind. Verify targets are deferred (they need an
# explicit author verification claim that has no field on ReeIntent yet), so
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
