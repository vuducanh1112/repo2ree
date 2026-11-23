from __future__ import annotations

from repo2ree_core.author_recipes.inference.checks.container_engine import ContainerEngineCheck
from repo2ree_core.author_recipes.inference.checks.dockerfile import (
    DockerfilesAtProjectRootCheck,
    NestedDockerfilesCheck,
)
from repo2ree_core.author_recipes.inference.checks.project_root import LogicalProjectRootCheck
from repo2ree_core.author_recipes.inference.checks.python import RequirementsAtProjectRootCheck
from repo2ree_core.author_recipes.inference.models import Check, Renderer, Resolver
from repo2ree_core.author_recipes.inference.renderers.docker_experiment_environment import DockerBuildRenderer
from repo2ree_core.author_recipes.inference.renderers.podman_experiment_environment import PodmanBuildRenderer
from repo2ree_core.author_recipes.inference.renderers.python_experiment_environment import PipVenvBuildRenderer
from repo2ree_core.author_recipes.inference.resolvers import ScoreFreeViabilityResolver

BUILD_CHECKS: dict[str, Check] = {
    check.code: check
    for check in (
        LogicalProjectRootCheck(),
        DockerfilesAtProjectRootCheck(),
        NestedDockerfilesCheck(),
        RequirementsAtProjectRootCheck(),
        ContainerEngineCheck("docker"),
        ContainerEngineCheck("podman"),
    )
}

BUILD_RESOLVERS: dict[str, Resolver] = {resolver.code: resolver for resolver in (ScoreFreeViabilityResolver(),)}

BUILD_RENDERERS: dict[str, Renderer] = {
    renderer.code: renderer for renderer in (DockerBuildRenderer(), PodmanBuildRenderer(), PipVenvBuildRenderer())
}
