"""Draw the behaviour specification's machines for the overview (``just generate-spec-diagrams``).

From the specification as exported (reports/exports/spec.json) and this tree's assessment of the
assurance-gate receipt's runs (reports/behaviour/), it writes under reports/diagrams/spec/: the
system map (system.svg), each machine as the specification allows it (machines/), each machine
with how often the receipt's tests took each edge (coverage/), and each part of an aggregate with
the operations that moved it (aggregates/).
It prints each file it wrote, for the recipe to stamp.

    python -m repo2ree_repoview spec-diagrams --spec reports/exports/spec.json -o reports/diagrams/spec
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from repo2ree_repoview.overview.drawing import machine_svg, submachine_svg, system_svg
from repo2ree_repoview.overview.exports import EXPORTS, Spec
from repo2ree_repoview.overview.figures import DIAGRAMS
from repo2ree_repoview.overview.receipt import (
    REPORTS,
    AggregateMoves,
    Evidence,
    Exercised,
    gate_runs,
    read_receipt,
    unreached,
)

SYSTEM = "spec/system.svg"


def machine_drawing(entity: str) -> str:
    return f"spec/machines/{entity}.svg"


def coverage_drawing(entity: str) -> str:
    return f"spec/coverage/{entity}.svg"


def part_drawing(aggregate: str, part: str) -> str:
    """A part's drawing; its name, ``definition.experiments[*]`` say, made safe for a file."""
    return f"spec/aggregates/{aggregate}/{re.sub(r'[^A-Za-z0-9._-]+', '-', part).strip('-')}.svg"


def drawings(spec: Spec, evidence: Evidence, excused: dict[str, str]) -> dict[str, str]:
    """Every drawing, by its path under reports/diagrams/."""
    edges = Exercised.over(evidence).edges
    drawn = {SYSTEM: system_svg(spec)}
    for name, entity in spec.entities.items():
        if entity.constrained:
            drawn[machine_drawing(name)] = machine_svg(spec, name)
            drawn[coverage_drawing(name)] = machine_svg(spec, name, edges, excused)
    for name, aggregate in spec.aggregates.items():
        moves = AggregateMoves.over(evidence, name)
        parts = {part_drawing(name, machine.name): machine for machine in aggregate.machines}
        if len(parts) != len(aggregate.machines):
            raise ValueError(f"two parts of {name} would share a drawing")
        drawn |= {path: submachine_svg(machine, moves.of(machine.name)) for path, machine in parts.items()}
    return drawn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--spec", type=Path, default=EXPORTS / "spec.json", help="the specification as exported")
    parser.add_argument("-o", "--output", type=Path, default=DIAGRAMS / "spec", help="where the drawings go")
    args = parser.parse_args()
    spec = Spec.model_validate_json(args.spec.read_text(encoding="utf-8"))
    # This tree's assessment of the receipt's runs, as assess-behaviour reported it.
    evidence = Evidence(runs=tuple(REPORTS / run.name for run, _ in gate_runs(read_receipt())))
    drawn = drawings(spec, evidence, unreached())
    for stale in args.output.rglob("*.svg") if args.output.is_dir() else ():
        stale.unlink()
    for relative, svg in drawn.items():
        path = args.output / Path(relative).relative_to("spec")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(svg, encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
