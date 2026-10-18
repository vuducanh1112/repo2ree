"""Runtime side of the behaviour specification in ``specifications/behaviour``.

``machines`` is generated from the specification. Owners enforce their machine
with ``require_transition`` where they already refuse illegal states, and record
every change with ``journal()``; ``repo2ree_conformance`` checks the records.
"""

from repo2ree_protocol.behaviour.machines import BOUNDARIES, MACHINES, SPEC_DIGEST
from repo2ree_protocol.behaviour.model import BoundaryShape, MachineShape
from repo2ree_protocol.behaviour.writer import Journal, close_journal, journal, open_journal


class IllegalTransitionError(ValueError):
    pass


def require_transition(machine: str, current: str, target: str) -> None:
    """Refuse an edge the specification does not declare; staying put is always allowed."""
    if current == target:
        return
    if not MACHINES[machine].allows(current, target):
        raise IllegalTransitionError(f"illegal {machine.lower()} transition {current} -> {target}")


__all__ = [
    "BOUNDARIES",
    "MACHINES",
    "SPEC_DIGEST",
    "BoundaryShape",
    "IllegalTransitionError",
    "Journal",
    "MachineShape",
    "close_journal",
    "journal",
    "open_journal",
    "require_transition",
]
