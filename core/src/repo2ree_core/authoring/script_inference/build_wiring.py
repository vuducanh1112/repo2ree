"""The single wiring of the build DAG's checks, resolver, and renderers.

Both the registry (the deployment surface) and ``build_regeneration`` (which
re-runs the build DAG to establish a runtime contract before the artifact
exists) need the exact set of checks/resolver/renderers the build graph walks.
Keeping that set in one place means the two callers can never drift: adding a
build strategy here updates both at once, so ``unchanged_generated_build`` can
never compute an expected body from a different wiring than the registry serves.

This module imports only build-side pieces — never the run-side checks/renderers
or the registry — so ``build_regeneration`` can import it without the import
cycle that pulling in the full registry would create.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.checks.dockerfile import (
    DockerfilesAtProjectRootCheck,
    NestedDockerfilesCheck,
)
from repo2ree_core.authoring.script_inference.checks.project_root import LogicalProjectRootCheck
from repo2ree_core.authoring.script_inference.checks.python import RequirementsAtProjectRootCheck
from repo2ree_core.authoring.script_inference.models import Check, Renderer, Resolver
from repo2ree_core.authoring.script_inference.renderers.docker_runtime import DockerBuildRenderer
from repo2ree_core.authoring.script_inference.renderers.python_runtime import PipVenvBuildRenderer
from repo2ree_core.authoring.script_inference.resolvers import ScoreFreeViabilityResolver

BUILD_CHECKS: dict[str, Check] = {
    check.code: check
    for check in (
        LogicalProjectRootCheck(),
        DockerfilesAtProjectRootCheck(),
        NestedDockerfilesCheck(),
        RequirementsAtProjectRootCheck(),
    )
}

BUILD_RESOLVERS: dict[str, Resolver] = {resolver.code: resolver for resolver in (ScoreFreeViabilityResolver(),)}

BUILD_RENDERERS: dict[str, Renderer] = {
    renderer.code: renderer for renderer in (DockerBuildRenderer(), PipVenvBuildRenderer())
}
