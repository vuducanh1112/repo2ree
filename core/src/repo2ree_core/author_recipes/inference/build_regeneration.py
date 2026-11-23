from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.author_recipes.inference.build_wiring import BUILD_CHECKS, BUILD_RENDERERS, BUILD_RESOLVERS
from repo2ree_core.author_recipes.inference.decision_graphs.build import (
    BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG,
    DOCKER_BUILD_RULE,
    PIP_BUILD_RULE,
    PODMAN_BUILD_RULE,
)
from repo2ree_core.author_recipes.inference.engine import evaluate_target
from repo2ree_core.author_recipes.inference.models import DecisionContext
from repo2ree_core.author_recipes.inference.renderers._common import experiment_environment_image_ref, podman_image_ref
from repo2ree_protocol.command import ScriptTarget
from repo2ree_protocol.inference import (
    DockerExperimentEnvironmentContract,
    ExperimentEnvironmentContract,
    VenvExperimentEnvironmentContract,
)
from repo2ree_ree.reserved_paths import RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT


class ExpectedBuild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    contract: ExperimentEnvironmentContract


def expected_builds_for_experiment_environment(
    context: DecisionContext, declared_experiment_environment_path: str
) -> list[ExpectedBuild]:
    base = DecisionContext(
        facts=context.facts,
        policy=context.policy,
        ree_name=context.ree_name,
        machine=context.machine,
        experiment_environment=context.experiment_environment.model_copy(
            update={"declared_experiment_environment_path": declared_experiment_environment_path}
        ),
    )
    result = evaluate_target(
        BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG,
        base,
        ScriptTarget(kind="build_experiment_environment", path=RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT),
        checks=BUILD_CHECKS,
        resolvers=BUILD_RESOLVERS,
        renderers=BUILD_RENDERERS,
    )

    expected: list[ExpectedBuild] = []
    for candidate in result.candidates:
        contract = _contract_for(candidate.inference_rule, context.ree_name, declared_experiment_environment_path)
        if contract is not None and candidate.body:
            expected.append(ExpectedBuild(body=candidate.body, contract=contract))
    return expected


def _contract_for(
    rule: str, ree_name: str, declared_experiment_environment_path: str
) -> ExperimentEnvironmentContract | None:
    if rule == DOCKER_BUILD_RULE:
        return DockerExperimentEnvironmentContract(
            artifact_path=declared_experiment_environment_path,
            image_ref=experiment_environment_image_ref(ree_name),
            engine="docker",
        )
    if rule == PODMAN_BUILD_RULE:
        return DockerExperimentEnvironmentContract(
            artifact_path=declared_experiment_environment_path, image_ref=podman_image_ref(ree_name), engine="podman"
        )
    if rule == PIP_BUILD_RULE:
        return VenvExperimentEnvironmentContract(artifact_path=declared_experiment_environment_path)
    return None
