"""The shared runtime-contract + command-fork subgraph.

Activation-run and experiment-run inference are identical below their target
gate: resolve the declared experiment environment into a typed contract (inspecting the built
artifact, or matching an unchanged generated build), then fork into one command
strategy per experiment environment kind (docker / venv), join through the score-free resolver,
and land on a result. Only the leaf rules/renderers differ (activation vs
experiment), so both DAGs embed the identical versioned nodes built here — the
published graph stays the exact executable control flow.

Node ids are fixed but validation is per-DAG, so activation and experiment can
reuse the same ids without collision.

Activation also forks by container engine: an image archive is loaded and run by
Docker or by Podman, each its own strategy, viable where its engine is usable and
not applicable where a generated build says the other engine holds the image. The
experiment runs inside the activated environment, so it has no engine of its own
and keeps the single container branch.
"""

from __future__ import annotations

from repo2ree_protocol.inference import CheckNode, DecisionNode, ForkNode, ResolveNode, ResultNode, StrategyLeafNode

# Shared node ids.
ENTRY = "declared-runtime"
FORK = "runtime-command"
RESOLVE = "resolve-runtime-command"
COMPLETE = "run-complete"
NEEDS_INPUT = "run-needs-input"
NOT_INFERRED = "run-not-inferred"


def experiment_environment_contract_and_command_nodes(
    *,
    docker_rule: str,
    docker_render: str,
    venv_rule: str,
    venv_render: str,
    podman: tuple[str, str] | None = None,
) -> list[DecisionNode]:
    """Nodes from the runtime-contract prefix (entry ``ENTRY``) through results.

    The caller wires its target gate to ``ENTRY`` and reuses ``NOT_INFERRED`` as
    the short-circuit target for any of its own blocked prefix branches. ``podman``,
    a (rule, renderer) pair, adds the engine strategies.
    """
    container = (
        _engine_strategies(docker_rule, docker_render, podman) if podman else _docker_only(docker_rule, docker_render)
    )
    strategies = {"docker": "docker-kind", "venv": "venv-kind"} | ({"podman": "podman-kind"} if podman else {})
    return [
        # --- runtime-contract prefix ---
        CheckNode(
            id=ENTRY,
            check="declared_experiment_environment_path",
            branches={"absent": NOT_INFERRED, "outside_root": NOT_INFERRED, "valid": "artifact-state"},
        ),
        CheckNode(
            id="artifact-state",
            check="experiment_environment_artifact_state",
            branches={"regular_file": "inspect-artifact", "missing": "unchanged-build"},
        ),
        CheckNode(
            id="inspect-artifact",
            check="inspect_experiment_environment_artifact",
            branches={
                "docker_single_ref": FORK,
                "venv": FORK,
                "docker_multiple_refs": NOT_INFERRED,
                "docker_no_ref": NOT_INFERRED,
                "invalid": NOT_INFERRED,
            },
        ),
        CheckNode(
            id="unchanged-build",
            check="unchanged_generated_build",
            branches={"matched": FORK, "unmatched": NOT_INFERRED},
        ),
        # --- command fork: one strategy per experiment environment kind (and, for activation, engine) ---
        ForkNode(id=FORK, branches=strategies, join=RESOLVE),
        *container,
        # venv strategy branch
        CheckNode(
            id="venv-kind",
            check="experiment_environment_contract_kind",
            branches={"venv": "venv-command", "docker": "venv-not-applicable"},
        ),
        StrategyLeafNode(
            id="venv-command",
            strategy="venv",
            outcome="candidate",
            rule=venv_rule,
            inference_version=1,
            render=venv_render,
            next=RESOLVE,
        ),
        StrategyLeafNode(id="venv-not-applicable", strategy="venv", outcome="not_applicable", next=RESOLVE),
        # --- join + results ---
        ResolveNode(
            id=RESOLVE,
            fork=FORK,
            resolver="score_free_viability_v1",
            branches={"complete": COMPLETE, "needs_input": NEEDS_INPUT, "not_inferred": NOT_INFERRED},
        ),
        ResultNode(id=COMPLETE, status="complete", application="automatic_allowed"),
        ResultNode(id=NEEDS_INPUT, status="needs_input", application="confirmation_required"),
        ResultNode(id=NOT_INFERRED, status="not_inferred", application="unavailable"),
    ]


def _docker_only(rule: str, render: str) -> list[DecisionNode]:
    return [
        CheckNode(
            id="docker-kind",
            check="experiment_environment_contract_kind",
            branches={"docker": "docker-config", "venv": "docker-not-applicable"},
        ),
        CheckNode(
            id="docker-config",
            check="docker_config_commands",
            branches={"candidates": "docker-command", "none": "docker-command"},
        ),
        StrategyLeafNode(
            id="docker-command",
            strategy="docker",
            # No explicit activation/experiment command source exists in Phase 1,
            # so a resolved docker experiment environment is always a confirmation-required
            # candidate, never an automatic complete.
            outcome="candidate",
            rule=rule,
            inference_version=1,
            render=render,
            next=RESOLVE,
        ),
        StrategyLeafNode(id="docker-not-applicable", strategy="docker", outcome="not_applicable", next=RESOLVE),
    ]


def _engine_strategies(docker_rule: str, docker_render: str, podman: tuple[str, str]) -> list[DecisionNode]:
    """A Docker and a Podman branch over an image archive: each runs where its engine is usable."""
    nodes: list[DecisionNode] = []
    for engine, other, rule, render in (
        ("docker", "podman", docker_rule, docker_render),
        ("podman", "docker", *podman),
    ):
        nodes += [
            CheckNode(
                id=f"{engine}-kind",
                check="experiment_environment_contract_kind",
                branches={"docker": f"{engine}-built-by", "venv": f"{engine}-not-applicable"},
            ),
            CheckNode(
                id=f"{engine}-built-by",
                check="experiment_environment_engine",
                branches={engine: f"{engine}-engine", "unknown": f"{engine}-engine", other: f"{engine}-not-applicable"},
            ),
            CheckNode(
                id=f"{engine}-engine",
                check=f"{engine}_engine",
                branches={
                    "usable": f"{engine}-command",
                    "unknown": f"{engine}-command",
                    "unavailable": f"{engine}-no-engine",
                },
            ),
            StrategyLeafNode(
                id=f"{engine}-command",
                strategy=engine,
                outcome="candidate",
                rule=rule,
                render=render,
                next=RESOLVE,
            ),
            StrategyLeafNode(id=f"{engine}-no-engine", strategy=engine, outcome="blocked", rule=rule, next=RESOLVE),
            StrategyLeafNode(id=f"{engine}-not-applicable", strategy=engine, outcome="not_applicable", next=RESOLVE),
        ]
    return nodes
