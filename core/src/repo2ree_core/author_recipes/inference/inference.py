from __future__ import annotations

from pathlib import Path

from repo2ree_authoring.targets import resolve_target
from repo2ree_core.author_recipes.inference.engine import evaluate_target
from repo2ree_core.author_recipes.inference.experiment_environment_inputs import ExperimentEnvironmentInputs
from repo2ree_core.author_recipes.inference.machine import MachineInputs
from repo2ree_core.author_recipes.inference.models import DecisionContext
from repo2ree_core.author_recipes.inference.policy import InferencePolicy, default_policy
from repo2ree_core.author_recipes.inference.registry import (
    CHECKS,
    DAG_FOR_TARGET_KIND,
    DECISION_DAGS,
    RENDERERS,
    RESOLVERS,
)
from repo2ree_core.author_recipes.inference.repository_facts import scan_repository
from repo2ree_protocol.command import ScriptTarget, ScriptTargetSelectorArg
from repo2ree_protocol.inference import (
    DecisionDag,
    DecisionTrace,
    InferenceEngineInfo,
    InferenceReport,
    TargetInferenceResult,
)
from repo2ree_ree.model import ReeDefinition

ENGINE_VERSION = "1"


def infer_scripts(
    upstream_path: Path,
    selectors: list[ScriptTargetSelectorArg],
    *,
    definition: ReeDefinition | None = None,
    policy: InferencePolicy | None = None,
    experiment_environment_inputs: ExperimentEnvironmentInputs | None = None,
    machine: MachineInputs | None = None,
    source_snapshot_digest: str | None = None,
) -> InferenceReport:
    facts = scan_repository(upstream_path)
    active_policy = policy or default_policy()
    base_context = DecisionContext(
        facts=facts,
        policy=active_policy,
        ree_name=definition.name if definition else "",
        experiment_environment=experiment_environment_inputs or ExperimentEnvironmentInputs(),
        machine=machine or MachineInputs(),
    )

    results: list[TargetInferenceResult] = []
    used_dags: dict[str, DecisionDag] = {}
    for selector in selectors:
        target = resolve_target(selector)
        dag_key = DAG_FOR_TARGET_KIND.get(target.kind)
        if dag_key is None:
            results.append(_unsupported_result(target))
            continue
        dag = DECISION_DAGS[dag_key]
        used_dags[dag.key] = dag
        context = base_context
        if target.experiment_name:
            context = base_context.model_copy(update={"requested_experiment": target.experiment_name})
        results.append(
            evaluate_target(
                dag,
                context,
                target,
                checks=CHECKS,
                resolvers=RESOLVERS,
                renderers=RENDERERS,
            )
        )

    return InferenceReport(
        schema_version=1,
        source_snapshot_digest=source_snapshot_digest,
        engine=InferenceEngineInfo(version=ENGINE_VERSION),
        results=results,
        dags=list(used_dags.values()),
    )


def _unsupported_result(target: ScriptTarget) -> TargetInferenceResult:
    return TargetInferenceResult(
        target=target,
        status="not_inferred",
        application="unavailable",
        candidates=[],
        warnings=[],
        decision=DecisionTrace(dag="", version=0, steps=[], edges=[], result_node=""),
    )
