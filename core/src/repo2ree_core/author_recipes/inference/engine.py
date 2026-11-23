from __future__ import annotations

from repo2ree_core.author_recipes.inference.models import (
    BindingKind,
    Check,
    DecisionContext,
    RenderedScript,
    Renderer,
    Resolver,
    StrategyOutcome,
)
from repo2ree_core.author_recipes.inference.warnings import is_known_code, make_warning
from repo2ree_core.digests import short_hash
from repo2ree_protocol.command import ScriptTarget
from repo2ree_protocol.inference import (
    CheckNode,
    DecisionDag,
    DecisionNode,
    DecisionStep,
    DecisionTrace,
    ForkNode,
    InferenceWarning,
    ResolveNode,
    ResultNode,
    ScriptCandidate,
    ScriptValidation,
    StrategyLeafNode,
    TargetInferenceResult,
    TraversedEdge,
)
from repo2ree_ree.digest import digest_bytes


class DagValidationError(ValueError):
    pass


def validate_dag(
    dag: DecisionDag,
    *,
    checks: dict[str, Check],
    resolvers: dict[str, Resolver],
    renderers: dict[str, Renderer],
) -> None:
    nodes = dag.nodes
    ids = [node.id for node in nodes]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise DagValidationError(f"{dag.key}: duplicate node ids: {dupes}")
    by_id = {node.id: node for node in nodes}

    if dag.root not in by_id:
        raise DagValidationError(f"{dag.key}: root {dag.root!r} is not a node")

    def require_target(source: str, target: str) -> None:
        if target not in by_id:
            raise DagValidationError(f"{dag.key}: {source} points at unknown node {target!r}")

    for node in nodes:
        if isinstance(node, CheckNode):
            check = checks.get(node.check)
            if check is None:
                raise DagValidationError(f"{dag.key}: node {node.id} references unknown check {node.check!r}")
            if set(node.branches) != set(check.branches):
                raise DagValidationError(
                    f"{dag.key}: node {node.id} branches {sorted(node.branches)} "
                    f"do not match check {node.check!r} branches {sorted(check.branches)}"
                )
            for branch, target in node.branches.items():
                require_target(f"node {node.id} branch {branch!r}", target)
                dest = by_id[target]
                if isinstance(dest, ResultNode) and dest.status != "not_inferred":
                    raise DagValidationError(
                        f"{dag.key}: check {node.id} branch {branch!r} short-circuits to "
                        f"{dest.status!r} result {target!r}; only not_inferred is allowed"
                    )
        elif isinstance(node, ForkNode):
            if not node.branches:
                raise DagValidationError(f"{dag.key}: fork {node.id} has no strategy branches")
            for branch, target in node.branches.items():
                require_target(f"fork {node.id} branch {branch!r}", target)
            require_target(f"fork {node.id} join", node.join)
            join = by_id[node.join]
            if not isinstance(join, ResolveNode):
                raise DagValidationError(f"{dag.key}: fork {node.id} join {node.join!r} is not a resolve node")
        elif isinstance(node, StrategyLeafNode):
            require_target(f"leaf {node.id} next", node.next)
            if not isinstance(by_id[node.next], ResolveNode):
                raise DagValidationError(f"{dag.key}: leaf {node.id} next {node.next!r} is not a resolve node")
            if node.outcome in ("complete", "candidate"):
                if node.render is None:
                    raise DagValidationError(f"{dag.key}: viable leaf {node.id} has no renderer")
                if node.render not in renderers:
                    raise DagValidationError(f"{dag.key}: leaf {node.id} references unknown renderer {node.render!r}")
            for code in node.warnings:
                if not is_known_code(code):
                    raise DagValidationError(f"{dag.key}: leaf {node.id} emits uncatalogued warning {code!r}")
        elif isinstance(node, ResolveNode):
            resolver = resolvers.get(node.resolver)
            if resolver is None:
                raise DagValidationError(f"{dag.key}: resolve {node.id} references unknown resolver {node.resolver!r}")
            require_target(f"resolve {node.id} fork", node.fork)
            fork = by_id[node.fork]
            if not isinstance(fork, ForkNode) or fork.join != node.id:
                raise DagValidationError(f"{dag.key}: resolve {node.id} fork {node.fork!r} does not join back to it")
            if set(node.branches) != set(resolver.results):
                raise DagValidationError(
                    f"{dag.key}: resolve {node.id} branches {sorted(node.branches)} "
                    f"do not match resolver {node.resolver!r} results {sorted(resolver.results)}"
                )
            for branch, target in node.branches.items():
                require_target(f"resolve {node.id} branch {branch!r}", target)
                if not isinstance(by_id[target], ResultNode):
                    raise DagValidationError(f"{dag.key}: resolve {node.id} branch {branch!r} is not a result node")

    for node in nodes:
        if isinstance(node, ForkNode):
            for leaf in _reachable_leaves(dag, node, by_id):
                if leaf.next != node.join:
                    raise DagValidationError(
                        f"{dag.key}: leaf {leaf.id} in fork {node.id} joins {leaf.next!r}, not {node.join!r}"
                    )

    _validate_acyclic(dag, by_id)
    _validate_bindings(dag, by_id, checks=checks, renderers=renderers)
    _validate_result_reachability(dag, by_id)


