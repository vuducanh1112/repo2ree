"""Legal lifecycle transitions for durable allocation records.

The supervisor's own table: the store refuses any other edge. The specification
(assurance/spec/entities/allocation.toml) states the machine the checker
holds the journal to; keeping that and this table in agreement is the checker's job,
so a change to the specification never changes what the supervisor does by itself.
"""

from __future__ import annotations

from repo2ree_protocol.allocation import AllocationState as S


class IllegalTransitionError(ValueError):
    pass


EDGES: dict[S, frozenset[S]] = {
    # Provider-managed allocations provision; externally managed ones wait for their bench. One the API
    # restarted before setting up any further fails.
    S.REQUESTED: frozenset({S.PROVISIONING, S.WAITING_FOR_WORKBENCH, S.FAILED}),
    # Setting up a bench either goes on or fails; a restart meanwhile fails it too.
    S.PROVISIONING: frozenset({S.WAITING_FOR_WORKBENCH, S.FAILED}),
    S.WAITING_FOR_WORKBENCH: frozenset({S.READY, S.FAILED}),
    S.READY: frozenset({S.ASSIGNED, S.FAILED}),
    # Only a bench that holds an REE is asked about, so only it is found lost.
    S.ASSIGNED: frozenset({S.DRAINING, S.LOST}),
    # A release the provider could not carry out leaves the allocation failed, to be released again.
    S.DRAINING: frozenset({S.RELEASED, S.FAILED}),
    # A failed or lost allocation is still released.
    S.FAILED: frozenset({S.DRAINING}),
    S.LOST: frozenset({S.DRAINING}),
    S.RELEASED: frozenset(),
}


def require_transition(current: S, target: S) -> None:
    """Refuse an edge the table does not hold; staying put is always allowed."""
    if current != target and target not in EDGES[current]:
        raise IllegalTransitionError(f"illegal allocation transition {current.value} -> {target.value}")
