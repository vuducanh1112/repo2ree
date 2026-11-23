from __future__ import annotations

from repo2ree_core.author_recipes.inference.build_wiring import BUILD_CHECKS, BUILD_RENDERERS, BUILD_RESOLVERS
from repo2ree_core.author_recipes.inference.checks.container_engine import ContractEngineCheck
from repo2ree_core.author_recipes.inference.checks.docker_config import DockerConfigCommandsCheck
from repo2ree_core.author_recipes.inference.checks.experiment import RequestedExperimentCheck
from repo2ree_core.author_recipes.inference.checks.experiment_environment_contract import (
    DeclaredExperimentEnvironmentPathCheck,
    ExperimentEnvironmentArtifactInspectionCheck,
    ExperimentEnvironmentArtifactStateCheck,
    ExperimentEnvironmentContractKindCheck,
    UnchangedGeneratedBuildCheck,
)
from repo2ree_core.author_recipes.inference.checks.slurm import SlurmCheck
from repo2ree_core.author_recipes.inference.decision_graphs.activate_experiment_environment import (
    ACTIVATE_EXPERIMENT_ENVIRONMENT_DAG,
)
from repo2ree_core.author_recipes.inference.decision_graphs.build import BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG
from repo2ree_core.author_recipes.inference.decision_graphs.experiment_run import EXPERIMENT_RUN_DAG
from repo2ree_core.author_recipes.inference.decision_graphs.launch import LAUNCH_DAG
from repo2ree_core.author_recipes.inference.engine import validate_dag
from repo2ree_core.author_recipes.inference.models import Check, Renderer, Resolver
from repo2ree_core.author_recipes.inference.renderers.activate_experiment_environment import (
    DockerActivateExperimentEnvironmentRenderer,
    PodmanActivateExperimentEnvironmentRenderer,
    VenvActivateExperimentEnvironmentRenderer,
)
from repo2ree_core.author_recipes.inference.renderers.docker_experiment import DockerExperimentRenderer
from repo2ree_core.author_recipes.inference.renderers.slurm_launch import SlurmLaunchRenderer
from repo2ree_core.author_recipes.inference.renderers.venv_experiment import VenvExperimentRenderer
from repo2ree_protocol.inference import DecisionDag

CHECKS: dict[str, Check] = {
    **BUILD_CHECKS,
    **{
        check.code: check
        for check in (
            DeclaredExperimentEnvironmentPathCheck(),
            ExperimentEnvironmentArtifactStateCheck(),
            ExperimentEnvironmentArtifactInspectionCheck(),
            UnchangedGeneratedBuildCheck(),
            ExperimentEnvironmentContractKindCheck(),
            ContractEngineCheck(),
            DockerConfigCommandsCheck(),
            RequestedExperimentCheck(),
            SlurmCheck(),
        )
    },
}

RESOLVERS: dict[str, Resolver] = dict(BUILD_RESOLVERS)

RENDERERS: dict[str, Renderer] = {
    **BUILD_RENDERERS,
    **{
        renderer.code: renderer
        for renderer in (
            DockerActivateExperimentEnvironmentRenderer(),
            PodmanActivateExperimentEnvironmentRenderer(),
            VenvActivateExperimentEnvironmentRenderer(),
            DockerExperimentRenderer(),
            VenvExperimentRenderer(),
            SlurmLaunchRenderer(),
        )
    },
}

DECISION_DAGS: dict[str, DecisionDag] = {
    BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG.key: BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG,
    ACTIVATE_EXPERIMENT_ENVIRONMENT_DAG.key: ACTIVATE_EXPERIMENT_ENVIRONMENT_DAG,
    EXPERIMENT_RUN_DAG.key: EXPERIMENT_RUN_DAG,
    LAUNCH_DAG.key: LAUNCH_DAG,
}

DAG_FOR_TARGET_KIND: dict[str, str] = {
    "build_experiment_environment": BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG.key,
    "activate_experiment_environment": ACTIVATE_EXPERIMENT_ENVIRONMENT_DAG.key,
    "experiment_run": EXPERIMENT_RUN_DAG.key,
    "launch": LAUNCH_DAG.key,
}


def validate_all() -> None:
    for dag in DECISION_DAGS.values():
        validate_dag(dag, checks=CHECKS, resolvers=RESOLVERS, renderers=RENDERERS)


validate_all()
