"""The words traceview draws by are words the current specification uses."""

from __future__ import annotations

from repo2ree_assurance_checker import load_spec
from repo2ree_assurance_traceview import terms


def test_every_term_traceview_draws_by_is_in_the_specification() -> None:
    spec = load_spec()
    entities, start, follow = spec.entities, spec.boundaries[terms.START_RUN], spec.boundaries[terms.FOLLOW_RUN]
    ree, attempt, action, receipt = (entities[name] for name in (terms.REE, terms.ATTEMPT, terms.ACTION, terms.RECEIPT))
    assert {terms.ACTION_NAME, terms.RUN_ID, terms.ATTEMPT_ID, terms.FAILURE_CATEGORY} <= set(action.facts)
    assert {terms.PROVISION, terms.LOAD_BUNDLE} <= set(action.allowed[terms.ACTION_NAME])
    assert set(terms.READS) == set(action.groups[terms.ACTION_NAME]["reading"])
    assert {terms.OPERATION, terms.OUTCOME, terms.COMMIT, terms.CHANGED} <= set(attempt.facts)
    assert terms.SUCCEEDED in attempt.allowed[terms.OUTCOME]
    attempt_states = {terms.PENDING, terms.EXECUTING, terms.COMPLETED, terms.CAPTURED, terms.CAPTURE_FAILED}
    assert attempt_states <= set(attempt.states)
    assert terms.SEALED in ree.states
    assert {terms.CAUSE, terms.KIND} <= set(receipt.facts)
    assert terms.BASELINE in receipt.allowed[terms.CAUSE]
    assert set(terms.STEP_ORDER) <= set(receipt.allowed[terms.KIND])
    assert {terms.CURRENT, terms.STALE, terms.MISSING, terms.NOT_APPLICABLE} <= set(receipt.states)
    session = entities[terms.SESSION]
    assert {terms.STORE_ID, terms.WORKBENCH_ID, terms.NONCE, terms.REASON, terms.CLOSE_CODE} <= set(session.facts)
    assert {terms.OPENED, terms.LOST} <= set(session.states)
    assert session.partition == terms.STORE_ID
    assert terms.STORE_ID in action.facts
    assert terms.SESSION_FACT in start.facts[terms.START_RUN]
    assert terms.SESSION_FACT in follow.facts[terms.FOLLOW_RUN]
    assert terms.OPERATION in start.facts[terms.START_RUN]
    assert terms.STATUS in follow.facts["settled"]
