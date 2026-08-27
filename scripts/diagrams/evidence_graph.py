"""Derive the REE's evidence dependency graph from the audit rules themselves.

``audit.py`` decides, step by step, whether a receipt still speaks for the REE.
Each ``_audit_*_step`` names the upstream receipts and declarations it compares
itself against — so the staleness relation between steps is already written
down, once, in executable form. This reads it back out.

An edge ``A --> B`` means: B's receipt is audited against A, labelled with the
digest the comparison joins on. Which makes the graph a blast radius — re-run A,
and everything downstream of it goes stale — and each step carries the size of
its own, as the count of what its re-run invalidates.

Nothing here is hand-maintained. Adding a comparison to a step adds an edge.

    python scripts/diagrams/evidence_graph.py                              # SVG on stdout
    python scripts/diagrams/evidence_graph.py -o dist/diagrams/domain/evidence.svg
    python scripts/diagrams/evidence_graph.py -f dot                       # to pipe into dot yourself
    python scripts/diagrams/evidence_graph.py -f blast                     # the closure, as text
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT = REPO_ROOT / "core/src/repo2ree_core/domain/ree/audit.py"

# The audited step each function answers for. Derived from the function name;
# spelled out only where the receipt slot and the step name differ.
SLOT_TO_STEP = {
    "source": "source",
    "evaluation": "evaluation",
    "hardware_observation": "hardware",
    "build": "runtime",
    "sbom": "sbom",
    "sbom_cross_check": "sbom_cross_check",
    "test_activation": "test_activation",
    "experiments": "experiments",
}


@dataclass(frozen=True)
class Origin:
    """Where a value in an audit comparison came from."""

    kind: str  # receipt | definition
    name: str

    @property
    def node(self) -> str:
        return SLOT_TO_STEP.get(self.name, self.name) if self.kind == "receipt" else f"def.{self.name}"


@dataclass(frozen=True)
class Edge:
    source: Origin
    step: str
    reason: str
    compared: str = ""
    kind: str = "staleness"  # staleness | applicable


class AuditExtractor:
    def __init__(self, path: Path):
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.funcs = {n.name: n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}

    def steps(self) -> list[tuple[str, ast.FunctionDef]]:
        out = []
        for name, fn in self.funcs.items():
            if not (name.startswith("_audit_") and name.endswith("_step")):
                continue
            step = name.removeprefix("_audit_").removesuffix("_step")
            out.append((step, fn))
        return out

    # ------------------------------------------------
    # Binding resolution
    # ------------------------------------------------

    def _bindings(self, fn: ast.FunctionDef) -> dict[str, Origin]:
        """Local names bound to a slice of the subject, so comparisons resolve."""
        bound: dict[str, Origin] = {}

        def bind(target: ast.expr, value: ast.expr) -> None:
            if isinstance(target, ast.Name):
                origin = self._origin(value, bound)
                if origin:
                    bound[target.id] = origin

        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                target = node.targets[0]
                if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                    for element, value in zip(target.elts, node.value.elts, strict=False):
                        bind(element, value)
                else:
                    bind(target, node.value)
            elif isinstance(node, ast.For):
                # `for experiment in subject.definition.experiments` — the loop
                # variable is one declared experiment, and the receipts keyed by
                # its name are audited against it.
                bind(node.target, node.iter)
        return bound

    def _origin(self, node: ast.expr, bound: dict[str, Origin]) -> Origin | None:
        # subject.receipts.experiments.get(name) — the call is incidental
        if isinstance(node, ast.Call):
            return self._origin(node.func, bound)
        if isinstance(node, ast.Name):
            return bound.get(node.id)
        if not isinstance(node, ast.Attribute):
            return None
        chain = self._chain(node)
        if len(chain) >= 3 and chain[0] == "subject" and chain[1] in {"receipts", "definition"}:
            return Origin("receipt" if chain[1] == "receipts" else "definition", chain[2])
        # `build.produced_runtime_digest` — a field read off a bound local
        if len(chain) >= 2 and chain[0] in bound:
            return bound[chain[0]]
        return None

    def _chain(self, node: ast.expr) -> list[str]:
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return list(reversed(parts))

    def _field(self, node: ast.expr) -> str:
        return node.attr if isinstance(node, ast.Attribute) else ""

    # ------------------------------------------------
    # Edges
    # ------------------------------------------------

    def edges(self, step: str, fn: ast.FunctionDef) -> list[Edge]:
        bound = self._bindings(fn)
        own = bound.get("receipt")
        out: list[Edge] = []

        for node in ast.walk(fn):
            if isinstance(node, ast.If):
                for reason in self._reasons(node):
                    out.extend(self._reason_edges(node.test, reason, step, own, bound))
            elif isinstance(node, ast.Call) and self._name(node.func) == "_step":
                out.extend(self._applicable_edges(node, step, own, bound))
        return out

    def _reasons(self, node: ast.If) -> list[str]:
        """The complaints this guard appends, and only its own — not a nested one's."""
        return [
            str(stmt.value.args[0].value)
            for stmt in node.body
            if isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and self._name(stmt.value.func).endswith("append")
            and stmt.value.args
            and isinstance(stmt.value.args[0], ast.Constant)
        ]

    def _reason_edges(
        self, test: ast.expr, reason: str, step: str, own: Origin | None, bound: dict[str, Origin]
    ) -> list[Edge]:
        compared: list[tuple[Origin, str]] = []
        for node in ast.walk(test):
            if isinstance(node, ast.Compare):
                for side in [node.left, *node.comparators]:
                    origin = self._origin(side, bound)
                    if origin:
                        compared.append((origin, self._field(side)))
            elif isinstance(node, ast.Attribute | ast.Name):
                origin = self._origin(node, bound)
                if origin:
                    compared.append((origin, ""))

        # The step's own receipt is one side of every comparison it makes; the
        # edge is what it was compared *against*.
        others = [(origin, field) for origin, field in compared if origin != own]
        if not others:
            return []
        # One edge per origin, and the *named field* wins over a bare mention of
        # it. `if receipt and source and receipt.x != source.x` mentions `source`
        # twice — once as a None-guard, once as the comparison that matters —
        # and walk order reaches the guard first, so taking the first hit
        # labelled every edge with nothing.
        best: dict[Origin, str] = {}
        for origin, field in others:
            if field or origin not in best:
                best.setdefault(origin, field)
                if field:
                    best[origin] = field
        return [Edge(origin, step, reason, field) for origin, field in best.items()]

    def _applicable_edges(self, call: ast.Call, step: str, own: Origin | None, bound: dict[str, Origin]) -> list[Edge]:
        expr = next((kw.value for kw in call.keywords if kw.arg == "applicable"), None)
        if expr is None:
            return []
        seen: set[Origin] = set()
        edges = []
        for origin in self._applicability_origins(expr, bound):
            if origin != own and origin not in seen:
                seen.add(origin)
                edges.append(Edge(origin, step, "is what this evidence is about", kind="applicable"))
        return edges

    def _applicability_origins(self, expr: ast.expr, bound: dict[str, Origin]) -> list[Origin]:
        """What an applicability test reads, following the helpers it delegates to.

        ``_runtime_is_declared(subject)`` stands for the declaration it reads,
        and it appears both alone and as one half of a conjunction — so the
        inlining happens per call node rather than only at the root. Its body is
        resolved against *its own* bindings: the name ``build`` means the
        declaration there and the receipt in most of its callers, and reading it
        with the caller's table turned a declaration into its own evidence.
        """
        origins: list[Origin] = []
        for node in ast.walk(expr):
            if isinstance(node, ast.Call) and self._name(node.func) in self.funcs:
                helper = self.funcs[self._name(node.func)]
                returned = self._returns(helper)
                if returned is not None:
                    origins.extend(self._applicability_origins(returned, self._bindings(helper)))
            elif isinstance(node, ast.Attribute | ast.Name):
                origin = self._origin(node, bound)
                if origin:
                    origins.append(origin)
        return origins

    def _returns(self, fn: ast.FunctionDef) -> ast.expr | None:
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and node.value is not None:
                return node.value
        return None

    def _name(self, node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""


def collect() -> list[Edge]:
    extractor = AuditExtractor(AUDIT)
    edges: list[Edge] = []
    for step, fn in extractor.steps():
        # `_audit_experiments_step` audits a family, not a step; name it so.
        name = "experiment" if step == "experiments" else step
        edges.extend(Edge(e.source, name, e.reason, e.compared, e.kind) for e in extractor.edges(step, fn))
    return edges


def blast_radius(edges: list[Edge]) -> dict[str, list[str]]:
    """For each step, every step that goes stale when it is re-run.

    Only receipt-to-receipt edges: a declaration moving is an authoring act, not
    a re-run, and mixing the two would answer a question nobody asked. The
    closure is transitive because staleness is — a rebuilt runtime restales the
    SBOM, and the cross-check rests on the SBOM.
    """
    downstream: dict[str, set[str]] = {}
    for edge in edges:
        if edge.kind == "staleness" and edge.source.kind == "receipt":
            downstream.setdefault(edge.source.node, set()).add(edge.step)

    def reach(start: str) -> set[str]:
        seen: set[str] = set()
        stack = list(downstream.get(start, ()))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            stack.extend(downstream.get(node, ()))
        return seen

    return {step: sorted(reach(step)) for step in sorted({e.step for e in edges})}


def tiers(edges: list[Edge]) -> dict[str, int]:
    """Each step's depth in the receipt DAG — how much evidence must precede it.

    Longest path rather than shortest: ``test_activation`` rests on both the
    source and the runtime built from it, and placing it beside the runtime
    (its shortest parent) would draw an edge that skips a rank and read as
    though the two were alternatives rather than a sequence.
    """
    parents: dict[str, set[str]] = {}
    for edge in edges:
        if edge.kind == "staleness" and edge.source.kind == "receipt":
            parents.setdefault(edge.step, set()).add(edge.source.node)
        parents.setdefault(edge.step, set())

    depth: dict[str, int] = {}

    def rank(step: str) -> int:
        if step in depth:
            return depth[step]
        depth[step] = 0  # guards against a cycle the audit rules should not have
        depth[step] = max((rank(parent) + 1 for parent in parents.get(step, ())), default=0)
        return depth[step]

    return {step: rank(step) for step in parents}


def render_dot(edges: list[Edge]) -> str:
    """Layered DOT, ranked by evidence depth — the layout dagre will not give us.

    Each tier is a ``rank=same`` group, so the diagram reads strictly downward:
    a step is always below every receipt it rests on. Declarations are pinned
    into their consumer's tier rather than given ranks of their own, which keeps
    authoring inputs beside the step they inform instead of inventing a rank
    between two evidence tiers.
    """
    depth = tiers(edges)
    by_tier: dict[int, list[str]] = {}
    for step, rank in sorted(depth.items()):
        by_tier.setdefault(rank, []).append(step)

    # A declaration sits with the shallowest step it informs: that is where it
    # first has to exist, and pulling it deeper would misstate when it is needed.
    decl_tier: dict[str, int] = {}
    for edge in edges:
        if edge.source.kind == "definition":
            node = edge.source.node
            decl_tier[node] = min(decl_tier.get(node, 99), depth.get(edge.step, 0))

    # A declaration's *own* step is the one it is compared against field by
    # field. Everything else it informs is a secondary relation, and drawing
    # those as edges is what produced arcs spanning three tiers: one node
    # reaching four steps at four depths cannot be laid out without them.
    # They become annotations on the step instead, where they read as a
    # property of the evidence rather than as another line to trace.
    primary: dict[str, str] = {}
    about: dict[str, list[str]] = {}
    for edge in edges:
        if edge.source.kind != "definition":
            continue
        if edge.kind == "staleness":
            primary[edge.source.node] = edge.step
    for edge in edges:
        if edge.source.kind != "definition" or edge.kind != "applicable":
            continue
        # A declaration nothing compares against still has one step it is for.
        if edge.source.node not in primary:
            primary[edge.source.node] = edge.step
        elif primary[edge.source.node] != edge.step:
            about.setdefault(edge.step, []).append(edge.source.node)

    lines = [
        "digraph evidence {",
        "  rankdir=TB;",
        "  newrank=true;",
        # Graphviz's default opaque canvas, as the arch_graph diagrams beside
        # this one have. `bgcolor=transparent` reads as a checkerboard in every
        # viewer that indicates transparency, and the figure's text is dark
        # besides — it has to sit on a light ground to be legible anyway, so
        # letting a host page choose that ground buys nothing.
        # A same-rank edge carries its label above the line, so without pad the
        # multi-line ones on the top tier are clipped by the canvas edge.
        '  graph [ranksep=0.85, nodesep=0.5, pad=0.4, fontname="Helvetica"];',
        '  node  [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11,',
        '         fillcolor="#dce7ee", color="#2d6b8c", fontcolor="#16202a",',
        # height is a floor, not a fixed size: a node carrying two annotation
        # lines has to grow, and leaving it at the default pressed the last line
        # against the border.
        '         height=0.36, margin="0.16,0.09"];',
        '  edge  [fontname="Helvetica", fontsize=9, color="#8595a2", fontcolor="#5a6b78"];',
        "",
    ]
    lines.extend(
        f'  "{node}" [shape=note, fillcolor="#e2ece8", color="#0f766e", fontcolor="#12312c"];'
        for node in sorted(decl_tier)
    )
    # Blast radius belongs on the node, not in a table beside the picture: it is
    # a property of the step, and it is the one number you want while looking at
    # the graph. Stated once, as the count — the fill ramp that carried it a
    # second time was the only mark here not derived from the audit rules, and
    # it encoded a number the number already gives you.
    radius = blast_radius(edges)
    for step in sorted(depth):
        extra = about.get(step)
        downstream = len(radius.get(step, ()))
        label = [step]
        if extra:
            label.append(f'<FONT POINT-SIZE="8" COLOR="#0f766e">about {", ".join(sorted(extra))}</FONT>')
        if downstream:
            plural = "step" if downstream == 1 else "steps"
            label.append(f'<FONT POINT-SIZE="8" COLOR="#8a5514">stales {downstream} {plural}</FONT>')
        lines.append(f'  "{step}" [label=<{"<BR/>".join(label)}>];')
    lines.append("")

    # Each declaration joins the rank of the step it declares, so it sits beside
    # its step rather than floating to the top of the drawing — `build_runtime`
    # was landing a full three tiers above the runtime it describes, and the
    # edge between them crossed everything in between. Now that a declaration
    # has exactly one edge, sharing a rank costs nothing and it reads as what it
    # is: an input alongside the step, not a stage before it.
    ranked: dict[int, list[str]] = {rank: list(members) for rank, members in by_tier.items()}
    for decl, step in sorted(primary.items()):
        ranked.setdefault(depth.get(step, 0), []).append(decl)
    for rank in sorted(ranked):
        if len(ranked[rank]) > 1:
            joined = "; ".join(f'"{m}"' for m in sorted(ranked[rank]))
            lines.append(f"  {{ rank=same; {joined}; }}")
    lines.append("")

    # One edge per pair. A declaration is compared field by field — origin, type
    # and ref for a source — and drawing those as parallel edges gave four
    # arrows between the same two boxes with their labels stacked into mush.
    # They are one relationship; the label lists what it covers.
    merged: dict[tuple[str, str, str], list[str]] = {}
    for edge in edges:
        key = (edge.source.node, edge.step, edge.kind)
        fields = merged.setdefault(key, [])
        # Field names, not complaints. `snapshot_digest` is the join the audit
        # actually makes, it is a third the width of the sentence about it, and
        # the sentence adds nothing the edge does not already show. The prose
        # stays in the text emitter, for reading rather than for looking at.
        if edge.compared and edge.compared not in fields:
            fields.append(edge.compared)

    for (tail, head, kind), fields in merged.items():
        if kind == "applicable":
            # Drawn only for a declaration whose step compares nothing against
            # it — otherwise the labelled edge already says it. Secondary
            # relations are annotations now, so nothing here spans a tier.
            if (tail, head, "staleness") in merged or primary.get(tail) != head:
                continue
            lines.append(f'  "{tail}" -> "{head}" [style=dashed, color="#0f766e", arrowsize=0.7];')
        else:
            joined = "\\n".join(fields)
            lines.append(f'  "{tail}" -> "{head}" [label="{joined}", weight=2];')
    lines.append("}")
    return "\n".join(lines)


def render_svg(edges: list[Edge]) -> str:
    """Run the graph through ``dot`` and return a figure fit to embed."""
    svg = subprocess.run(["dot", "-Tsvg"], input=render_dot(edges), capture_output=True, text=True, check=True).stdout
    # Drop the prolog so the figure inlines into a host document, and let the
    # container size it: a graph pinned to its own point size cannot be embedded
    # anywhere its author did not measure first.
    svg = svg[svg.index("<svg") :]
    return re.sub(r'width="\d+pt" height="\d+pt"', 'class="evidence-graph"', svg, count=1)


def _emit(text: str, output: Path | None) -> None:
    """Write to *output* or stdout, reporting the path the way arch_graph does."""
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    print(f"wrote {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-f", "--format", choices=("svg", "dot", "blast"), default="svg")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()
    edges = collect()
    if args.format == "svg":
        _emit(render_svg(edges), args.output)
    elif args.format == "dot":
        _emit(render_dot(edges), args.output)
    else:
        radius = blast_radius(edges)
        listed = "\n".join(
            f"{step:<18} re-run → {', '.join(downstream) or '(nothing)'}" for step, downstream in radius.items()
        )
        _emit(listed, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
