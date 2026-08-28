"""Top-level inference entrypoint.

One scan of the immutable upstream tree feeds every requested target; each
target is evaluated independently against its registered DAG and returns a
complete trace even when nothing is inferred. Inference is stateless and always
recomputes — there is no persisted report — and it never writes: it only
produces candidate bytes a caller may later write through ``writeReeFile``.
"""

from __future__ import annotations

from pathlib import Path

from repo2ree_core.author_recipes.inference.engine import evaluate_target
from repo2ree_core.author_recipes.inference.models import (
    DecisionContext,
    DecisionDag,
    DecisionTrace,
    InferenceEngineInfo,
    InferenceReport,
    TargetInferenceResult,
)
from repo2ree_core.author_recipes.inference.policy import InferencePolicy, default_policy
from repo2ree_core.author_recipes.inference.registry import (
    CHECKS,
    DAG_FOR_TARGET_KIND,
    DECISION_DAGS,
    RENDERERS,
    RESOLVERS,
)
from repo2ree_core.author_recipes.inference.repository_facts import scan_repository
from repo2ree_core.author_recipes.inference.runtime_inputs import RuntimeInputs
from repo2ree_core.author_recipes.targets import ScriptTarget, ScriptTargetSelector, resolve_target
from repo2ree_core.domain.ree.model import ReeDefinition

ENGINE_VERSION = "1"


def infer_scripts(
    upstream_path: Path,
    selectors: list[ScriptTargetSelector],
    *,
    definition: ReeDefinition | None = None,
    policy: InferencePolicy | None = None,
    runtime_inputs: RuntimeInputs | None = None,
    source_snapshot_digest: str | None = None,
) -> InferenceReport:
    facts = scan_repository(upstream_path)
    active_policy = policy or default_policy()
    base_context = DecisionContext(
        facts=facts,
        policy=active_policy,
        ree_name=definition.name if definition else "",
        runtime=runtime_inputs or RuntimeInputs(),
    )

    results: list[TargetInferenceResult] = []
    # The static DAGs actually executed, deduplicated by key, so a client can
    # overlay each target's trace onto the full graph it came from.
    used_dags: dict[str, DecisionDag] = {}
    for selector in selectors:
        target = resolve_target(selector)
        dag_key = DAG_FOR_TARGET_KIND.get(target.kind)
        if dag_key is None:
            results.append(_unsupported_result(target))
            continue
        dag = DECISION_DAGS[dag_key]
        used_dags[dag.key] = dag
        # The experiment name lives on the target, so it enters the context here
        # rather than on the shared scan; build/activation targets carry none.
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
    """A requested target with no DAG registered yet — the verify targets in
    Phase 1 (they await an author verification claim ``ReeDefinition`` cannot yet
    carry). Still returns a well-formed, empty trace rather than an error."""
    return TargetInferenceResult(
        target=target,
        status="not_inferred",
        application="unavailable",
        candidates=[],
        warnings=[],
        decision=DecisionTrace(dag="", version=0, steps=[], edges=[], result_node=""),
    )
