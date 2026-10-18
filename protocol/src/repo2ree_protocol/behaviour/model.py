"""Shapes of the generated behaviour machines; the values live in ``machines.py``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MachineShape:
    name: str
    owner: str
    initial: frozenset[str]
    states: tuple[str, ...]
    terminal: frozenset[str]
    facts: frozenset[str]
    edges: dict[str, frozenset[str]]

    def allows(self, current: str | None, target: str) -> bool:
        if current is None:
            return target in self.initial
        return target in self.edges.get(current, frozenset())


@dataclass(frozen=True)
class BoundaryShape:
    name: str
    sender: str
    request: str
    responses: frozenset[str]
