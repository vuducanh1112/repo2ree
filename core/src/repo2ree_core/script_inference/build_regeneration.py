"""Regenerate the build script to establish a runtime contract before a build.

The second Phase-1 runtime-evidence source: before the artifact exists, a build
script that is still byte-identical to what inference would generate *now* lets
downstream inference reuse the constants the generator emitted (the image ref a
Docker build tags, or the venv tarball a pip build packs). Merely declaring
``ReeIntent.runtime`` cannot — a path does not identify what is inside the
artifact.

This runs the published build DAG through the same generic engine (the DAG stays
the sole authority; there is no parallel build rule here) with the build checks,
resolver, and renderers wired directly so it never imports the registry — which
imports this module's consumers. It returns the expected build-script body and
the runtime contract that body implies, only when a single build candidate's
runtime-artifact path matches the declared runtime.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.script_inference.checks.dockerfile import (
    DockerfilesAtProjectRootCheck,
    NestedDockerfilesCheck,
)
from repo2ree_core.script_inference.checks.project_root import LogicalProjectRootCheck
from repo2ree_core.script_inference.checks.python import RequirementsAtProjectRootCheck
from repo2ree_core.script_inference.decision_graphs.build import BUILD_INFERENCE_DAG
from repo2ree_core.script_inference.engine import evaluate_target
from repo2ree_core.script_inference.models import (
    Check,
    DecisionContext,
    DockerRuntimeContract,
    Renderer,
    Resolver,
    RuntimeContract,
    ScriptTarget,
    VenvRuntimeContract,
)
from repo2ree_core.script_inference.renderers._common import (
    DOCKER_RUNTIME_ARTIFACT_SUFFIX,
    VENV_RUNTIME_ARTIFACT_SUFFIX,
    runtime_artifact_path,
    runtime_image_ref,
)
from repo2ree_core.script_inference.renderers.docker_runtime import DockerBuildRenderer
from repo2ree_core.script_inference.renderers.python_runtime import PipVenvBuildRenderer
from repo2ree_core.script_inference.resolvers import ScoreFreeViabilityResolver

_BUILD_CHECKS: dict[str, Check] = {
    check.code: check
    for check in (
        LogicalProjectRootCheck(),
        DockerfilesAtProjectRootCheck(),
        NestedDockerfilesCheck(),
        RequirementsAtProjectRootCheck(),
    )
}
_BUILD_RESOLVERS: dict[str, Resolver] = {ScoreFreeViabilityResolver().code: ScoreFreeViabilityResolver()}
_BUILD_RENDERERS: dict[str, Renderer] = {
    renderer.code: renderer for renderer in (DockerBuildRenderer(), PipVenvBuildRenderer())
}

# Maps a build strategy rule to the runtime it produces at the logical root.
_DOCKER_RULE = "single-project-root-dockerfile-v1"
_PIP_RULE = "root-pip-requirements-v1"


class ExpectedBuild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    contract: RuntimeContract


def expected_build_for_runtime(context: DecisionContext, declared_runtime_path: str) -> ExpectedBuild | None:
    """The build inference would generate now, if it produces the declared runtime.

    Returns the expected build-script body and the implied runtime contract, or
    ``None`` when nothing is inferred, when the sole build candidate does not
    target the declared runtime path, or when the runtime is ambiguous.
    """
    root = context.facts.logical_project_root
    # A fresh context: the build DAG re-resolves the project root itself and must
    # not collide with a project_root binding already accumulated upstream.
    base = DecisionContext(
        facts=context.facts,
        policy=context.policy,
        ree_name=context.ree_name,
        runtime=context.runtime,
    )
    result = evaluate_target(
        BUILD_INFERENCE_DAG,
        base,
        ScriptTarget(kind="build", path=RESERVED_BUILD_SCRIPT),
        checks=_BUILD_CHECKS,
        resolvers=_BUILD_RESOLVERS,
        renderers=_BUILD_RENDERERS,
    )

    for candidate in result.candidates:
        contract = _contract_for(candidate.inference_rule, root, context.ree_name, declared_runtime_path)
        if contract is not None and candidate.body:
            return ExpectedBuild(body=candidate.body, contract=contract)
    return None


def _contract_for(
    rule: str,
    root: str,
    ree_name: str,
    declared_runtime_path: str,
) -> RuntimeContract | None:
    if rule == _DOCKER_RULE:
        artifact = runtime_artifact_path(root, DOCKER_RUNTIME_ARTIFACT_SUFFIX)
        if artifact != declared_runtime_path:
            return None
        return DockerRuntimeContract(artifact_path=artifact, image_ref=runtime_image_ref(ree_name))
    if rule == _PIP_RULE:
        artifact = runtime_artifact_path(root, VENV_RUNTIME_ARTIFACT_SUFFIX)
        if artifact != declared_runtime_path:
            return None
        return VenvRuntimeContract(artifact_path=artifact)
    return None
