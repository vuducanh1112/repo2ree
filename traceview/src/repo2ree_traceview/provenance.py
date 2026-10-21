"""Why a sealed REE can be trusted: each step's evidence at seal, the operation that produced it, and its chain.

The chain runs from the receipt back to the request: the attempt that wrote it (Git), the dispatch
that started the attempt (journal), the run that dispatched it (journal), and the client request
that created the run (span). Every link carries the verdicts of the rules its own events triggered.
Built from an operation trace alone, so it can never disagree with the other views.
"""

from __future__ import annotations

from repo2ree_traceview.model import Entry, OperationTrace, RuleHit, StepChange, ViewModel

ABSENT = (None, "missing", "not_applicable")
PRESENT = ("current", "stale")


class Link(ViewModel):
    label: str
    source: str
    rules: tuple[RuleHit, ...] = ()


class StepOrigin(ViewModel):
    step: str
    standing: str  # At seal.
    produced_by: str | None = None
    change: StepChange | None = None
    commit: str | None = None
    rules: tuple[RuleHit, ...] = ()
    later: tuple[str, ...] = ()  # What happened to the evidence after it was produced, before the seal.
    chain: tuple[Link, ...] = ()
    history: tuple[str, ...] = ()  # The states it went through when it was never produced.


class Provenance(ViewModel):
    ree: str
    recording: str
    verdict: str
    commit: str | None
    seal: tuple[Link, ...]
    seal_rules: tuple[RuleHit, ...]
    standing: dict[str, str]
    steps: tuple[StepOrigin, ...]
    after_seal: int  # Attempts after sealing; sealed is terminal, so any would be a violation.


def _hits(entry: Entry, subject: str, key: str | None = None) -> tuple[RuleHit, ...]:
    return tuple(hit for hit in entry.rules if hit.subject == subject and (key is None or hit.key == key))


def chain(entry: Entry) -> tuple[Link, ...]:
    """The links that led to one entry's capture, from the attempt back to the client's request."""
    if entry.kind == "authoring":
        operations = ", ".join(f"{count}x {name}" for name, count in entry.operations.items())
        return (Link(label=f"authoring: {operations}", source="git"),)
    links: list[Link] = []
    if entry.attempt is not None:
        attempt = entry.attempt
        commit = f"@{attempt.commit[:8]}" if attempt.commit else "not captured"
        links.append(
            Link(
                label=f"attempt {attempt.key[:8]} {entry.name}: {' → '.join(attempt.states)}",
                source=f"git {commit}",
                rules=_hits(entry, "Attempt", attempt.key),
            )
        )
    if entry.dispatch is not None and entry.attempt is not None:
        dispatch = entry.dispatch
        links.append(
            Link(
                label=f"dispatch exec_action → {dispatch.outcome or 'no outcome'}",
                source=f"journal {dispatch.sent or '?'} → {dispatch.received or '?'}",
                rules=_hits(entry, "dispatch", entry.attempt.key),
            )
        )
    if entry.run is not None:
        run, states = entry.run, entry.run.states
        links.append(
            Link(
                label=f"action {run.key}: {' → '.join(s.state for s in states)}",
                source=f"journal {states[0].ref} → {states[-1].ref}" if states else "journal",
                rules=_hits(entry, "AuthorApiAction", run.key),
            )
        )
    request = _request(entry)
    if request is not None:
        links.append(Link(label=f"{request} at +{entry.start or 0:.0f} s", source="span"))
    return tuple(links)


def _request(entry: Entry) -> str | None:
    if entry.sequence is None:
        return None
    rows = entry.sequence.rows
    sent = next((r for r in rows if r.lane == "client" and r.to == "api" and r.provenance == "span"), None)
    if sent is None:
        return None
    answer = next((r for r in rows if r.lane == "api" and r.to == "client"), None)
    status = answer.label.removesuffix(" response") if answer else "?"
    return f"{sent.label} → {status}"


