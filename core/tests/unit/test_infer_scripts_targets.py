"""Orchestration-level coverage for ``infer_scripts`` / ``resolve_target``.

The build DAG has its own suite; this pins the target-resolution and
report-assembly paths around it: reserved-path resolution per kind, selector
validation, and the well-formed ``not_inferred`` result for targets whose DAG
is not registered yet (activation/experiment in Phase 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.author_recipes.inference import ScriptTargetSelector, infer_scripts
from repo2ree_core.author_recipes.inference.inference import resolve_target
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    RESERVED_BUILD_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)


def test_resolve_target_reserved_paths() -> None:
    assert resolve_target(ScriptTargetSelector(kind="build")).path == RESERVED_BUILD_SCRIPT
    assert resolve_target(ScriptTargetSelector(kind="activation_run")).path == RESERVED_ACTIVATION_SCRIPT
    assert resolve_target(ScriptTargetSelector(kind="activation_verify")).path == RESERVED_ACTIVATION_VERIFY_SCRIPT


def test_resolve_target_experiment_paths_use_the_slug() -> None:
    run = resolve_target(ScriptTargetSelector(kind="experiment_run", experiment_name="My Exp"))
    verify = resolve_target(ScriptTargetSelector(kind="experiment_verify", experiment_name="My Exp"))
    assert run.path == experiment_run_script_path("My Exp")
    assert verify.path == experiment_verify_script_path("My Exp")
    assert run.experiment_name == "My Exp"


def test_resolve_target_rejects_experiment_name_on_non_experiment() -> None:
    with pytest.raises(ValueError, match="must not carry an experiment_name"):
        resolve_target(ScriptTargetSelector(kind="build", experiment_name="oops"))


def test_resolve_target_requires_experiment_name_for_experiment() -> None:
    with pytest.raises(ValueError, match="requires an experiment_name"):
        resolve_target(ScriptTargetSelector(kind="experiment_run"))


def test_unregistered_target_kinds_return_wellformed_not_inferred(tmp_path: Path) -> None:
    # Verify targets remain deferred in Phase 1 (no verification-claim field yet).
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    report = infer_scripts(
        tmp_path,
        [
            ScriptTargetSelector(kind="activation_verify"),
            ScriptTargetSelector(kind="experiment_verify", experiment_name="e1"),
        ],
    )
    for result in report.results:
        assert result.status == "not_inferred"
        assert result.application == "unavailable"
        assert result.candidates == []
        # A placeholder-but-valid trace, never a raised error.
        assert result.decision.steps == []


def test_infer_scripts_rejects_a_missing_source_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be an existing directory"):
        infer_scripts(tmp_path / "does-not-exist", [ScriptTargetSelector(kind="build")])


def test_report_ships_the_static_dag_executed(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    report = infer_scripts(tmp_path, [ScriptTargetSelector(kind="build")])
    # The full static graph for the build target travels alongside the trace.
    keys = {dag.key for dag in report.dags}
    assert keys == {"build-inference"}
    build_dag = next(dag for dag in report.dags if dag.key == "build-inference")
    # The trace references a DAG that is actually included, by key and version.
    trace = report.results[0].decision
    assert trace.dag == build_dag.key
    assert trace.version == build_dag.version
    # It is the full graph (all branches), not just the traversed path.
    assert len(build_dag.nodes) > len(trace.steps)


def test_report_deduplicates_dags_across_targets(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM x\n")
    # Two build requests share one DAG; it must appear once.
    report = infer_scripts(
        tmp_path,
        [ScriptTargetSelector(kind="build"), ScriptTargetSelector(kind="build")],
    )
    assert [dag.key for dag in report.dags] == ["build-inference"]


def test_unregistered_targets_contribute_no_dag(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("x")
    report = infer_scripts(tmp_path, [ScriptTargetSelector(kind="activation_verify")])
    assert report.dags == []


def test_report_carries_snapshot_digest(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("x")
    report = infer_scripts(
        tmp_path,
        [ScriptTargetSelector(kind="build")],
        source_snapshot_digest="sha256:abc",
    )
    assert report.source_snapshot_digest == "sha256:abc"
    assert report.engine.name == "repo2ree-script-inference"
