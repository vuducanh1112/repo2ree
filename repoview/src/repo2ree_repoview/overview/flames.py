from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from repo2ree_repoview.diagrams.recipes import Recipe
from repo2ree_repoview.overview.html import esc
from repo2ree_repoview.overview.timings import Invocation

GATES = ("commit-gate", "assurance-gate")
WINDOW = timedelta(days=14)
WIDTH, ROW, CHARACTER = 1000, 22, 6.7

type Totals = dict[tuple[str, ...], float]


@dataclass(frozen=True)
class Frame:
    path: tuple[str, ...]
    start: float
    cost: float
    own: float


@dataclass(frozen=True)
class Flames:
    command: str
    machine: str
    frames: tuple[Frame, ...]
    runs: int


def _own(invocation: Invocation) -> dict[str, float]:
    found: dict[str, float] = {}
    for completed in invocation.recipes:
        found.setdefault(completed.recipe, completed.seconds)
    return found


def _reaches(name: str, ran: dict[str, float], recipes: dict[str, Recipe], seen: frozenset[str] = frozenset()) -> bool:
    if name in seen or name not in recipes:
        return False
    return any(
        dependency.recipe in ran or _reaches(dependency.recipe, ran, recipes, seen | {name})
        for dependency in recipes[name].dependencies
    )


def _tree(root: str, ran: dict[str, float], recipes: dict[str, Recipe]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = defaultdict(list)
    placed = {root}

    def walk(name: str) -> None:
        for dependency in recipes[name].dependencies if name in recipes else ():
            needed = dependency.recipe in ran or _reaches(dependency.recipe, ran, recipes)
            if needed and dependency.recipe not in placed:
                placed.add(dependency.recipe)
                children[name].append(dependency.recipe)
                walk(dependency.recipe)

    walk(root)
    children[root].extend(name for name in ran if name not in placed)
    return children


def _cost(
    path: tuple[str, ...], ran: dict[str, float], children: dict[str, list[str]], work: Totals, owns: Totals
) -> float:
    own = ran.get(path[-1], 0.0)
    total = own + sum(_cost((*path, child), ran, children, work, owns) for child in children[path[-1]])
    work[path] += total
    owns[path] += own
    return total


def flame_graph(invocations: Sequence[Invocation], recipes: dict[str, Recipe]) -> tuple[Frame, ...]:
    work: Totals = defaultdict(float)
    owns: Totals = defaultdict(float)
    for invocation in invocations:
        root = invocation.start.argv[0]
        ran = _own(invocation)
        _cost((root,), ran, _tree(root, ran, recipes), work, owns)
    runs = max(1, len(invocations))
    frames: list[Frame] = []

    def place(path: tuple[str, ...], start: float) -> None:
        frames.append(Frame(path, start, work[path] / runs, owns[path] / runs))
        offset = start + owns[path] / runs
        inner = [other for other in work if len(other) == len(path) + 1 and other[: len(path)] == path]
        for child in sorted(inner, key=lambda child: -work[child]):
            place(child, offset)
            offset += work[child] / runs

    for top in [path for path in work if len(path) == 1]:
        place(top, 0.0)
    return tuple(frames)


def _started(invocation: Invocation) -> float:
    return datetime.fromisoformat(invocation.start.started).timestamp()


def flames(invocations: Sequence[Invocation], recipes: dict[str, Recipe]) -> tuple[Flames, ...]:
    found = []
    for command in GATES:
        green = [
            invocation
            for invocation in invocations
            if invocation.start.argv[:1] == (command,) and invocation.end is not None and invocation.end.exit == 0
        ]
        if not green or command not in recipes:
            continue
        machine = Counter(invocation.start.machine for invocation in green).most_common(1)[0][0]
        on_machine = [invocation for invocation in green if invocation.start.machine == machine]
        since = _started(on_machine[-1]) - WINDOW.total_seconds()
        window = [invocation for invocation in on_machine if _started(invocation) >= since]
        found.append(Flames(command, machine, flame_graph(window, recipes), len(window)))
    return tuple(found)


def seconds(value: float) -> str:
    return f"{value:.1f} s" if value < 10 else f"{value:.0f} s"


def _fitted(label: str, width: float) -> str:
    room = int((width - 8) / CHARACTER)
    if room >= len(label):
        return label
    return label[: room - 1] + "…" if room >= 4 else ""


def _bar(x: float, y: float, width: float, label: str, tip: str) -> str:
    shown = _fitted(label, width)
    text = f'<text x="{x + 4:.1f}" y="{y + ROW / 2 + 4:.1f}" class="flame-label">{esc(shown)}</text>' if shown else ""
    return (
        f'<g class="flame-bar"><title>{esc(tip)}</title>'
        f'<rect x="{x:.1f}" y="{y + 1:.1f}" width="{max(width - 2, 1):.1f}" height="{ROW - 2}" rx="3"/>{text}</g>'
    )


def graph_svg(found: Flames) -> str:
    total = max((frame.cost for frame in found.frames if len(frame.path) == 1), default=0.0) or 1.0
    scale = WIDTH / total
    bars = []
    for frame in found.frames:
        share = frame.cost / total * 100
        tip = (
            f"{' > '.join(frame.path)}: {seconds(frame.cost)} of work per run ({share:.0f}%), "
            f"{seconds(frame.own)} its own"
        )
        bars.append(_bar(frame.start * scale, (len(frame.path) - 1) * ROW, frame.cost * scale, frame.path[-1], tip))
    height = max(len(frame.path) for frame in found.frames) * ROW + 4
    return (
        f'<div class="flame-panel"><svg class="flame" viewBox="0 0 {WIDTH} {height}" role="img" '
        f'aria-label="flamegraph of just {esc(found.command)}">{"".join(bars)}</svg></div>'
    )