def build_provenance(trace: OperationTrace) -> Provenance | None:
    """None when the recording never sealed its REE."""
    standing = dict(trace.standings[0].states) if trace.standings else {}
    produced: dict[str, tuple[Entry, StepChange]] = {}
    later: dict[str, list[str]] = {}
    seal: Entry | None = None
    after = 0
    for entry in trace.entries:
        if seal is not None:
            after += entry.kind in ("operation", "authoring")
            continue
        for change in entry.changes:
            standing[change.step] = change.after
            if change.after in PRESENT and change.before in ABSENT:
                produced[change.step] = (entry, change)
                later[change.step] = []
            elif change.step in later:
                later[change.step].append(f"{change.before} → {change.after} by {entry.name}")
        if entry.ree is not None and entry.ree.after == "sealed" and entry.ree.before != "sealed":
            seal = entry
    if seal is None:
        return None
    origins = []
    for step in trace.steps:
        state = standing.get(step, "not_applicable")
        if step not in produced:
            seen = [change.after for entry in trace.entries for change in entry.changes if change.step == step]
            initial = trace.standings[0].states.get(step) if trace.standings else None
            origins.append(StepOrigin(step=step, standing=state, history=(initial or "undeclared", *seen)))
            continue
        entry, change = produced[step]
        origins.append(
            StepOrigin(
                step=step,
                standing=state,
                produced_by=entry.name,
                change=change,
                commit=entry.attempt.commit if entry.attempt else None,
                rules=tuple(hit for hit in entry.rules if hit.subject == "Step" and hit.key.endswith(f"/{step}")),
                later=tuple(later[step]),
                chain=chain(entry),
            )
        )
    return Provenance(
        ree=trace.ree,
        recording=trace.recording.name,
        verdict=trace.verdict,
        commit=seal.attempt.commit if seal.attempt else None,
        seal=chain(seal),
        seal_rules=_hits(seal, "Ree"),
        standing=standing,
        steps=tuple(origins),
        after_seal=after,
    )


MARK = {"passed": "✓", "violated": "✗", "inconclusive": "?"}


def _rules(hits: tuple[RuleHit, ...]) -> str:
    unique = dict.fromkeys((hit.rule, hit.verdict) for hit in hits)
    return "  ".join(f"{MARK[verdict]} {rule}" for rule, verdict in unique)


def render_text(provenance: Provenance) -> str:
    counts = {
        state: sum(1 for s in provenance.standing.values() if s == state) for state in ("current", "stale", "missing")
    }
    missing = [step for step, state in provenance.standing.items() if state == "missing"]
    lines = [
        f"Provenance of REE {provenance.ree[:8]} · recording {provenance.recording}",
        f"behaviour conformance: {provenance.verdict}",
        "",
        f"REE {provenance.ree[:8]}  SEALED @{(provenance.commit or '?')[:8]}",
    ]
    if text := _rules(provenance.seal_rules):
        lines.append(f"│  {text}")
    lines.append(
        f"│  at seal: {counts['current']} current · {counts['stale']} stale · {counts['missing']} missing"
        + (f" ({', '.join(missing)}): only stale evidence blocks sealing" if missing else "")
    )
    lines.append(
        f"│  after seal: {provenance.after_seal} attempts" + ("" if provenance.after_seal else " (sealed is terminal)")
    )
    lines += ["│", "│  sealing itself:", *_links(provenance.seal, "│    "), "│"]
    for index, origin in enumerate(provenance.steps):
        last = index == len(provenance.steps) - 1
        branch, pad = ("└─", "   ") if last else ("├─", "│  ")
        lines.append(
            f"{branch} {origin.step:<26} {origin.standing.upper() if origin.standing == 'current' else origin.standing}"
        )
        if origin.change is None:
            lines += [f"{pad}   never produced: {' → '.join(origin.history)}", pad]
            continue
        where = f" @{origin.commit[:8]}" if origin.commit else ""
        lines.append(
            f"{pad}   receipt produced by {origin.produced_by}{where}  "
            f"({origin.change.before or 'undeclared'} → {origin.change.after})   [git: audit around the attempt]"
        )
        if text := _rules(origin.rules):
            lines.append(f"{pad}   {text}")
        lines.append(f"{pad}   then: {', '.join(origin.later)}" if origin.later else f"{pad}   unchanged until seal")
        lines += [*_links(origin.chain, f"{pad}   "), pad]
    lines += [
        "",
        "[git] REE history and operation records · [journal] API process journal · [span] OTel, context only",
        "✓ ✗ ? are the verdicts of the rules each link's own events triggered (repo2ree_conformance)",
    ]
    return "\n".join(line.rstrip() for line in lines) + "\n"


def _links(links: tuple[Link, ...], indent: str) -> list[str]:
    lines = []
    for link in links:
        lines.append(f"{indent}← {link.label}   [{link.source}]")
        if text := _rules(link.rules):
            lines.append(f"{indent}  {text}")
    return lines
