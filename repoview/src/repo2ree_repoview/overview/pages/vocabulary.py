"""What owners record, drawn as declarations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from repo2ree_repoview.overview.exports import Spec
from repo2ree_repoview.overview.html import esc, section, table

TYPES = {"str": "str", "str?": "str | None", "bool": "bool", "bool?": "bool | None", "int": "int", "int?": "int | None"}


@dataclass
class Line:
    """One line of a rendered declaration: its plain text (to align comments), its markup, and a comment."""

    text: str
    markup: str = ""
    note: str = ""


def code(lines: list[Line]) -> str:
    noted = [len(line.text) for line in lines if line.note]
    column = min(max(noted, default=0), 44) + 2
    rendered = []
    for line in lines:
        markup = line.markup or esc(line.text)
        if line.note:
            pad = " " * max(column - len(line.text), 2)
            markup += f'{pad}<span class="c"># {esc(line.note)}</span>'
        rendered.append(markup)
    return '<pre class="code">' + "\n".join(rendered) + "</pre>"


def kw(word: str) -> str:
    return f'<span class="k">{esc(word)}</span>'


def quoted(value: str) -> str:
    return f'<span class="s">"{esc(value)}"</span>'


def required_note(states: list[str], everywhere: list[str]) -> str:
    if not states:
        return ""
    return "required" if set(states) == set(everywhere) else "required in " + ", ".join(states)


def entity_code(spec: Spec, name: str) -> str:
    entity = spec.entities[name]
    source = "witnessed from Git" if entity.evidence == "git" else "from its journal"
    lines = [
        Line(
            f"# owned by {entity.owner} · {source} · keyed by {entity.key} · partitioned by {entity.partition}",
            f'<span class="c"># owned by {esc(entity.owner)} · {source} · keyed by {esc(entity.key)} · '
            f"partitioned by {esc(entity.partition)}</span>",
        ),
        Line(f"class {name}(Entity):", f"{kw('class')} <b>{esc(name)}</b>(Entity):"),
        Line(f'    """{entity.summary}"""', f'    <span class="s">"""{esc(entity.summary)}"""</span>'),
        Line("    state: Literal[", f"    state: {kw('Literal')}["),
    ]
    lines += [
        Line(f'        "{state}",', f"        {quoted(state)},", description)
        for state, description in entity.states.items()
    ]
    lines.append(Line("    ]"))
    states = list(entity.states)
    for fact, kind in entity.facts.items():
        where = [state for state in states if fact in entity.required.get(state, ())]
        note = required_note(where, states)
        if fact not in entity.meanings:
            lines.append(Line(f"    {fact}: {TYPES[kind]}", note=note))
            continue
        optional = " | None" if kind.endswith("?") else ""
        lines.append(Line(f"    {fact}: Literal[", f"    {esc(fact)}: {kw('Literal')}[", note))
        lines += value_lines(entity.meanings[fact], entity.groups.get(fact, {}))
        lines.append(Line(f"    ]{optional}"))
    return code(lines)


def value_lines(meanings: dict[str, str], groups: dict[str, tuple[str, ...]]) -> list[Line]:
    """A fact's listed values with what each means, under a comment naming each group."""
    sections = list(groups.items()) or [("", tuple(meanings))]
    lines: list[Line] = []
    for group, values in sections:
        if group:
            lines.append(Line(f"        # {group}", f'        <span class="c"># {esc(group)}</span>'))
        lines += [Line(f'        "{value}",', f"        {quoted(value)},", meanings[value]) for value in values]
    return lines


def boundary_code(spec: Spec, name: str) -> str:
    boundary = spec.boundaries[name]
    header = (
        f"# sent by {boundary.sender} to {boundary.receiver} · recorded by the sender · "
        f"keyed by {boundary.key} · partitioned by {boundary.partition}"
    )
    lines = [
        Line(header, f'<span class="c">{esc(header)}</span>'),
        Line(f"class {name}(Boundary):", f"{kw('class')} <b>{esc(name)}</b>(Boundary):"),
        Line(f'    """{boundary.summary}"""', f'    <span class="s">"""{esc(boundary.summary)}"""</span>'),
    ]
    for message, description in boundary.messages.items():
        role = "Request" if message == boundary.request else "Response"
        facts = boundary.facts.get(message, {})
        opening = f"    class {message}({role}):"
        markup = f"    {kw('class')} <b>{esc(message)}</b>({role}):"
        if not facts:
            lines.append(Line(opening + " ...", markup + " ...", description))
            continue
        lines.append(Line(opening, markup, description))
        required = boundary.required.get(message, ())
        lines += [
            Line(f"        {fact}: {TYPES[kind]}", note="required" if fact in required else "")
            for fact, kind in facts.items()
        ]
    abandon = "    class abandoned(Outcome): ..."
    lines.append(
        Line(
            abandon, f"    {kw('class')} <b>abandoned</b>(Outcome): ...", "the sender stopped waiting; carries a reason"
        )
    )
    return code(lines)


def page_vocabulary(spec: Spec) -> str:
    processes: dict[str, list[str]] = defaultdict(list)
    for component in spec.components.values():
        processes[component.process].append(component.name)
    process_rows = [
        [
            f"<code>{esc(process)}</code>",
            "<br>".join(
                f"<code>{esc(member)}</code> <span class='muted'>{esc(spec.components[member].summary)}</span>"
                for member in sorted(members)
            ),
        ]
        for process, members in sorted(processes.items())
    ]
    entities = "".join(f'<div class="decl">{entity_code(spec, name)}</div>' for name in sorted(spec.entities))
    boundaries = "".join(f'<div class="decl">{boundary_code(spec, name)}</div>' for name in sorted(spec.boundaries))
    body = (
        "<h3>Processes</h3>"
        '<p class="lede">A journal speaks for every component its process hosts, and is named after the process.</p>'
        + table(["Process", "Components"], process_rows)
        + "<h3>Entities</h3>"
        '<p class="lede">Each change of state is one record, written by the owner after its own state changed. '
        "A fact is required where a rule cannot decide without it; the rest may be absent. Owners may record "
        "more than this; it is listed as not judged and never part of a verdict.</p>" + entities + "<h3>Boundaries</h3>"
        '<p class="lede">The sender records the request before it leaves and the one outcome it observed.</p>'
        + boundaries
    )
    lede = (
        f"What owners record, from <code>specifications/behaviour/vocabulary/</code>; published to the product as "
        "<code>contracts/behaviour/events.schema.json</code> "
        f"(vocabulary <code>{esc(spec.vocabulary_digest[:19])}…</code>)."
    )
    return section("vocabulary", "Vocabulary", lede, body)
