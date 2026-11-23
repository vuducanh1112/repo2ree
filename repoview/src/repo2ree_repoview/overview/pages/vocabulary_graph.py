from __future__ import annotations

from repo2ree_repoview.graphviz import quote as q
from repo2ree_repoview.overview.drawing import dot_svg
from repo2ree_repoview.overview.exports import GraphEdge, GraphVocabulary, VocabularyGraph
from repo2ree_repoview.overview.html import Page, esc, filter_box, prose, section, table

VOCABULARY_GRAPH = "vocabulary-graph"
ORIGIN_FILL = {"spec": "#ede9fe", "contract": "#dbeafe", "source": "#fef3c7"}
ORIGIN_LINE = {"spec": "#7c3aed", "contract": "#2563eb", "source": "#d97706"}
FAILING = "#dc2626"


def _swatch(fill: str, line: str, text: str, dashed: bool = False) -> str:
    border = f"1px {'dashed' if dashed else 'solid'} {line}"
    return f'<span style="background:{fill};border:{border};border-radius:3px;padding:0 4px">{text}</span>'


def _stroke(color: str, text: str, dashed: bool = False) -> str:
    return f'<span style="border-bottom:2px {"dashed" if dashed else "solid"} {color}">{text}</span>'


_SYMBOLS = (
    (_swatch(ORIGIN_FILL["spec"], ORIGIN_LINE["spec"], "spec"), "read from the specification"),
    (_swatch(ORIGIN_FILL["contract"], ORIGIN_LINE["contract"], "contract"), "read from a generated contract"),
    (_swatch(ORIGIN_FILL["source"], ORIGIN_LINE["source"], "source"), "a literal written in code"),
    (_swatch("#fff", FAILING, "unanchored", dashed=True), "not traced back to the catalogue"),
    (_stroke("#15803d", "equals"), "the same names as its sources"),
    (_stroke("#15803d", "within"), "a subset of its sources"),
    (_stroke("#94a3b8", "derived", dashed=True), "generated from its sources, not checked"),
    (_stroke(FAILING, "failing"), "the relation does not hold"),
    ("<b>+n</b>", "n names of its own beyond its sources"),
)
LEGEND = (
    '<ul class="muted">' + "".join(f"<li>{symbol} {description}</li>" for symbol, description in _SYMBOLS) + "</ul>"
)


def _node(vocabulary: GraphVocabulary, roots: tuple[str, ...]) -> str:
    line = ORIGIN_LINE[vocabulary.origin] if vocabulary.anchored else FAILING
    shape = "doubleoctagon" if vocabulary.name in roots else "box"
    style = '"rounded,filled"' if vocabulary.anchored else '"rounded,filled,dashed"'
    return (
        f"  {q(vocabulary.name)} [shape={shape}, style={style}, fillcolor={q(ORIGIN_FILL[vocabulary.origin])}, "
        f"color={q(line)}, label={q(f'{vocabulary.name} ({len(vocabulary.names)})')}, "
        f"tooltip={q(vocabulary.where)}];"
    )


def _edge(edge: GraphEdge) -> list[str]:
    label = edge.relation + (f" +{len(edge.extras)}" if edge.extras else "")
    if edge.problems:
        style = f'color="{FAILING}", fontcolor="{FAILING}", penwidth=2'
    elif edge.relation == "derived":
        style = 'style=dashed, color="#94a3b8", fontcolor="#94a3b8"'
    else:
        style = 'color="#15803d", fontcolor="#15803d"'
    tooltip = "; ".join(edge.problems) or ", ".join(edge.extras) or edge.relation
    return [
        f"  {q(source)} -> {q(edge.target)} [label={q(label)}, {style}, tooltip={q(tooltip)}];"
        for source in edge.sources
    ]


def graph_svg(graph: VocabularyGraph) -> str:
    lines = [
        "digraph vocabulary {",
        '  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.12; ranksep=1.1;',
        "  node [fontsize=10, height=0.3];",
        "  edge [fontsize=8, arrowsize=0.6];",
        f"  {{ rank=source; {' '.join(q(root) for root in graph.roots)} }}",
    ]
    lines += [_node(vocabulary, graph.roots) for vocabulary in graph.vocabularies]
    lines += [line for edge in graph.edges for line in _edge(edge)]
    return dot_svg("\n".join([*lines, "}"]))


def _held_by(graph: VocabularyGraph, name: str) -> str:
    held = [edge for edge in graph.edges if edge.target == name]
    return "<br>".join(
        f"{esc(edge.relation)} {' | '.join(f'<code>{esc(source)}</code>' for source in edge.sources)}"
        + (f' <span class="muted">+{esc(", ".join(edge.extras))}</span>' if edge.extras else "")
        for edge in held
    )


def _names(names: tuple[str, ...]) -> str:
    shown = ", ".join(esc(name) for name in names)
    return f"<details><summary>{len(names)}</summary>{shown}</details>" if names else "0"


def page_vocabulary_graph(graph: VocabularyGraph) -> Page:
    failing = [edge for edge in graph.edges if edge.problems]
    loose = [vocabulary for vocabulary in graph.vocabularies if not vocabulary.anchored]
    lede = "Every set of names held to the operation catalogue; <code>just check-vocabulary</code> checks it."
    found = "".join(f'<p class="state-missing">! {esc(problem)}</p>' for problem in graph.problems)
    vocabularies = table(
        ["Vocabulary", "Read from", "Held by", "Names"],
        [
            [
                (
                    f'<b id="vocabulary-{esc(vocabulary.name)}">{esc(vocabulary.name)}</b><br>'
                    f'<span class="muted">{prose(vocabulary.summary)}</span>'
                ),
                f"<code>{esc(vocabulary.where)}</code>",
                _held_by(graph, vocabulary.name) or '<span class="muted">a root</span>',
                _names(vocabulary.names),
            ]
            for vocabulary in graph.vocabularies
        ],
        "vocabulary-list",
    )
    exceptions = table(
        ["Site", "Why it is no vocabulary"],
        [[f"<code>{esc(item.site)}</code>", prose(item.reason)] for item in graph.exceptions],
    )
    body = (
        found
        + LEGEND
        + f'<div class="svgwrap">{graph_svg(graph)}</div>'
        + "<h3 id='vocabularies'>Vocabularies</h3>"
        + filter_box("vocabulary-list", "Filter vocabularies, places and names…")
        + vocabularies
        + "<h3 id='exceptions'>Exceptions</h3>"
        '<p class="lede">Sets of names found that share one with the catalogue but are no vocabulary.</p>' + exceptions
    )
    state = f"{len(failing)} failing edges, {len(loose)} unanchored" if failing or loose else "every edge holds"
    teaser = f"{len(graph.vocabularies)} vocabularies, {len(graph.edges)} edges: {state}"
    return Page(VOCABULARY_GRAPH, "Vocabulary graph", teaser, section(VOCABULARY_GRAPH, "Vocabulary graph", lede, body))
