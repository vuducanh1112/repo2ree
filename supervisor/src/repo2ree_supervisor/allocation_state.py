"""Legal lifecycle transitions for durable allocation records.

The table is the Allocation machine in specifications/behaviour, generated into
``repo2ree_protocol.behaviour``; edit the specification, not this module.
"""

from __future__ import annotations

from repo2ree_protocol.allocation import AllocationState
from repo2ree_protocol.behaviour import require_transition as require_specified_transition


def require_transition(current: AllocationState, target: AllocationState) -> None:
    require_specified_transition("Allocation", current.value, target.value)
