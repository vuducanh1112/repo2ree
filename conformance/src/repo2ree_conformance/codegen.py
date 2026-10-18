"""Render the runtime's view of the specification as a Python module.

The output is already in ruff's format (double quotes, one item per line, magic
trailing commas), so formatting the tree never makes the module look stale.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from repo2ree_conformance.spec import Spec


def _quote(value: str) -> str:
    return json.dumps(value)


def _block(opening: str, items: Iterable[str], closing: str, indent: int) -> list[str]:
    pad = " " * indent
    rendered = list(items)
    if not rendered:
        return [f"{pad}{opening}{closing}"]
    return [f"{pad}{opening}", *(f"{pad}    {item}," for item in rendered), f"{pad}{closing}"]


def _strings(opening: str, values: Iterable[str], indent: int, *, ordered: bool = False) -> list[str]:
    items = [_quote(value) for value in (values if ordered else sorted(values))]
    pad = " " * indent
    if opening.endswith("frozenset("):
        if not items:
            return [pad + opening + "),"]
        return [pad + opening, *_block("{", items, "}", indent + 4), pad + "),"]
    return _block(opening, items, "),", indent)


def render_machines(spec: Spec) -> str:
    lines = [
        '"""Behaviour machines and boundaries, generated from specifications/behaviour. Do not edit.',
        "",
        "Regenerate with ``python -m repo2ree_conformance generate``; a test fails while this",
        "module disagrees with the specification it was generated from.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from repo2ree_protocol.behaviour.model import BoundaryShape, MachineShape",
        "",
        f"SPEC_DIGEST = {_quote(spec.digest)}",
        "",
        "MACHINES: dict[str, MachineShape] = {",
    ]
    for name, entity in sorted(spec.entities.items()):
        lines += [
            f"    {_quote(name)}: MachineShape(",
            f"        name={_quote(name)},",
            f"        owner={_quote(entity.owner)},",
            *_strings("initial=frozenset(", entity.initial, 8),
            *_strings("states=(", entity.states, 8, ordered=True),
            *_strings("terminal=frozenset(", entity.terminal, 8),
            *_strings("facts=frozenset(", entity.facts, 8),
            "        edges={",
        ]
        for state, targets in entity.edges.items():
            lines += _strings(f"{_quote(state)}: frozenset(", targets, 12)
        lines += ["        },", "    ),"]
    lines += ["}", "", "BOUNDARIES: dict[str, BoundaryShape] = {"]
    for name, boundary in sorted(spec.boundaries.items()):
        lines += [
            f"    {_quote(name)}: BoundaryShape(",
            f"        name={_quote(name)},",
            f"        sender={_quote(boundary.sender)},",
            f"        request={_quote(boundary.request)},",
            *_strings("responses=frozenset(", boundary.responses, 8),
            "    ),",
        ]
    lines += ["}", ""]
    return "\n".join(lines)
