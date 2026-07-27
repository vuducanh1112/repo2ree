"""The Phase 1 build-inference decision DAG.

A shared project-root prefix, a fork into one branch per runtime strategy
(only ``dockerfile`` in Phase 1), and an explicit score-free resolver join.
This is deployment-static, versioned data — the sibling of ``ree_step_catalog``
— and it is the *only* control-flow authority: the generic engine walks exactly
these nodes. Adding an ecosystem later means adding a fork branch and another
input edge to the same resolver, never a priority number.

The dockerfile branch is purely locational (see ``checks/dockerfile.py``): more
than one project-root Dockerfile blocks (can't pick which); a nested Dockerfile
blocks on ambiguous build context; exactly one at the root is complete.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.models import (
    CheckNode,
    DecisionDag,
    ForkNode,
    ResolveNode,
    ResultNode,
    StrategyLeafNode,
)

# The build-strategy rule ids the leaves below emit. They are the authority:
# ``build_regeneration`` imports these to map a regenerated build candidate back
# to the runtime it produces, so the rule name lives in exactly one place and the
# two cannot drift apart behind a string literal.
DOCKER_BUILD_RULE = "single-project-root-dockerfile-v1"
PIP_BUILD_RULE = "root-pip-requirements-v1"

BUILD_INFERENCE_DAG = DecisionDag(
    key="build-inference",
    version=1,
    root="project-root",
    nodes=[
        CheckNode(
            id="project-root",
            check="logical_project_root",
            branches={"root": "runtime-strategies", "wrapper": "runtime-strategies"},
        ),
        ForkNode(
            id="runtime-strategies",
            branches={"dockerfile": "dockerfiles-at-root", "pip": "requirements-at-root"},
            join="resolve-runtime-strategies",
        ),
        CheckNode(
            id="dockerfiles-at-root",
            check="dockerfiles_at_project_root",
            branches={
                "none": "nested-dockerfiles",
                "exactly_one": "dockerfile-complete",
                "more_than_one": "dockerfile-multiple",
            },
        ),
        CheckNode(
            id="nested-dockerfiles",
            check="nested_dockerfiles",
            branches={
                "none": "dockerfile-not-applicable",
                "one_or_more": "dockerfile-ambiguous",
            },
        ),
        StrategyLeafNode(
            id="dockerfile-complete",
            strategy="dockerfile",
            outcome="complete",
            rule=DOCKER_BUILD_RULE,
            inference_version=1,
            render="docker_build_v1",
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="dockerfile-multiple",
            strategy="dockerfile",
            outcome="blocked",
            rule=DOCKER_BUILD_RULE,
            warnings=["multiple_dockerfiles"],
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="dockerfile-ambiguous",
            strategy="dockerfile",
            outcome="blocked",
            rule=DOCKER_BUILD_RULE,
            warnings=["ambiguous_build_context"],
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="dockerfile-not-applicable",
            strategy="dockerfile",
            outcome="not_applicable",
            next="resolve-runtime-strategies",
        ),
        # --- pip-requirements strategy branch ---
        CheckNode(
            id="requirements-at-root",
            check="requirements_at_project_root",
            branches={
                "none": "pip-not-applicable",
                "exactly_one": "pip-candidate",
            },
        ),
        StrategyLeafNode(
            id="pip-candidate",
            strategy="pip",
            # A generated build strategy is viable but requires confirmation: a
            # lone candidate therefore resolves to needs_input, and a Dockerfile
            # alongside it makes the two strategies an explicit decision.
            outcome="candidate",
            rule=PIP_BUILD_RULE,
            inference_version=1,
            render="pip_venv_build_v1",
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="pip-not-applicable",
            strategy="pip",
            outcome="not_applicable",
            next="resolve-runtime-strategies",
        ),
        ResolveNode(
            id="resolve-runtime-strategies",
            fork="runtime-strategies",
            resolver="score_free_viability_v1",
            branches={
                "complete": "build-complete",
                "needs_input": "build-needs-input",
                "not_inferred": "build-not-inferred",
            },
        ),
        ResultNode(id="build-complete", status="complete", application="automatic_allowed"),
        ResultNode(
            id="build-needs-input",
            status="needs_input",
            application="confirmation_required",
        ),
        ResultNode(id="build-not-inferred", status="not_inferred", application="unavailable"),
    ],
)