def _successors(node: DecisionNode) -> list[str]:
    if isinstance(node, CheckNode):
        return list(node.branches.values())
    if isinstance(node, ForkNode):
        return [*node.branches.values(), node.join]
    if isinstance(node, StrategyLeafNode):
        return [node.next]
    if isinstance(node, ResolveNode):
        return list(node.branches.values())
    return []


def _reachable_leaves(dag: DecisionDag, fork: ForkNode, by_id: dict[str, DecisionNode]) -> list[StrategyLeafNode]:
    leaves: list[StrategyLeafNode] = []
    seen: set[str] = set()
    stack = list(fork.branches.values())
    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id == fork.join:
            continue
        seen.add(node_id)
        node = by_id[node_id]
        if isinstance(node, StrategyLeafNode):
            leaves.append(node)
            continue
        if isinstance(node, CheckNode):
            stack.extend(node.branches.values())
    return leaves


def _validate_acyclic(dag: DecisionDag, by_id: dict[str, DecisionNode]) -> None:
    color: dict[str, int] = {}

    def visit(node_id: str) -> None:
        state = color.get(node_id)
        if state == 1:
            return
        if state == 0:
            raise DagValidationError(f"{dag.key}: cycle detected at node {node_id!r}")
        color[node_id] = 0
        for succ in _successors(by_id[node_id]):
            visit(succ)
        color[node_id] = 1

    visit(dag.root)


def _validate_result_reachability(dag: DecisionDag, by_id: dict[str, DecisionNode]) -> None:
    reachable: set[str] = set()
    stack = [dag.root]
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        stack.extend(_successors(by_id[node_id]))
    result_nodes = {node.id for node in dag.nodes if isinstance(node, ResultNode)}
    unreachable = result_nodes - reachable
    if unreachable:
        raise DagValidationError(f"{dag.key}: unreachable result nodes: {sorted(unreachable)}")


def _validate_bindings(
    dag: DecisionDag,
    by_id: dict[str, DecisionNode],
    *,
    checks: dict[str, Check],
    renderers: dict[str, Renderer],
) -> None:
    incoming: dict[str, frozenset[BindingKind] | None] = {node.id: None for node in dag.nodes}
    incoming[dag.root] = frozenset()

    changed = True
    while changed:
        changed = False
        for node in dag.nodes:
            here = incoming[node.id]
            if here is None:
                continue
            for branch, target in _binding_edges(node):
                produced = _produced_bindings(node, branch, checks)
                out = here | produced
                prev = incoming[target]
                merged = out if prev is None else (prev & out)
                if merged != prev:
                    incoming[target] = merged
                    changed = True

    for node in dag.nodes:
        here = incoming[node.id] or frozenset()
        if isinstance(node, CheckNode):
            required = checks[node.check].requires
            missing = required - here
            if missing:
                raise DagValidationError(
                    f"{dag.key}: check node {node.id} needs bindings {sorted(missing)} not guaranteed on all paths"
                )
        elif isinstance(node, StrategyLeafNode) and node.render is not None:
            required = renderers[node.render].requires
            missing = required - here
            if missing:
                raise DagValidationError(
                    f"{dag.key}: leaf {node.id} renderer needs bindings {sorted(missing)} not guaranteed on all paths"
                )


