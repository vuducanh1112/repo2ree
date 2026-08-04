"""Regenerate the build script to establish a runtime contract before a build.

The second Phase-1 runtime-evidence source: before the artifact exists, a build
script that is still byte-identical to what inference would generate *now* lets
downstream inference reuse the constants the generator emitted (the image ref a
Docker build tags, or the venv tarball a pip build packs). Merely declaring
``ReeDefinition.runtime`` cannot — a path does not identify what is inside the
artifact.

This runs the published build DAG through the same generic engine (the DAG stays
the sole authority; there is no parallel build rule here) using the shared build
wiring (``build_wiring``) — the same checks, resolver, and renderers the registry
serves — so it never imports the registry (which imports this module's consumers)
yet can never drift from the build inference the registry actually runs. It
returns the expected build-script body and the runtime contract that body
implies, only when a single build candidate's runtime-artifact path matches the
declared runtime.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from repo2ree_core.author_recipes.inference.build_wiring import BUILD_CHECKS, BUILD_RENDERERS, BUILD_RESOLVERS
from repo2ree_core.author_recipes.inference.decision_graphs.build import (
    BUILD_INFERENCE_DAG,
    DOCKER_BUILD_RULE,
    PIP_BUILD_RULE,
)
from repo2ree_core.author_recipes.inference.engine import evaluate_target
from repo2ree_core.author_recipes.inference.models import (
    DecisionContext,
    DockerRuntimeContract,
    RuntimeContract,
    ScriptTarget,
    VenvRuntimeContract,
)
from repo2ree_core.author_recipes.inference.renderers._common import (
    DOCKER_RUNTIME_ARTIFACT_SUFFIX,
    VENV_RUNTIME_ARTIFACT_SUFFIX,
    runtime_artifact_path,
    runtime_image_ref,
)
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT


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
        checks=BUILD_CHECKS,
        resolvers=BUILD_RESOLVERS,
        renderers=BUILD_RENDERERS,
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
    if rule == DOCKER_BUILD_RULE:
        artifact = runtime_artifact_path(root, DOCKER_RUNTIME_ARTIFACT_SUFFIX)
        if artifact != declared_runtime_path:
            return None
        return DockerRuntimeContract(artifact_path=artifact, image_ref=runtime_image_ref(ree_name))
    if rule == PIP_BUILD_RULE:
        artifact = runtime_artifact_path(root, VENV_RUNTIME_ARTIFACT_SUFFIX)
        if artifact != declared_runtime_path:
            return None
        return VenvRuntimeContract(artifact_path=artifact)
    return None
