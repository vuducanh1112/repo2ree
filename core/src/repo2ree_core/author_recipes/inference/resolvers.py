from __future__ import annotations

from repo2ree_core.author_recipes.inference.models import ResolverResult, StrategyOutcome
from repo2ree_protocol.inference import StrategyOutcomeObservation, StrategyOutcomesObservation


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
        if result not in self.results:
            raise AssertionError(f"resolver produced an undeclared result: {result!r}")
        return ResolverResult(result=result, observed=observed)