def _binding_edges(node: DecisionNode) -> list[tuple[str, str]]:
    if isinstance(node, CheckNode):
        return list(node.branches.items())
    if isinstance(node, ForkNode):
        return list(node.branches.items())
    if isinstance(node, StrategyLeafNode):
        return [("join", node.next)]
    return []


def _produced_bindings(node: DecisionNode, branch: str, checks: dict[str, Check]) -> frozenset[BindingKind]:
    if isinstance(node, CheckNode):
        return checks[node.check].produces.get(branch, frozenset())
    return frozenset()


def evaluate_target(
    dag: DecisionDag,
    context: DecisionContext,
    target: ScriptTarget,
    *,
    checks: dict[str, Check],
    resolvers: dict[str, Resolver],
    renderers: dict[str, Renderer],
) -> TargetInferenceResult:
    steps: list[DecisionStep] = []
    edges: list[TraversedEdge] = []
    by_id = {node.id: node for node in dag.nodes}

    rendered: dict[str, tuple[StrategyLeafNode, RenderedScript]] = {}
    outcomes: dict[str, StrategyOutcome] = {}
    prefix_warnings: list[InferenceWarning] = []

    current = dag.root
    while True:
        node = by_id[current]

        if isinstance(node, CheckNode):
            result = checks[node.check].evaluate(context)
            steps.append(
                DecisionStep(
                    node_id=node.id,
                    kind="check",
                    check=node.check,
                    branch=result.branch,
                    observed=result.observed,
                    bindings=result.bindings,
                    evidence=result.evidence,
                )
            )
            prefix_warnings.extend(result.warnings)
            context = context.with_bindings(result.bindings)
            target_id = node.branches[result.branch]
            edges.append(TraversedEdge(source=node.id, branch=result.branch, target=target_id))
            current = target_id
            continue

        if isinstance(node, ForkNode):
            steps.append(DecisionStep(node_id=node.id, kind="fork", outcome=f"evaluated: {len(node.branches)}"))
            for strategy in sorted(node.branches):
                child = node.branches[strategy]
                edges.append(TraversedEdge(source=node.id, branch=strategy, target=child))
                outcome, branch_steps, branch_edges = _walk_branch(
                    dag,
                    by_id,
                    child,
                    context,
                    target,
                    checks=checks,
                    renderers=renderers,
                    rendered=rendered,
                )
                steps.extend(branch_steps)
                edges.extend(branch_edges)
                outcomes[strategy] = outcome
            current = node.join
            continue

        if isinstance(node, ResolveNode):
            resolver_result = resolvers[node.resolver].evaluate(outcomes)
            steps.append(
                DecisionStep(
                    node_id=node.id,
                    kind="resolve",
                    observed=resolver_result.observed,
                    outcome=resolver_result.result,
                )
            )
            target_id = node.branches[resolver_result.result]
            edges.append(TraversedEdge(source=node.id, branch=resolver_result.result, target=target_id))
            current = target_id
            continue

        if isinstance(node, ResultNode):
            steps.append(DecisionStep(node_id=node.id, kind="result", outcome=node.status))
            trace = DecisionTrace(
                dag=dag.key,
                version=dag.version,
                steps=steps,
                edges=edges,
                result_node=node.id,
            )
            candidates = _finalize_candidates(node, target, outcomes, rendered)
            warnings = _collect_warnings(outcomes, candidates, prefix_warnings)
            return TargetInferenceResult(
                target=target,
                status=node.status,
                application=node.application,
                candidates=candidates,
                warnings=warnings,
                decision=trace,
            )

        raise DagValidationError(f"{dag.key}: unwalkable node {node.id!r}")


