from __future__ import annotations

from repo2ree_repoview.overview.exports import Invariant, Source, Spec
from repo2ree_repoview.overview.html import Page, esc, rule_link, section, table
from repo2ree_repoview.overview.pages.aggregate import slug, title
from repo2ree_repoview.repository import Commit

SPEC_CORE_PAGE = "specification-core"
SPECIFICATION = "specification"


def entity_is_core(spec: Spec, entity: str) -> bool:
    return entity in spec.cli_core.entities


def boundary_is_core(spec: Spec, boundary: str) -> bool:
    return boundary in spec.cli_core.boundaries


def invariant_is_core(spec: Spec, invariant: Invariant) -> bool:
    return invariant.id in spec.cli_core.rules


def _rules(found: list[Invariant]) -> str:
    rows = [[rule_link(i.id), f"<code>{esc(i.pattern)}</code>", esc(i.summary)] for i in found]
    return table(["Rule", "Pattern", "Meaning"], rows)


def _machines(spec: Spec) -> str:
    aggregated = {aggregate.name: aggregate for aggregate in spec.aggregates.values()}
    rows = []
    for name, entity in sorted(spec.entities.items()):
        if not entity_is_core(spec, name):
            continue
        if name in aggregated:
            aggregate = aggregated[name]
            kinds = [machine.kind for machine in aggregate.machines]
            parts = ", ".join(
                f"{kinds.count(kind)} {kind}" for kind in ("lifecycle", "field", "receipt") if kind in kinds
            )
            page = f'<a href="{slug(aggregate)}.html">{esc(title(aggregate))}</a>'
            judged = f"{rule_link(f'aggregate:{name}')} ({parts}; {page})"
        elif entity.constrained:
            judged = rule_link(f"machine:{name}")
        else:
            judged = '<span class="muted">no machine; only its invariants</span>'
        states = " · ".join(f"<code>{esc(state)}</code>" for state in entity.states)
        rows.append([f"<code>{esc(name)}</code>", esc(entity.owner), esc(entity.summary), states, judged])
    return table(["Entity", "Owner", "Summary", "States", "Judged by"], rows)


def _documents(spec: Spec) -> str:
    out = []
    for name, rules in spec.documents.items():
        rows = [
            [rule_link(f"document:{rule.id}"), f"<code>{esc(rule.pattern)}</code>", esc(rule.summary)]
            for rule in rules.rules
        ]
        out.append(f"<h4>{esc(name)} ({len(rows)})</h4>" + table(["Rule", "Pattern", "Meaning"], rows))
    return "".join(out)


def _boundaries(spec: Spec) -> str:
    rows = [
        [
            f"<code>{esc(name)}</code>",
            f"{esc(boundary.sender)} → {esc(boundary.receiver)}",
            esc(boundary.summary),
            " · ".join(f"<code>{esc(message)}</code>" for message in boundary.messages),
        ]
        for name, boundary in sorted(spec.boundaries.items())
        if boundary_is_core(spec, name)
    ]
    return table(["Boundary", "Between", "Summary", "Messages"], rows)


def core_names(spec: Spec) -> set[str]:
    return {
        *(name for name in spec.entities if entity_is_core(spec, name)),
        *(name for name in spec.boundaries if boundary_is_core(spec, name)),
        *spec.documents,
        *(invariant.id for invariant in spec.invariants if invariant_is_core(spec, invariant)),
        *spec.cli_core.components,
    }


def _declared_here(spec: Spec, source: Source, names: set[str]) -> tuple[str, ...]:
    match source.kind:
        case "vocabulary":
            shared = tuple(name for name in source.names if name not in spec.entities and name not in spec.boundaries)
            return shared or tuple(name for name in source.names if name in names)
        case _:
            return tuple(name for name in source.names if name in names)


def _declares(source: Source, here: tuple[str, ...]) -> str:
    if source.kind == "invariants":
        return f"{len(here)} of its {len(source.names)} rules"
    return " · ".join(f"<code>{esc(name)}</code>" for name in here)


def _commits(history: tuple[Commit, ...]) -> str:
    if not history:
        return '<span class="muted">not committed</span>'
    listed = "".join(
        f"<li><code>{esc(commit.revision[:8])}</code> {esc(commit.committed[:10])} {esc(commit.subject)}</li>"
        for commit in history
    )
    newest = f"{len(history)}, newest {esc(history[0].committed[:10])}"
    return f"<details><summary>{newest}</summary><ul>{listed}</ul></details>"


def _sources(spec: Spec, histories: dict[str, tuple[Commit, ...]]) -> str:
    names = core_names(spec)
    rows = [
        [f"<code>{esc(source.path)}</code>", _declares(source, here), _commits(histories.get(source.path, ()))]
        for source in spec.sources
        if (here := _declared_here(spec, source, names))
    ]
    return table(["File", "Declares", "Commits"], rows)


def core_teaser(spec: Spec) -> str:
    core = sum(invariant_is_core(spec, invariant) for invariant in spec.invariants)
    documented = sum(len(rules.rules) for rules in spec.documents.values())
    entities = sum(entity_is_core(spec, name) for name in spec.entities)
    return f"{core + documented} rules, {entities} entities"


def page_specification_core(spec: Spec, histories: dict[str, tuple[Commit, ...]]) -> Page:
    core = [invariant for invariant in spec.invariants if invariant_is_core(spec, invariant)]
    documented = sum(len(rules.rules) for rules in spec.documents.values())
    entities = sum(entity_is_core(spec, name) for name in spec.entities)
    lede = (
        "The part of the specification about the product a person meets at the command line: <code>ree</code> run by "
        "whatever acts on the REE (the <i>environment</i>), and <i>core</i>, which owns the REE and its history. "
        "An entity belongs here when one of the two owns it, a boundary when it runs between them, and a rule when "
        "everything it names does."
    )
    body = (
        f"<h3>Rules across entities ({len(core)})</h3>" + _rules(core) + f"<h3>Rules on one commit ({documented})</h3>"
        '<p class="lede">Each reads one capture commit alone: its document and the files it holds.</p>'
        + _documents(spec)
        + f"<h3>Entities ({entities})</h3>"
        '<p class="lede">The REE and a review are judged part by part: their lifecycle, one machine per field of '
        "their document, and one per receipt, each drawn on its own page.</p>"
        + _machines(spec)
        + "<h3>Boundaries</h3>"
        + _boundaries(spec)
        + "<h3>Sources</h3>"
        '<p class="lede">The files under <code>assurance/spec/</code> these come from, and the commits that changed '
        "each, newest first and across renames.</p>" + _sources(spec, histories)
    )
    trail = f'<p class="muted"><a href="{SPECIFICATION}.html">Specification</a> /</p>'
    return Page(
        SPEC_CORE_PAGE, "CLI ↔ Core", core_teaser(spec), trail + section(SPEC_CORE_PAGE, "CLI ↔ Core", lede, body)
    )
