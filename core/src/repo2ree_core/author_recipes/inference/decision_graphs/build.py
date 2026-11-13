"""The build-experiment-environment-inference decision DAG.

A shared project-root prefix, a fork into one branch per experiment environment strategy
(``dockerfile`` and ``podman`` for a container file, ``pip``), and an explicit score-free resolver
join. This is deployment-static, versioned data — the sibling of
``ree_step_catalog`` — and it is the *only* control-flow authority: the generic
engine walks exactly these nodes. Adding an ecosystem later means adding a fork
branch and another input edge to the same resolver, never a priority number.

The container branches are locational (see ``checks/dockerfile.py``) and then ask the
machine: more than one project-root container file blocks (can't pick which); a nested
one blocks on ambiguous build context; exactly one at the root is built by Docker on
the ``dockerfile`` branch and by Podman on the ``podman`` branch, each complete where its
engine is usable, blocked where it is not, and a candidate where the engines could not be
probed. Either engine builds either file name, so the name decides nothing. The pip
branch yields a ``candidate`` rather than a complete outcome, so a lone
requirements.txt resolves to ``needs_input`` and a Dockerfile alongside it makes
the two strategies an explicit decision.
"""

from __future__ import annotations

from repo2ree_protocol.inference import CheckNode, DecisionDag, ForkNode, ResolveNode, ResultNode, StrategyLeafNode

# The build-strategy rule ids the leaves below emit. They are the authority:
# ``build_regeneration`` imports these to map a regenerated build candidate back
# to the experiment environment it produces, so the rule name lives in exactly one place and the
# two cannot drift apart behind a string literal.
DOCKER_BUILD_RULE = "single-project-root-dockerfile-v1"
PIP_BUILD_RULE = "root-pip-requirements-v1"
PODMAN_BUILD_RULE = "single-project-root-containerfile-podman"

BUILD_EXPERIMENT_ENVIRONMENT_INFERENCE_DAG = DecisionDag(
    key="build-experiment-environment-inference",
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
            branches={
                "dockerfile": "dockerfiles-at-root",
                "podman": "containerfiles-at-root",
                "pip": "requirements-at-root",
            },
            join="resolve-runtime-strategies",
        ),
        CheckNode(
            id="dockerfiles-at-root",
            check="dockerfiles_at_project_root",
            branches={
                "none": "nested-dockerfiles",
                "exactly_one": "docker-engine",
                "more_than_one": "dockerfile-multiple",
            },
        ),
        CheckNode(
            id="docker-engine",
            check="docker_engine",
            branches={
                "usable": "dockerfile-complete",
                "unknown": "dockerfile-unprobed",
                "unavailable": "dockerfile-no-engine",
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
            id="dockerfile-unprobed",
            strategy="dockerfile",
            outcome="candidate",
            rule=DOCKER_BUILD_RULE,
            render="docker_build_v1",
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="dockerfile-no-engine",
            strategy="dockerfile",
            outcome="blocked",
            rule=DOCKER_BUILD_RULE,
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
        # --- podman strategy branch: the same container file, built with Podman ---
        CheckNode(
            id="containerfiles-at-root",
            check="dockerfiles_at_project_root",
            branches={
                "none": "nested-containerfiles",
                "exactly_one": "podman-engine",
                "more_than_one": "podman-multiple",
            },
        ),
        CheckNode(
            id="nested-containerfiles",
            check="nested_dockerfiles",
            branches={
                "none": "podman-not-applicable",
                "one_or_more": "podman-ambiguous",
            },
        ),
        CheckNode(
            id="podman-engine",
            check="podman_engine",
            branches={
                "usable": "podman-complete",
                "unknown": "podman-unprobed",
                "unavailable": "podman-no-engine",
            },
        ),
        StrategyLeafNode(
            id="podman-complete",
            strategy="podman",
            outcome="complete",
            rule=PODMAN_BUILD_RULE,
            render="podman_build",
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="podman-unprobed",
            strategy="podman",
            outcome="candidate",
            rule=PODMAN_BUILD_RULE,
            render="podman_build",
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="podman-no-engine",
            strategy="podman",
            outcome="blocked",
            rule=PODMAN_BUILD_RULE,
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="podman-multiple",
            strategy="podman",
            outcome="blocked",
            rule=PODMAN_BUILD_RULE,
            warnings=["multiple_dockerfiles"],
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="podman-ambiguous",
            strategy="podman",
            outcome="blocked",
            rule=PODMAN_BUILD_RULE,
            warnings=["ambiguous_build_context"],
            next="resolve-runtime-strategies",
        ),
        StrategyLeafNode(
            id="podman-not-applicable",
            strategy="podman",
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