def _walk_branch(
    dag: DecisionDag,
    by_id: dict[str, DecisionNode],
    start: str,
    context: DecisionContext,
    target: ScriptTarget,
    *,
    checks: dict[str, Check],
    renderers: dict[str, Renderer],
    rendered: dict[str, tuple[StrategyLeafNode, RenderedScript]],
) -> tuple[StrategyOutcome, list[DecisionStep], list[TraversedEdge]]:
    steps: list[DecisionStep] = []
    edges: list[TraversedEdge] = []
    branch_warnings: list[InferenceWarning] = []
    current = start
    while True:
        node = by_id[current]
        if isinstance(node, CheckNode):
            result = checks[node.check].evaluate(context)
            steps.append(
                DecisionStep(
                    node_id=node.id,
                    kind="check",
                    check=node.check,
                    branch=result.branch,
                    observed=result.observed,
                    bindings=result.bindings,
                    evidence=result.evidence,
                )
            )
            branch_warnings.extend(result.warnings)
            context = context.with_bindings(result.bindings)
            target_id = node.branches[result.branch]
            edges.append(TraversedEdge(source=node.id, branch=result.branch, target=target_id))
            current = target_id
            continue

        if isinstance(node, StrategyLeafNode):
            leaf_warnings = [make_warning(code) for code in node.warnings]
            if node.render is not None and node.outcome in ("complete", "candidate"):
                rendered_script = renderers[node.render].render(context, target)
                rendered[node.strategy] = (node, rendered_script)
            steps.append(DecisionStep(node_id=node.id, kind="strategy_leaf", outcome=node.outcome))
            edges.append(TraversedEdge(source=node.id, branch="join", target=node.next))
            outcome = StrategyOutcome(
                strategy=node.strategy,
                leaf=node.id,
                outcome=node.outcome,
                bindings=context.bindings,
                warnings=branch_warnings + leaf_warnings,
            )
            return outcome, steps, edges

        raise DagValidationError(f"{dag.key}: strategy branch reached non-leaf terminal {node.id!r}")


def _finalize_candidates(
    result_node: ResultNode,
    target: ScriptTarget,
    outcomes: dict[str, StrategyOutcome],
    rendered: dict[str, tuple[StrategyLeafNode, RenderedScript]],
) -> list[ScriptCandidate]:
    if result_node.status == "not_inferred":
        return []
    candidates: list[ScriptCandidate] = []
    for strategy in sorted(rendered):
        outcome = outcomes.get(strategy)
        if outcome is None or outcome.outcome not in ("complete", "candidate"):
            continue
        leaf, script = rendered[strategy]
        body = script.body
        body_hash = short_hash(body.encode())
        rule = leaf.rule or leaf.strategy
        candidate_id = f"{rule}:{leaf.inference_version}:{target.kind}:{body_hash}"
        candidates.append(
            ScriptCandidate(
                candidate_id=candidate_id,
                target=target,
                status=result_node.status,
                application=result_node.application,
                body=body,
                dependencies=script.dependencies,
                evidence=script.evidence,
                warnings=script.warnings,
                inference_rule=rule,
                inference_version=leaf.inference_version,
                decision_leaf=leaf.id,
                validation=ScriptValidation(
                    status="not_run",
                    script_digest=digest_bytes(body.encode()),
                ),
            )
        )
    return candidates


def _collect_warnings(
    outcomes: dict[str, StrategyOutcome],
    candidates: list[ScriptCandidate],
    prefix_warnings: list[InferenceWarning],
) -> list[InferenceWarning]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    union: list[InferenceWarning] = []
    for warning in prefix_warnings:
        key = (warning.code, tuple(warning.affected_paths))
        if key not in seen:
            seen.add(key)
            union.append(warning)
    for strategy in sorted(outcomes):
        source_warnings = list(outcomes[strategy].warnings)
        for warning in source_warnings:
            key = (warning.code, tuple(warning.affected_paths))
            if key not in seen:
                seen.add(key)
                union.append(warning)
    for candidate in candidates:
        for warning in candidate.warnings:
            key = (warning.code, tuple(warning.affected_paths))
            if key not in seen:
                seen.add(key)
                union.append(warning)
    return union
