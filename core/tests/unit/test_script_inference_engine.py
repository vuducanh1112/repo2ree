"""Startup DAG-validation coverage.

A structurally broken graph must be rejected before it can ever execute. Each
case corrupts one aspect of the valid build DAG and asserts the validator
rejects it — the guarantee that the published graph is always executable.
"""

from __future__ import annotations

import pytest

from repo2ree_core.script_inference.decision_graphs.build import BUILD_INFERENCE_DAG
from repo2ree_core.script_inference.engine import DagValidationError, validate_dag
from repo2ree_core.script_inference.models import (
    CheckNode,
    DecisionDag,
    ResultNode,
    StrategyLeafNode,
)
from repo2ree_core.script_inference.registry import CHECKS, RENDERERS, RESOLVERS


def _validate(dag: DecisionDag) -> None:
    validate_dag(dag, checks=CHECKS, resolvers=RESOLVERS, renderers=RENDERERS)


def test_reference_build_dag_is_valid() -> None:
    _validate(BUILD_INFERENCE_DAG)  # must not raise


def _mutate(replace: dict[str, object]) -> DecisionDag:
    dag = BUILD_INFERENCE_DAG.model_copy(deep=True)
    nodes = [replace.get(node.id, node) for node in dag.nodes]
    if "__extra__" in replace:
        nodes.append(replace["__extra__"])  # type: ignore[arg-type]
    return dag.model_copy(update={"nodes": nodes})


def test_unknown_check_is_rejected() -> None:
    broken = _mutate(
        {
            "project-root": CheckNode(
                id="project-root",
                check="does_not_exist",
                branches={"root": "runtime-strategies", "wrapper": "runtime-strategies"},
            )
        }
    )
    with pytest.raises(DagValidationError, match="unknown check"):
        _validate(broken)


def test_unhandled_check_branch_is_rejected() -> None:
    broken = _mutate(
        {
            "project-root": CheckNode(
                id="project-root",
                check="logical_project_root",
                branches={"root": "runtime-strategies"},  # missing "wrapper"
            )
        }
    )
    with pytest.raises(DagValidationError, match="do not match check"):
        _validate(broken)


def test_dangling_branch_target_is_rejected() -> None:
    broken = _mutate(
        {
            "project-root": CheckNode(
                id="project-root",
                check="logical_project_root",
                branches={"root": "nowhere", "wrapper": "runtime-strategies"},
            )
        }
    )
    with pytest.raises(DagValidationError, match="unknown node"):
        _validate(broken)


def test_duplicate_node_ids_are_rejected() -> None:
    dup = ResultNode(id="build-complete", status="not_inferred", application="unavailable")
    with pytest.raises(DagValidationError, match="duplicate node ids"):
        _validate(_mutate({"__extra__": dup}))


def test_missing_binding_is_rejected() -> None:
    # Route the "none" branch (which produces no dockerfile binding) straight at
    # the renderer leaf, whose renderer requires the dockerfile binding.
    broken = _mutate(
        {
            "dockerfiles-at-root": CheckNode(
                id="dockerfiles-at-root",
                check="dockerfiles_at_project_root",
                branches={
                    "none": "dockerfile-complete",  # no dockerfile binding on this path
                    "exactly_one": "dockerfile-complete",
                    "more_than_one": "dockerfile-multiple",
                },
            )
        }
    )
    with pytest.raises(DagValidationError, match="not guaranteed on all paths"):
        _validate(broken)


def test_leaf_joining_wrong_node_is_rejected() -> None:
    broken = _mutate(
        {
            "dockerfile-not-applicable": StrategyLeafNode(
                id="dockerfile-not-applicable",
                strategy="dockerfile",
                outcome="not_applicable",
                next="build-complete",  # not the fork's join
            )
        }
    )
    with pytest.raises(DagValidationError):
        _validate(broken)


def test_uncatalogued_leaf_warning_is_rejected() -> None:
    broken = _mutate(
        {
            "dockerfile-multiple": StrategyLeafNode(
                id="dockerfile-multiple",
                strategy="dockerfile",
                outcome="blocked",
                warnings=["totally_made_up_code"],
                next="resolve-runtime-strategies",
            )
        }
    )
    with pytest.raises(DagValidationError, match="uncatalogued warning"):
        _validate(broken)
