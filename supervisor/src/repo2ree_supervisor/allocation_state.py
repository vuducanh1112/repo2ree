"""Legal lifecycle transitions for durable allocation records."""

from __future__ import annotations

from repo2ree_protocol.allocation import AllocationState

_TRANSITIONS: dict[AllocationState, frozenset[AllocationState]] = {
    AllocationState.REQUESTED: frozenset(
        {
            AllocationState.PROVISIONING,
            AllocationState.WAITING_FOR_WORKBENCH,
            AllocationState.DRAINING,
            AllocationState.FAILED,
        }
    ),
    AllocationState.PROVISIONING: frozenset(
        {AllocationState.WAITING_FOR_WORKBENCH, AllocationState.DRAINING, AllocationState.FAILED, AllocationState.LOST}
    ),
    AllocationState.WAITING_FOR_WORKBENCH: frozenset(
        {
            AllocationState.READY,
            AllocationState.DRAINING,
            AllocationState.FAILED,
            AllocationState.LOST,
        }
    ),
    AllocationState.READY: frozenset(
        {AllocationState.ASSIGNED, AllocationState.DRAINING, AllocationState.FAILED, AllocationState.LOST}
    ),
    AllocationState.ASSIGNED: frozenset({AllocationState.DRAINING, AllocationState.FAILED, AllocationState.LOST}),
    AllocationState.DRAINING: frozenset({AllocationState.RELEASED, AllocationState.FAILED}),
    AllocationState.RELEASED: frozenset(),
    AllocationState.FAILED: frozenset({AllocationState.DRAINING}),
    AllocationState.LOST: frozenset({AllocationState.DRAINING}),
}


def require_transition(current: AllocationState, target: AllocationState) -> None:
    if current == target:
        return
    if target not in _TRANSITIONS[current]:
        raise ValueError(f"illegal allocation transition {current.value} -> {target.value}")
