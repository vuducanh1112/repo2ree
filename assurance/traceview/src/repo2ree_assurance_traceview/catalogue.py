"""Many behaviour traces folded into one entry per operation and outcome.

Each entry has its instances, rule tallies, a representative sequence with how many instances show each
line, and per lane the weakest reach any instance has. Lines match once ids, durations, and counts are
masked; lines placed by time alone are requests before the operation and are left out.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from repo2ree_assurance_traceview.model import BehaviourTrace, Entry, Lane, Provenance, Row, ViewModel
from repo2ree_assurance_traceview.sequence import LANES

FORMAT: Final = "repo2ree-operations/1"

type Reach = Literal["checked", "exchanged", "span", "none"]
_WEAKEST_FIRST: tuple[Reach, ...] = ("none", "span", "exchanged", "checked")
_STRENGTH: dict[Reach, int] = {reach: strength for strength, reach in enumerate(_WEAKEST_FIRST)}
_CHECKED: frozenset[Provenance] = frozenset({"journal", "git", "inferred"})  # Inferred are Git records too.
_MASKS = (
    re.compile(r"\b[0-9a-f]{7,}\b"),
    re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|s)\b"),
    re.compile(r"\b\d+x\b"),
)


class Line(ViewModel):
    lane: str
    to: str | None = None
    label: str  # Masked.
    provenance: Provenance
    t: float  # Seconds from the operation's first line.
    seen: int  # Instances that show the line.


class Instance(ViewModel):
    source: str  # The verification as given.
    test: str | None
    ree: str
    outcome: str | None
    duration: float | None
    verdict: str  # The whole dossier's.


class Tally(ViewModel):
    rule: str
    passed: int = 0
    violated: int = 0
    inconclusive: int = 0


class Operation(ViewModel):
    name: str
    outcome: str | None
    kind: Literal["setup", "operation"]
    instances: tuple[Instance, ...]
    representative: int  # Index of the instance of median duration.
    lines: tuple[Line, ...]
    elsewhere: tuple[Line, ...]  # Lines only other instances show.
    reach: dict[str, Reach]
    rules: tuple[Tally, ...]


class Undrawn(ViewModel):
    source: str
    test: str | None = None
    verdict: str | None = None
    reason: str


class OperationCatalogue(ViewModel):
    format: Literal["repo2ree-operations/1"] = FORMAT
    lanes: tuple[Lane, ...]
    operations: tuple[Operation, ...]
    undrawn: tuple[Undrawn, ...] = ()


def mask(label: str) -> str:
    for pattern in _MASKS:
        label = pattern.sub("…", label)
    return label


type _Key = tuple[str, str | None, Provenance, str, int]


def _keyed(rows: Iterable[Row]) -> list[tuple[_Key, Row]]:
    repeats: Counter[tuple[str, str | None, Provenance, str]] = Counter()
    keyed: list[tuple[_Key, Row]] = []
    for row in rows:
        if row.provenance == "time":
            continue
        shape = (row.lane, row.to, row.provenance, mask(row.label))
        keyed.append(((*shape, repeats[shape]), row))
        repeats[shape] += 1
    return keyed


@dataclass(frozen=True)
class _Seen:
    instance: Instance
    entry: Entry
    position: float  # In its trace, from 0 (first) to 1 (last).
    rows: list[tuple[_Key, Row]]

    @classmethod
    def of(cls, instance: Instance, entry: Entry, position: float) -> _Seen:
        return cls(instance, entry, position, _keyed(entry.sequence.rows if entry.sequence else ()))


def _line(key: _Key, t: float, seen: int) -> Line:
    lane, to, provenance, label, _ = key
    return Line(lane=lane, to=to, provenance=provenance, label=label, t=round(t, 3), seen=seen)


def _representative(seen: list[_Seen]) -> int:
    candidates = sorted((s.instance.duration or 0.0, index) for index, s in enumerate(seen))
    return candidates[(len(candidates) - 1) // 2][1]


def _reached(row: Row) -> Reach:
    """What a line shows of the lanes it touches: a note its own, a message both ends."""
    if row.to is None:
        return "checked" if row.provenance in _CHECKED else "span" if row.provenance == "span" else "none"
    return "exchanged" if row.provenance in _CHECKED else "span"


def _reach(seen: list[_Seen]) -> dict[str, Reach]:
    weakest = {lane.id: _STRENGTH["checked"] for lane in LANES}
    for one in seen:
        strongest: dict[str, int] = defaultdict(int)
        for _, row in one.rows:
            for lane in (row.lane,) if row.to is None else (row.lane, row.to):
                strongest[lane] = max(strongest[lane], _STRENGTH[_reached(row)])
        for lane in weakest:
            weakest[lane] = min(weakest[lane], strongest[lane])
    return {lane: _WEAKEST_FIRST[strength] for lane, strength in weakest.items()}


def _tally(seen: list[_Seen]) -> tuple[Tally, ...]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for one in seen:
        for hit in one.entry.rules:
            counts[hit.rule][hit.verdict] += 1
    return tuple(
        Tally(rule=rule, passed=c["passed"], violated=c["violated"], inconclusive=c["inconclusive"])
        for rule, c in sorted(counts.items())
    )


def _operation(name: str, outcome: str | None, seen: list[_Seen]) -> Operation:
    seen = sorted(seen, key=lambda s: (s.instance.source, s.instance.ree, s.position))
    chosen = _representative(seen)
    shown: Counter[_Key] = Counter()
    times: dict[_Key, list[float]] = defaultdict(list)
    for one in seen:
        rows = one.rows
        origin = rows[0][1].t if rows else 0.0
        for key, row in rows:
            shown[key] += 1
            times[key].append(row.t - origin)
    own = seen[chosen].rows
    origin = own[0][1].t if own else 0.0
    lines = tuple(_line(key, row.t - origin, shown[key]) for key, row in own)
    mine = {key for key, _ in own}
    others = (_line(key, statistics.median(times[key]), n) for key, n in shown.items() if key not in mine)
    elsewhere = tuple(sorted(others, key=lambda line: (line.t, line.lane, line.label)))
    return Operation(
        name=name,
        outcome=outcome,
        kind="setup" if seen[0].entry.kind == "setup" else "operation",
        instances=tuple(s.instance for s in seen),
        representative=chosen,
        lines=lines,
        elsewhere=elsewhere,
        reach=_reach(seen),
        rules=_tally(seen),
    )


def build_catalogue(
    traces: Iterable[tuple[str, BehaviourTrace]], undrawn: Iterable[Undrawn] = ()
) -> OperationCatalogue:
    """Operations in their usual order in a trace, each one's outcomes from most to least common."""
    by_name: dict[str, list[_Seen]] = defaultdict(list)
    for source, trace in traces:
        drawn = [entry for entry in trace.entries if entry.kind != "authoring"]
        for index, entry in enumerate(drawn):
            instance = Instance(
                source=source,
                test=trace.dossier.test,
                ree=trace.ree,
                outcome=entry.outcome,
                duration=None if entry.start is None or entry.end is None else round(entry.end - entry.start, 3),
                verdict=trace.verdict,
            )
            by_name[entry.name].append(_Seen.of(instance, entry, index / max(len(drawn) - 1, 1)))
    order = sorted(by_name, key=lambda name: (statistics.fmean(s.position for s in by_name[name]), name))
    variants: list[Operation] = []
    for name in order:
        by_outcome: dict[str | None, list[_Seen]] = defaultdict(list)
        for one in by_name[name]:
            by_outcome[one.instance.outcome].append(one)
        ranked = sorted(by_outcome.items(), key=lambda item: (-len(item[1]), item[0] or ""))
        variants += [_operation(name, outcome, seen) for outcome, seen in ranked]
    return OperationCatalogue(lanes=LANES, operations=tuple(variants), undrawn=tuple(undrawn))
