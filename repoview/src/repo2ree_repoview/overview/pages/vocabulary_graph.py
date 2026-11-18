"""Every set of names the repository spells, held to the operation catalogue: the vocabulary graph, drawn."""

from __future__ import annotations

from repo2ree_repoview.graphviz import quote as q
from repo2ree_repoview.overview.drawing import dot_svg
from repo2ree_repoview.overview.exports import GraphEdge, GraphVocabulary, VocabularyGraph
from repo2ree_repoview.overview.html import Page, esc, filter_box, prose, section, table

VOCABULARY_GRAPH = "vocabulary-graph"
# Where a vocabulary is written, as a fill: what a reader trusts, and what can drift.
ORIGIN_FILL = {"spec": "#ede9fe", "contract": "#dbeafe", "source": "#fef3c7"}
ORIGIN_LINE = {"spec": "#7c3aed", "contract": "#2563eb", "source": "#d97706"}
FAILING = "#dc2626"


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
    """The roots at the left; each edge from what holds a vocabulary to it, green when it holds, red when not."""
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
    lede = (
        "Every closed set of names the repository spells, each read from where it is written, and held to the "
        "operation catalogue by the edges between them: a vocabulary <b>equals</b> its sources, lies "
        "<b>within</b> them with the extras it names of its own, or is <b>derived</b> from them (generated, "
        "never checked). Fill says where it is written: "
        '<span style="background:#ede9fe">specification</span>, <span style="background:#dbeafe">contract</span>, '
        '<span style="background:#fef3c7">source</span>; a green edge holds, a red one does not, and a dashed red '
        "box reaches no root. <code>just check-vocabulary</code> fails on any of these, and on a set of names found "
        "anywhere that no vocabulary, gap or exception claims."
    )
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
    gaps = table(
        ["Site", "Why nothing holds it yet", "Names"],
        [[f"<code>{esc(gap.site)}</code>", prose(gap.reason), _names(gap.names)] for gap in graph.gaps],
    )
    exceptions = table(
        ["Site", "Why it is no vocabulary"],
        [[f"<code>{esc(item.site)}</code>", prose(item.reason)] for item in graph.exceptions],
    )
    body = (
        found
        + f'<div class="svgwrap">{graph_svg(graph)}</div>'
        + "<h3 id='vocabularies'>Vocabularies</h3>"
        + filter_box("vocabulary-list", "Filter vocabularies, places and names…")
        + vocabularies
        + "<h3 id='gaps'>Known gaps</h3>"
        '<p class="lede">Sets of names found that nothing holds yet, each kept visible with its reason.</p>'
        + gaps
        + "<h3 id='exceptions'>Exceptions</h3>"
        '<p class="lede">Sets of names found that share one with the catalogue but are no vocabulary.</p>' + exceptions
    )
    state = f"{len(failing)} failing edges, {len(loose)} unanchored" if failing or loose else "every edge holds"
    teaser = f"{len(graph.vocabularies)} vocabularies, {len(graph.edges)} edges: {state}; {len(graph.gaps)} known gaps"
    return Page(VOCABULARY_GRAPH, "Vocabulary graph", teaser, section(VOCABULARY_GRAPH, "Vocabulary graph", lede, body))
