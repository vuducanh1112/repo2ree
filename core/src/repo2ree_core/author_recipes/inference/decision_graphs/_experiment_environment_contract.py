from __future__ import annotations

from repo2ree_protocol.inference import CheckNode, DecisionNode, ForkNode, ResolveNode, ResultNode, StrategyLeafNode

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
    container = (
        _engine_strategies(docker_rule, docker_render, podman) if podman else _docker_only(docker_rule, docker_render)
    )
    strategies = {"docker": "docker-kind", "venv": "venv-kind"} | ({"podman": "podman-kind"} if podman else {})
    return [
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
        ForkNode(id=FORK, branches=strategies, join=RESOLVE),
        *container,
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
            outcome="candidate",
            rule=rule,
            inference_version=1,
            render=render,
            next=RESOLVE,
        ),
        StrategyLeafNode(id="docker-not-applicable", strategy="docker", outcome="not_applicable", next=RESOLVE),
    ]


def _engine_strategies(docker_rule: str, docker_render: str, podman: tuple[str, str]) -> list[DecisionNode]:
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
