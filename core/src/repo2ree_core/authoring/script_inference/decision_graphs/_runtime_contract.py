"""The shared runtime-contract + command-fork subgraph.

Activation-run and experiment-run inference are identical below their target
gate: resolve the declared runtime into a typed contract (inspecting the built
artifact, or matching an unchanged generated build), then fork into one command
strategy per runtime kind (docker / venv), join through the score-free resolver,
and land on a result. Only the leaf rules/renderers differ (activation vs
experiment), so both DAGs embed the identical versioned nodes built here — the
published graph stays the exact executable control flow.

Node ids are fixed but validation is per-DAG, so activation and experiment can
reuse the same ids without collision.
"""

from __future__ import annotations

from repo2ree_core.authoring.script_inference.models import (
    CheckNode,
    DecisionNode,
    ForkNode,
    ResolveNode,
    ResultNode,
    StrategyLeafNode,
)

# Shared node ids.
ENTRY = "declared-runtime"
FORK = "runtime-command"
RESOLVE = "resolve-runtime-command"
COMPLETE = "run-complete"
NEEDS_INPUT = "run-needs-input"
NOT_INFERRED = "run-not-inferred"


def runtime_contract_and_command_nodes(
    *,
    docker_rule: str,
    docker_render: str,
    venv_rule: str,
    venv_render: str,
) -> list[DecisionNode]:
    """Nodes from the runtime-contract prefix (entry ``ENTRY``) through results.

    The caller wires its target gate to ``ENTRY`` and reuses ``NOT_INFERRED`` as
    the short-circuit target for any of its own blocked prefix branches.
    """
    return [
        # --- runtime-contract prefix ---
        CheckNode(
            id=ENTRY,
            check="declared_runtime_path",
            branches={"absent": NOT_INFERRED, "outside_root": NOT_INFERRED, "valid": "artifact-state"},
        ),
        CheckNode(
            id="artifact-state",
            check="runtime_artifact_state",
            branches={"regular_file": "inspect-artifact", "missing": "unchanged-build"},
        ),
        CheckNode(
            id="inspect-artifact",
            check="inspect_runtime_artifact",
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
        # --- command fork: one strategy per runtime kind ---
        ForkNode(id=FORK, branches={"docker": "docker-kind", "venv": "venv-kind"}, join=RESOLVE),
        # docker strategy branch
        CheckNode(
            id="docker-kind",
            check="runtime_contract_kind",
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
            # so a resolved docker runtime is always a confirmation-required
            # candidate, never an automatic complete.
            outcome="candidate",
            rule=docker_rule,
            inference_version=1,
            render=docker_render,
            next=RESOLVE,
        ),
        StrategyLeafNode(id="docker-not-applicable", strategy="docker", outcome="not_applicable", next=RESOLVE),
        # venv strategy branch
        CheckNode(
            id="venv-kind",
            check="runtime_contract_kind",
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
