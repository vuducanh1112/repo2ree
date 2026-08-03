from __future__ import annotations

from repo2ree_core.evidence.step_graph import REE_STEPS, ree_step_catalog


def test_catalog_is_acyclic_and_references_known_steps() -> None:
    keys = {step.key for step in REE_STEPS}
    seen: set[str] = set()
    for step in REE_STEPS:
        for requirement in step.requires:
            assert requirement in keys, f"{step.key} requires unknown step {requirement}"
            assert requirement in seen, f"{step.key} requires later/unordered step {requirement}"
        seen.add(step.key)


def test_catalog_orders_are_unique_and_sequential() -> None:
    orders = [step.order for step in ree_step_catalog()]
    assert orders == list(range(1, len(orders) + 1))
