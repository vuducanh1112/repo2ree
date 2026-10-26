"""The REE's change history as the verifier replayed it, in the order it drew its parts."""

from __future__ import annotations

from repo2ree_assurance_checker.verification import AggregateHistory, Part
from repo2ree_assurance_traceview.model import ChangeHistory, HistoryRow, HistoryStep


def change_history(replayed: AggregateHistory) -> ChangeHistory:
    return ChangeHistory(
        rows=tuple(HistoryRow(part=p.name, label=_label(p), kind=p.kind, group=p.group) for p in replayed.parts),
        steps=tuple(
            HistoryStep(operation=step.operation, ref=step.ref, states=step.states, moved=step.moved)
            for step in replayed.steps
        ),
    )


def _label(part: Part) -> str:
    """A receipt beside what it is about reads as "receipt"; a field without the definition's prefix."""
    name = "receipt" if part.kind == "receipt" else part.machine.removeprefix("definition.").removesuffix("[*]")
    return f"{name}[{part.item}]" if part.item else name
