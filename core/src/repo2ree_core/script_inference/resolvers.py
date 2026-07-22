"""Score-free strategy resolution.

The resolver joins every strategy leaf's outcome and applies the fixed policy —
it never ranks strategies. "Docker 100 versus Conda 80" is not a valid model:
multiple viable strategies are a visible decision, not a priority contest.

    exactly one viable complete outcome -> complete
    one or more other viable outcomes   -> needs_input
    no viable outcomes                  -> not_inferred

A "viable" outcome is ``complete`` or ``candidate``. ``blocked`` and
``not_applicable`` leaves are not viable but still travel in the observation so
the trace explains why the resolver saw no viable strategy.
"""

from __future__ import annotations

from repo2ree_core.script_inference.models import (
    ResolverResult,
    StrategyOutcome,
    StrategyOutcomeObservation,
    StrategyOutcomesObservation,
)


class ScoreFreeViabilityResolver:
    code = "score_free_viability_v1"
    results = frozenset({"complete", "needs_input", "not_inferred"})

    def evaluate(self, outcomes: dict[str, StrategyOutcome]) -> ResolverResult:
        ordered = [outcomes[name] for name in sorted(outcomes)]
        observed = StrategyOutcomesObservation(
            outcomes=[StrategyOutcomeObservation(strategy=o.strategy, outcome=o.outcome, leaf=o.leaf) for o in ordered]
        )
        completes = [o for o in ordered if o.outcome == "complete"]
        viable = [o for o in ordered if o.outcome in ("complete", "candidate")]

        if len(completes) == 1 and len(viable) == 1:
            result = "complete"
        elif viable:
            result = "needs_input"
        else:
            result = "not_inferred"
        # Postcondition: the resolver only ever returns a result it declared, so
        # the DAG's resolve-node branch map is guaranteed to have an edge for it.
        if result not in self.results:
            raise AssertionError(f"resolver produced an undeclared result: {result!r}")
        return ResolverResult(result=result, observed=observed)
