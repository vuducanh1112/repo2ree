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
returns one expected build-script body, with the runtime contract that body
implies, per viable strategy; the caller settles which one the author meant.
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
from repo2ree_core.author_recipes.inference.renderers._common import runtime_image_ref
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT


class ExpectedBuild(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str
    contract: RuntimeContract


def expected_builds_for_runtime(context: DecisionContext, declared_runtime_path: str) -> list[ExpectedBuild]:
    """Every build inference would generate now for the declared runtime.

    One entry per viable strategy, in the engine's candidate order. More than one
    is normal — a repository carrying both a Dockerfile and a requirements.txt
    makes the runtime kind a genuine decision — and the artifact path no longer
    separates them, since every strategy writes to the declared path. The caller
    settles it by digest: only one candidate's body can match the build script
    the author actually saved.
    """
    # A fresh context: the build DAG re-resolves the project root itself and must
    # not collide with a project_root binding already accumulated upstream. The
    # validated declaration is pinned onto it so the renderers below emit the very
    # path this regeneration is being asked about.
    base = DecisionContext(
        facts=context.facts,
        policy=context.policy,
        ree_name=context.ree_name,
        runtime=context.runtime.model_copy(update={"declared_runtime_path": declared_runtime_path}),
    )
    result = evaluate_target(
        BUILD_INFERENCE_DAG,
        base,
        ScriptTarget(kind="build", path=RESERVED_BUILD_SCRIPT),
        checks=BUILD_CHECKS,
        resolvers=BUILD_RESOLVERS,
        renderers=BUILD_RENDERERS,
    )

    expected: list[ExpectedBuild] = []
    for candidate in result.candidates:
        contract = _contract_for(candidate.inference_rule, context.ree_name, declared_runtime_path)
        if contract is not None and candidate.body:
            expected.append(ExpectedBuild(body=candidate.body, contract=contract))
    return expected


def _contract_for(rule: str, ree_name: str, declared_runtime_path: str) -> RuntimeContract | None:
    """The runtime contract a build rule's artifact implies.

    The path is the declared one for every rule — that is where the generated
    script writes — so the rule decides only the *kind* of runtime produced.
    """
    if rule == DOCKER_BUILD_RULE:
        return DockerRuntimeContract(artifact_path=declared_runtime_path, image_ref=runtime_image_ref(ree_name))
    if rule == PIP_BUILD_RULE:
        return VenvRuntimeContract(artifact_path=declared_runtime_path)
    return None
