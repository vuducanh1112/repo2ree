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
    # Provider-managed allocations provision; externally managed ones wait for their bench.
    S.REQUESTED: frozenset({S.PROVISIONING, S.WAITING_FOR_WORKBENCH, S.DRAINING, S.FAILED}),
    S.PROVISIONING: frozenset({S.WAITING_FOR_WORKBENCH, S.DRAINING, S.FAILED, S.LOST}),
    S.WAITING_FOR_WORKBENCH: frozenset({S.READY, S.DRAINING, S.FAILED, S.LOST}),
    S.READY: frozenset({S.ASSIGNED, S.DRAINING, S.FAILED, S.LOST}),
    S.ASSIGNED: frozenset({S.DRAINING, S.FAILED, S.LOST}),
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
