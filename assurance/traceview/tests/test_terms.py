"""The words traceview draws by are words the current specification uses."""

from __future__ import annotations

from repo2ree_assurance_checker import load_spec
from repo2ree_assurance_traceview import terms


def test_every_term_traceview_draws_by_is_in_the_specification() -> None:
    spec = load_spec()
    entities, dispatch = spec.entities, spec.boundaries[terms.DISPATCH]
    ree, attempt, action, allocation, receipt = (
        entities[name] for name in (terms.REE, terms.ATTEMPT, terms.ACTION, terms.ALLOCATION, terms.RECEIPT)
    )
    assert {terms.ACTION_NAME, terms.RUN_ID, terms.ATTEMPT_ID, terms.FAILURE_CATEGORY} <= set(action.facts)
    assert terms.PROVISION in action.allowed[terms.ACTION_NAME]
    assert {terms.OPERATION, terms.OUTCOME, terms.COMMIT, terms.CHANGED} <= set(attempt.facts)
    assert terms.SUCCEEDED in attempt.allowed[terms.OUTCOME]
    attempt_states = {terms.PENDING, terms.EXECUTING, terms.COMPLETED, terms.CAPTURED, terms.CAPTURE_FAILED}
    assert attempt_states <= set(attempt.states)
    assert terms.SEALED in ree.states
    assert set(terms.RELEASED) <= set(allocation.states)
    assert {terms.CAUSE, terms.KIND} <= set(receipt.facts)
    assert terms.BASELINE in receipt.allowed[terms.CAUSE]
    assert set(terms.STEP_ORDER) <= set(receipt.allowed[terms.KIND])
    assert {terms.CURRENT, terms.STALE, terms.MISSING, terms.NOT_APPLICABLE} <= set(receipt.states)
    assert {terms.EXEC_ACTION, terms.RESULT} <= set(dispatch.messages)
    assert terms.OPERATION in dispatch.facts[terms.EXEC_ACTION]
    assert terms.STATUS in dispatch.facts[terms.RESULT]
