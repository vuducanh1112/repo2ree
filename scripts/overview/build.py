#!/usr/bin/env python3
"""Build the repository overview: one static page over what the repository already knows.

It draws nothing new from the code. It reads the zones (zones.toml), the gates'
certificates, the behaviour specification with the coverage and excuses of the last
behaviour receipt, the generated architecture and recipe diagrams, the Just recipes,
the environment contract, and the OpenAPI contract, and lays them out page by page.

The overview is a bundle bound to one commit: whatever it shows from outside the tree
(test evidence, diagrams) is copied into it, and what is too large to copy (REE Git
archives, spans) is listed by sha256. manifest.json records the commit, whether the
working tree was dirty, and every input. `just repo-overview` regenerates the diagrams
and writes reports/overview/<revision>/, with reports/overview/latest pointing at it.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import zones as zone_map  # noqa: E402
from scripts.diagrams.stamp import read_svg_stamp  # noqa: E402

from repo2ree_conformance import load_spec  # noqa: E402
from repo2ree_conformance.spec import (  # noqa: E402
    CitedEntity,
    CitingEntity,
    EntityRequirement,
    EntityTrigger,
    ExclusionRequirement,
    GuardRequirement,
    Invariant,
    MessageRequirement,
    Spec,
)

CERTIFICATES = ROOT / ".validation-certificates"
EXPECTATIONS = ROOT / "conformance/expected-verdicts.toml"
DIAGRAMS = ROOT / "reports/diagrams"
OVERVIEWS = ROOT / "reports/overview"
ENVIRONMENT = ROOT / "contracts/config/environment.json"
OPENAPI = ROOT / "contracts/openapi.json"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def prose(value: object) -> str:
    """Escaped text with `backticked` spans as code."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(value))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------------------- facts


@dataclass(frozen=True)
class Head:
    revision: str
    tree: str
    index_tree: str
    subject: str
    branch: str
    dirty: bool
    committed: str


def head() -> Head:
    return Head(
        revision=git("rev-parse", "HEAD"),
        tree=git("rev-parse", "HEAD^{tree}"),
        index_tree=git("write-tree"),
        subject=git("log", "-1", "--format=%s"),
        branch=git("rev-parse", "--abbrev-ref", "HEAD"),
        dirty=bool(git("status", "--porcelain")),
        committed=git("log", "-1", "--format=%cI"),
    )


@dataclass(frozen=True)
class Certificate:
    name: str
    recipe: str
    state: str  # current, stale, missing
    detail: str


def certificates(now: Head) -> tuple[list[Certificate], dict[str, Any] | None]:
    found: list[Certificate] = []
    commit = CERTIFICATES / "commit-gate-ok"
    if commit.is_file():
        tree = commit.read_text().strip()
        current = tree in {now.tree, now.index_tree}
        found.append(
            Certificate("Commit gate", "just commit-gate", "current" if current else "stale", f"tree {tree[:10]}")
        )
    else:
        found.append(Certificate("Commit gate", "just commit-gate", "missing", "never run in this clone"))
    receipt: dict[str, Any] | None = None
    behaviour = CERTIFICATES / "behaviour-ok"
    if behaviour.is_file():
        receipt = json.loads(behaviour.read_text())
        detail = f"{receipt.get('revision', '')[:10]}: {len(receipt.get('tests', []))} tests"
        if receipt.get("tree") != now.tree:
            state = "stale"
        elif now.dirty:
            state, detail = "current", detail + "; covers HEAD, not the uncommitted changes"
        else:
            state = "current"
        found.append(Certificate("Behaviour gate", "just behaviour-gate", state, detail))
    else:
        found.append(Certificate("Behaviour gate", "just behaviour-gate", "missing", "never run in this clone"))
    publish = CERTIFICATES / "publish-gate-ok"
    if publish.is_file():
        rows = dict(line.split("\t")[:2] for line in publish.read_text().splitlines() if line.count("\t") == 1)
        current = rows.get("tree") == now.tree
        detail = f"{rows.get('revision', '?')[:10]}: local image set"
        found.append(Certificate("Publish gate", "just publish-gate", "current" if current else "stale", detail))
    else:
        found.append(Certificate("Publish gate", "just publish-gate", "missing", "never run in this clone"))
    return found, receipt


# ---------------------------------------------------------------------------- bundle


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_name(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


class Bundle:
    """The overview's own copy of what it shows from outside the tree, and what it only references."""

    def __init__(self, root: Path, revision: str) -> None:
        self.root = root
        self.revision = revision
        self.copied: list[dict[str, Any]] = []
        self.referenced: list[dict[str, Any]] = []

    def copy(self, source: Path, target: str, **context: str) -> str | None:
        """Copy one file to ``target`` (relative to the bundle); None when the source is missing."""
        if not source.is_file():
            return None
        destination = self.root / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self.copied.append({"path": target, "source": source_name(source), "sha256": sha256(destination), **context})
        return target

    def copy_tree(self, source: Path, target: str, **context: str) -> None:
        for path in sorted(source.rglob("*")) if source.is_dir() else []:
            if path.is_file():
                self.copy(path, f"{target}/{path.relative_to(source)}", **context)

    def reference(self, source: Path, **context: str) -> None:
        for path in sorted(source.rglob("*")) if source.is_dir() else [source] if source.is_file() else []:
            if path.is_file():
                entry = {"source": source_name(path), "sha256": sha256(path), "bytes": path.stat().st_size}
                self.referenced.append(entry | context)


# What a test's evidence holds, by whether the overview copies it or only names it by hash.
COPIED = (
    "test.json",
    "junit.xml",
    "logs",
    "verification",
    "traces",
    "recording/manifest.json",
    "recording/journal",
    "recording/stores",
)
REFERENCED = ("recording/rees", "recording/telemetry", "artifacts")


def bundle_evidence(bundle: Bundle, receipt: dict[str, Any] | None) -> tuple[list[Path], dict[tuple[str, str], str]]:
    """Copy the receipt and its runs' evidence; (bundled run directories, (run, test) -> bundled test directory)."""
    if receipt is None:
        return [], {}
    bundle.copy(CERTIFICATES / "behaviour-ok", "evidence/behaviour-ok.json", kind="receipt")
    runs: list[Path] = []
    tests: dict[tuple[str, str], str] = {}
    for run in (ROOT / name for name in receipt.get("runs", [])):
        if not (run / "run.json").is_file():
            continue
        described = json.loads((run / "run.json").read_text())
        context = {"run": run.name, "run_revision": str(described.get("build_revision", ""))}
        bundle.copy(run / "run.json", f"evidence/{run.name}/run.json", **context)
        for test in described.get("tests", []):
            target = f"evidence/{run.name}/{test['directory']}"
            for part in COPIED:
                source = run / test["directory"] / part
                if source.is_dir():
                    bundle.copy_tree(source, f"{target}/{part}", **context)
                else:
                    bundle.copy(source, f"{target}/{part}", **context)
            for part in REFERENCED:
                bundle.reference(run / test["directory"] / part, **context)
            tests[(run.name, str(test["name"]))] = target
        runs.append(bundle.root / "evidence" / run.name)
    return runs, tests


def suite_coverage(runs: list[Path]) -> tuple[Counter[str], Counter[str]]:
    """(edge and message counts, rule trigger counts) over the bundled evidence of the receipt's tests."""
    edges: Counter[str] = Counter()
    rules: Counter[str] = Counter()
    for run in runs:
        for report in run.glob("tests/*/verification/conformance.json"):
            data = json.loads(report.read_text())
            for machine, counts in data.get("coverage", {}).get("transitions", {}).items():
                edges.update({f"{machine} {edge}": count for edge, count in counts.items()})
            for boundary, counts in data.get("coverage", {}).get("messages", {}).items():
                edges.update({f"{boundary}: {message}": count for message, count in counts.items()})
            rules.update({rule["rule"]: int(rule.get("triggered", 0)) for rule in data.get("rules", [])})
    return edges, rules


def excuses() -> tuple[list[dict[str, Any]], dict[str, str]]:
    declared = tomllib.loads(EXPECTATIONS.read_text())
    unreached = {item: entry["reason"] for entry in declared.get("unreached", []) for item in entry["items"]}
    return declared.get("expected", []), unreached


def recipes() -> list[dict[str, Any]]:
    dump = json.loads(
        subprocess.run(
            ["just", "--dump", "--dump-format", "json"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout
    )
    listed = []
    for name, raw in dump["recipes"].items():
        group = next(
            (a["group"] for a in raw.get("attributes", []) if isinstance(a, dict) and "group" in a), "Ungrouped"
        )
        listed.append(
            {
                "name": name,
                "group": group,
                "doc": raw.get("doc") or "",
                "private": bool(raw.get("private")),
                "parameters": [p["name"] for p in raw.get("parameters", [])],
                "dependencies": [d["recipe"] for d in raw.get("dependencies", [])],
            }
        )
    return sorted(listed, key=lambda r: (r["group"], r["name"]))


# ---------------------------------------------------------------------------- drawing


def dot_svg(source: str) -> str:
    svg = subprocess.run(["dot", "-Tsvg"], input=source, capture_output=True, text=True, check=True).stdout
    # Graphviz names the font it measured with; the page draws them all in its own sans-serif.
    return re.sub(r'font-family="[^"]*"', 'font-family="system-ui,sans-serif"', svg[svg.index("<svg") :])


def machine_svg(
    spec: Spec, name: str, edges: Counter[str] | None = None, unreached: dict[str, str] | None = None
) -> str:
    """One machine. With ``edges``, each edge carries how often the receipt's tests took it; without, the spec alone."""
    entity = spec.entities[name]
    why = {(t.source, target): t.why for t in entity.transitions for target in t.targets if t.why}
    lines = [
        "digraph machine {",
        '  rankdir=LR; bgcolor="transparent"; pad=0.2;',
        '  node [shape=box, style="rounded,filled", fillcolor="#eef2f7", color="#64748b", fontsize=10];',
        '  edge [fontsize=9, color="#64748b", fontcolor="#334155"];',
        '  "(none)" [shape=point, width=0.12, color="#334155"];',
    ]
    for state in entity.states:
        terminal = state in entity.terminal
        lines.append(f'  "{state}" [peripheries={2 if terminal else 1}, tooltip="{esc(entity.states[state])}"];')
    pairs = [("(none)", state) for state in entity.initial] + [
        (source, target) for source, targets in entity.edges.items() for target in sorted(targets)
    ]
    for source, target in pairs:
        key = f"{name} {source} -> {target}"
        if edges is None:
            tip = f', tooltip="{esc(why[(source, target)])}"' if (source, target) in why else ""
            lines.append(f'  "{source}" -> "{target}" [color="#475569"{tip}];')
            continue
        count = edges.get(key, 0)
        if count:
            style = f'label="{count}", color="#0f766e", fontcolor="#0f766e", penwidth=1.6'
        elif unreached and key in unreached:
            style = (
                f'label="excused", style=dashed, color="#b45309", fontcolor="#b45309", tooltip="{esc(unreached[key])}"'
            )
        else:
            style = 'label="0", style=dashed, color="#dc2626", fontcolor="#dc2626"'
        lines.append(f'  "{source}" -> "{target}" [{style}];')
    lines.append("}")
    return dot_svg("\n".join(lines))


def system_svg(spec: Spec) -> str:
    lines = [
        "digraph system {",
        '  rankdir=LR; compound=true; bgcolor="transparent"; pad=0.2;',
        "  node [fontsize=10];",
        '  edge [fontsize=9, color="#64748b"];',
    ]
    processes: dict[str, list[str]] = defaultdict(list)
    for name, component in spec.components.items():
        processes[component.process].append(name)
    for process, members in processes.items():
        lines.append(
            f'  subgraph "cluster_p_{process}" {{ label="{process} process"; style="rounded"; color="#94a3b8";'
        )
        for member in members:
            lines.append(
                f'    subgraph "cluster_c_{member}" {{ label="{member}"; '
                'style="rounded,filled"; fillcolor="#f1f5f9"; color="#cbd5e1";'
            )
            owned = [e.name for e in spec.entities.values() if e.owner == member]
            entity_style = 'shape=ellipse, style=filled, fillcolor="#dbeafe", color="#3b82f6"'
            lines.extend(f'      "{entity}" [{entity_style}];' for entity in owned)
            if not owned:
                lines.append(f'      "anchor_{member}" [shape=point, style=invis];')
            lines.append("    }")
        lines.append("  }")
    for boundary in spec.boundaries.values():
        lines.append(
            f'  "b_{boundary.name}" [label="{boundary.name}", shape=hexagon, '
            'style=filled, fillcolor="#fef3c7", color="#d97706"];'
        )
        sender = next(
            (e.name for e in spec.entities.values() if e.owner == boundary.sender), f"anchor_{boundary.sender}"
        )
        receiver = next(
            (e.name for e in spec.entities.values() if e.owner == boundary.receiver), f"anchor_{boundary.receiver}"
        )
        lines.append(f'  "{sender}" -> "b_{boundary.name}" [ltail="cluster_c_{boundary.sender}"];')
        lines.append(f'  "b_{boundary.name}" -> "{receiver}" [lhead="cluster_c_{boundary.receiver}"];')
    lines.append("}")
    return dot_svg("\n".join(lines))


# ---------------------------------------------------------------------------- page

# The page's look and its filter boxes, inlined so the page is one file.
STYLE = (Path(__file__).with_name("overview.css")).read_text()
SCRIPT = (Path(__file__).with_name("overview.js")).read_text()


def section(anchor: str, title: str, lede: str, body: str) -> str:
    return f'<section id="{anchor}"><h2>{esc(title)}</h2><p class="lede">{lede}</p>{body}</section>'


def table(headers: list[str], rows: list[list[str]], ident: str = "") -> str:
    head_row = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr data-row>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    opening = f'<table id="{ident}">' if ident else "<table>"
    return f"{opening}<thead><tr>{head_row}</tr></thead><tbody>{body}</tbody></table>"


def filter_box(target: str, placeholder: str) -> str:
    return f'<input class="filter" data-target="{target}" placeholder="{esc(placeholder)}">'


def page_overview(now: Head, found: list[Certificate]) -> str:
    cards = [
        ("HEAD", f"<code>{now.revision[:10]}</code>", esc(now.subject)),
        ("Branch", esc(now.branch), "working tree dirty" if now.dirty else "working tree clean"),
    ]
    cards += [
        (c.name, f'<span class="state-{c.state}">{c.state}</span>', f"{esc(c.detail)} · <code>{esc(c.recipe)}</code>")
        for c in found
    ]
    body = (
        '<div class="cards">'
        + "".join(
            f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div><div class="muted">{d}</div></div>'
            for k, v, d in cards
        )
        + "</div>"
    )
    return section(
        "overview", "Overview", f"Generated from commit <code>{now.revision[:10]}</code> ({esc(now.committed)}).", body
    )


def page_zones(declared: zone_map.Zones, problems: list[str]) -> str:
    parts = []
    for zone in declared.zones:
        badge = '<span class="badge protected">protected</span>' if zone.protected else ""
        groups = "".join(
            f'<div class="group"><b>{esc(g.name)}</b> <span class="muted">{esc(g.summary)}</span>'
            + "".join(
                f'<div class="entry" data-row><code>{esc(e.path)}</code><span>{prose(e.description)}</span></div>'
                for e in g.entries
            )
            + "</div>"
            for g in zone.groups
        )
        parts.append(
            f'<div class="zone{" is-protected" if zone.protected else ""}" id="zone-{esc(zone.name)}">'
            f'<h3><span class="dot zone-{esc(zone.name)}"></span>{esc(zone.name)} {badge}</h3>'
            f'<div class="muted">{esc(zone.summary)}</div>{groups}</div>'
        )
    warn = "".join(f'<p class="state-missing">! {esc(p)}</p>' for p in problems)
    lede = (
        "Every tracked file belongs to the zone of its longest matching entry in <code>zones.toml</code>. "
        "Protected zones are what humans review; a commit touching one touches nothing else."
    )
    return section(
        "zones",
        "Zones",
        lede,
        filter_box("zone-list", "Filter paths and descriptions…") + f'<div id="zone-list">{"".join(parts)}</div>{warn}',
    )


def evidence_links(bundle: Bundle, directory: str | None) -> str:
    """Links to a test's bundled verdict report and operation traces."""
    if directory is None:
        return '<span class="muted">not bundled</span>'
    links = []
    if (bundle.root / directory / "verification/conformance.html").is_file():
        links.append(f'<a href="{esc(directory)}/verification/conformance.html">verdicts</a>')
    traces = sorted((bundle.root / directory / "traces").glob("*.html"))
    links += [f'<a href="{esc(directory)}/traces/{esc(trace.name)}">trace</a>' for trace in traces]
    return " · ".join(links) or '<span class="muted">none</span>'


def page_gates(
    receipt: dict[str, Any] | None,
    unreached: dict[str, str],
    bundle: Bundle,
    tests: dict[tuple[str, str], str],
) -> str:
    if not receipt:
        return section(
            "behaviour-gate",
            "Behaviour gate",
            "No behaviour receipt in this clone yet: run <code>just behaviour-gate</code>.",
            "",
        )
    rows = [
        [
            esc(t["test"]),
            esc(t["outcome"]),
            f'<span class="{"ok" if t["behaviour"] == "passed" else "ex"}">{esc(t["behaviour"])}</span>',
            esc(t.get("excused", "")),
            evidence_links(bundle, tests.get((t["run"], t["test"]))),
        ]
        for t in receipt.get("tests", [])
    ]
    coverage = receipt.get("coverage", {})
    reasons: dict[str, list[str]] = defaultdict(list)
    for item, reason in unreached.items():
        reasons[reason].append(item)
    unreached_rows = [
        [" ".join(f"<code>{esc(i)}</code>" for i in items), esc(reason)] for reason, items in reasons.items()
    ]
    body = (
        f"<p>Receipt for <code>{esc(receipt.get('revision', '')[:10])}</code> from runs "
        + ", ".join(f"<code>{esc(Path(r).name)}</code>" for r in receipt.get("runs", []))
        + ", copied into this overview under <code>evidence/</code>"
        + (
            f". The suite reached {coverage.get('reached', '?')} of {coverage.get('declared', '?')} "
            "specified rules, edges, and messages."
            if coverage
            else "."
        )
        + "</p>"
        + table(["Test", "Outcome", "Behaviour", "Excused because", "Evidence"], rows)
        + f"<h3>What a receipt does not prove ({len(unreached)} items)</h3>"
        + table(["Unreached by any gated test", "Why"], unreached_rows)
    )
    lede = "What the last behaviour gate accepted, and what its receipt concedes."
    return section("behaviour-gate", "Behaviour gate", lede, body)


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


def literal(value: Any) -> str:
    """A condition's value as written in the specification: names bare, anything else (``""``, ``false``) as JSON."""
    return value if isinstance(value, str) and value else json.dumps(value)


type Groups = dict[str, dict[str, tuple[str, ...]]]


def whole_groups(values: list[Any], groups: dict[str, tuple[str, ...]]) -> list[str]:
    """The groups that together list exactly ``values``, in declaration order; none when no such groups exist."""
    named = [group for group, members in groups.items() if set(members) <= set(values)]
    covered = {value for group in named for value in groups[group]}
    return named if covered == set(values) else []


def condition(name: str, value: Any, groups: Groups) -> str:
    """A condition as the specification states it: a value list that is whole groups reads as those groups."""
    if isinstance(value, dict) and "not" in value:
        return f"{name} ≠ {literal(value['not'])}"
    if isinstance(value, dict) and "per" in value:
        # The alternatives depend on the trigger's fact: one list for each of its values.
        cases = "; ".join(f"{key}: {', '.join(map(literal, items))}" for key, items in value["in"].items())
        return f"{name} by the trigger's {value['per']} ({cases})"
    if isinstance(value, dict) and "in" in value:
        if named := whole_groups(value["in"], groups.get(name, {})):
            return f"{name} ∈ {' ∪ '.join(named)}"  # noqa: RUF001 — the union sign, as the page shows it
        return f"{name} ∈ {{{', '.join(map(literal, value['in']))}}}"
    return f"{name} = {literal(value)}"


def where(conditions: dict[str, Any], groups: Groups) -> str:
    if not conditions:
        return ""
    return " where " + ", ".join(condition(name, value, groups) for name, value in conditions.items())


def entity_groups(spec: Spec, entity: str) -> Groups:
    return spec.entities[entity].groups if entity in spec.entities else {}


def trigger_text(spec: Spec, invariant: Invariant) -> str:
    when = invariant.when
    if isinstance(when, EntityTrigger):
        source = f" from {' | '.join(when.source)}" if when.source else ""
        return f"{when.entity}{source} → {' | '.join(when.to)}{where(when.where, entity_groups(spec, when.entity))}"
    return f"{when.boundary}.{when.message}{where(when.where, {})}"


def requirement_text(spec: Spec, invariant: Invariant) -> str:
    require = invariant.require
    if isinstance(require, GuardRequirement):
        trigger = invariant.when.entity if isinstance(invariant.when, EntityTrigger) else ""
        return where(require.where, entity_groups(spec, trigger)).removeprefix(" where ")
    if isinstance(require, ExclusionRequirement):
        partition = spec.entities[require.entity].partition
        return f"no {require.entity} in {' | '.join(require.in_states)} with the same {partition}"
    if isinstance(require, EntityRequirement | MessageRequirement):
        key = "its own key" if require.key_from == "$key" else require.key_from
        before = ", before it" if require.order == "before" else ""
        if isinstance(require, EntityRequirement):
            reached = " | ".join(require.reached)
            conditions = where(require.where, entity_groups(spec, require.entity))
            return f"{require.entity} keyed by {key} reached {reached}{conditions}{before}"
        return f"{require.boundary}.{require.message} keyed by {key} was recorded{before}"
    return f"eventually {' | '.join(invariant.eventually)}"


def rule_values(spec: Spec) -> tuple[dict[tuple[str, str, str], list[str]], dict[str, list[str]]]:
    """((entity, fact, value) -> the rules whose trigger names that value, entity -> the rules naming none of its).

    A requirement's conditions on another entity name values of that entity's facts; a guard's
    condition is what the trigger must satisfy, so the guard applies to every value its trigger admits.
    """
    named: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    every: dict[str, list[str]] = defaultdict(list)

    def collect(rule: str, entity: str, conditions: dict[str, Any]) -> set[str]:
        listed = spec.entities[entity].allowed if entity in spec.entities else {}
        facts = set()
        for fact, value in conditions.items():
            if fact not in listed:
                continue
            facts.add(fact)
            if isinstance(value, dict) and "per" in value:
                values = {item for items in value["in"].values() for item in items}
            elif isinstance(value, dict) and "in" in value:
                values = set(value["in"])
            elif isinstance(value, dict) and "not" in value:
                values = set(listed[fact]) - {value["not"]}
            else:
                values = {value}
            for item in values:
                named[(entity, fact, item)].append(rule)
        return facts

    for invariant in spec.invariants:
        when, require = invariant.when, invariant.require
        names_none = isinstance(when, EntityTrigger) and not collect(invariant.id, when.entity, when.where)
        if isinstance(when, EntityTrigger) and names_none and spec.entities[when.entity].allowed:
            every[when.entity].append(invariant.id)
        if isinstance(require, EntityRequirement):
            collect(invariant.id, require.entity, require.where)
    for name, entity in spec.entities.items():
        if entity.allowed:
            every[name].insert(0, f"machine:{name}")
    return named, every


def listed_values(spec: Spec) -> str:
    """Each value a fact lists, its group and meaning, and which rules name it."""
    named, every = rule_values(spec)
    out = []
    for name, entity in sorted(spec.entities.items()):
        for fact, meanings in entity.meanings.items():
            group_of = {value: group for group, values in entity.groups.get(fact, {}).items() for value in values}
            rows = [
                [
                    esc(group_of.get(value, "")),
                    f"<code>{esc(value)}</code>",
                    esc(meaning),
                    " ".join(f"<code>{esc(rule)}</code>" for rule in named.get((name, fact, value), []))
                    or '<span class="muted">none</span>',
                ]
                for value, meaning in meanings.items()
            ]
            applies = " ".join(f"<code>{esc(rule)}</code>" for rule in every.get(name, []))
            out.append(
                f"<h4>{esc(name)}.{esc(fact)}</h4>"
                f'<p class="lede">Every {esc(name)}, whatever its {esc(fact)}: {applies}</p>'
                + table(["Group", "Value", "Meaning", "Rules naming it"], rows)
            )
    return "".join(out)


SETTLES = {
    True: "must be terminal when its owner's journal closes",
    "final": "must be terminal when its owner's journal closes for good",
    False: "no close settles it",
}


def page_specification(spec: Spec) -> str:
    machines = []
    for name, entity in sorted(spec.entities.items()):
        edges = sum(len(targets) for targets in entity.edges.values())
        facts = (
            f"starts in {' | '.join(entity.initial)} · ends in {' | '.join(entity.terminal) or 'nothing'} · "
            f"{edges} edges · {SETTLES[entity.settles_before_close]}"
        )
        reasons = [(t.source, ", ".join(t.targets), t.why) for t in entity.transitions if t.why]
        why = (
            "<details><summary>Why these edges</summary><ul>"
            + "".join(f"<li><code>{esc(s)} → {esc(ts)}</code>: {esc(w)}</li>" for s, ts, w in reasons)
            + "</ul></details>"
            if reasons
            else ""
        )
        machines.append(
            f'<div class="card"><b>{esc(name)}</b> <span class="muted">owned by {esc(entity.owner)}</span>'
            f'<div class="muted">{esc(facts)}</div>'
            f'<div class="svgwrap">{machine_svg(spec, name)}</div>{why}</div>'
        )
    citations = []
    for boundary in spec.boundaries.values():
        for cite in boundary.cites:
            by, cited = cite.by, cite.cited
            citing = (
                f"{by.entity} reaching {by.reached}"
                if isinstance(by, CitingEntity)
                else f"{boundary.name}.{by.message}"
            )
            named = (
                f"{cited.entity} reaching {cited.reached} (its {cited.fact})"
                if isinstance(cited, CitedEntity)
                else f"the {boundary.name}.{cited.message} record"
            )
            citations.append([f"<code>{esc(boundary.name)}</code>", esc(f"{citing} names {named} in {by.fact}")])
    patterns: dict[str, list[Any]] = defaultdict(list)
    for invariant in spec.invariants:
        patterns[invariant.pattern].append(invariant)
    invariants = "".join(
        f"<h4>{esc(pattern)}</h4>"
        + table(
            ["Rule", "When", "Then", "Meaning"],
            [
                [
                    f"<code>{esc(i.id)}</code>",
                    f"<code>{esc(trigger_text(spec, i))}</code>",
                    f"<code>{esc(requirement_text(spec, i))}</code>",
                    esc(i.summary),
                ]
                for i in rules
            ],
        )
        for pattern, rules in sorted(patterns.items())
    )
    body = (
        '<h3>System map</h3><div class="diagram svgwrap">' + system_svg(spec) + "</div><h3>State machines</h3>"
        '<p class="lede">Where an instance starts, which edges it may take, and when it must have settled. '
        "Every other edge is a violation; nothing may leave a terminal state.</p>"
        + f'<div class="machines">{"".join(machines)}</div>'
        + "<h3>Citations</h3>"
        '<p class="lede">The only order the checker trusts across sources: a record that names another was written '
        "after it. Without the citation, a rule that needs the order is inconclusive.</p>"
        + table(["Boundary", "Citation"], citations)
        + "<h3>Invariants</h3>"
        '<p class="lede">Cross-entity rules, each in one fixed pattern. A condition never matches an absent fact.</p>'
        + invariants
        + "<h3>Listed values</h3>"
        '<p class="lede">The values a fact may take, as its declaration lists and groups them, and the rules '
        "whose trigger or requirement names each one. A value no rule names is still checked by the rules "
        "that apply to every value.</p>" + listed_values(spec)
    )
    lede = "What the checker holds the evidence to, from <code>specifications/behaviour/</code>: no test results here."
    return section("specification", "Specification", lede, body)


def suite_extras(runs: list[Path]) -> Counter[tuple[str, str]]:
    """What the receipt's tests recorded beyond the vocabulary, as each test's verdicts list it."""
    found: Counter[tuple[str, str]] = Counter()
    for run in runs:
        for report in run.glob("tests/*/verification/conformance.json"):
            for extra in json.loads(report.read_text()).get("extras", []):
                found[(extra["subject"], extra.get("fact") or "")] += int(extra["count"])
    return found


def page_coverage(
    spec: Spec, edges: Counter[str], rules: Counter[str], unreached: dict[str, str], extras: Counter[tuple[str, str]]
) -> str:
    legend = (
        '<p class="legend"><span class="ok">— reached (count)</span><span class="ex">- - excused</span>'
        '<span class="no">- - unreached, not excused</span></p>'
    )
    machines = "".join(
        f'<div class="card"><b>{esc(name)}</b> <span class="muted">owned by {esc(entity.owner)}</span>'
        f'<div class="svgwrap">{machine_svg(spec, name, edges, unreached)}</div></div>'
        for name, entity in sorted(spec.entities.items())
    )
    boundary_rows = [
        [
            f"<code>{esc(b.name)}</code>",
            " ".join(
                f'<span class="badge">{esc(m)} · {edges.get(f"{b.name}: {m}", 0)}</span>'
                for m in [*b.messages, "abandoned"]
            ),
        ]
        for b in spec.boundaries.values()
    ]
    invariant_rows = []
    for invariant in spec.invariants:
        count = rules.get(invariant.id, 0)
        status = (
            f'<span class="ok">{count}</span>'
            if count
            else (
                '<span class="ex">excused</span>'
                if f"rule:{invariant.id}" in unreached
                else '<span class="no">0</span>'
            )
        )
        invariant_rows.append([f"<code>{esc(invariant.id)}</code>", esc(invariant.pattern), status])
    extra_rows = [
        [f"<code>{esc(subject)}</code>", f"<code>{esc(fact)}</code>" if fact else "the whole subject", str(count)]
        for (subject, fact), count in sorted(extras.items())
    ]
    body = (
        "<h3>State machines, with how often each edge was taken</h3>"
        + legend
        + f'<div class="machines">{machines}</div>'
        + "<h3>Boundaries, with how often each message was recorded</h3>"
        + table(["Boundary", "Messages"], boundary_rows)
        + "<h3>Invariants, with how often each was triggered</h3>"
        + table(["Rule", "Pattern", "Triggered"], invariant_rows)
        + "<h3>Recorded beyond the vocabulary</h3>"
        + (
            table(["Subject", "Fact", "Records"], extra_rows)
            if extra_rows
            else '<p class="muted">Nothing: every record the tests left is declared in the vocabulary.</p>'
        )
    )
    lede = (
        "How the tests behind the last behaviour receipt exercised the specification, summed over their recordings. "
        'Excused items are listed with their reasons on the <a href="behaviour-gate.html">Behaviour gate</a> page.'
    )
    return section("coverage", "Coverage", lede, body)


def diagram_origin(bundle: Bundle, path: Path) -> str:
    """Which commit a diagram was generated from, as it records itself, against the overview's commit."""
    stamp = read_svg_stamp(path) if path.suffix == ".svg" else None
    if stamp is None:
        return '<span class="state-stale">Records no commit; regenerate it.</span>'
    revision = f"<code>{esc(stamp['revision'][:10])}</code>" + (" with uncommitted changes" if stamp["dirty"] else "")
    if stamp["revision"] != bundle.revision:
        older = f"Generated from an older commit, {revision}, at {esc(stamp['generated'])}."
        return f'<span class="state-stale">{older}</span>'
    return f"Generated from {revision} at {esc(stamp['generated'])}."


def diagram(bundle: Bundle, path: Path, title: str, note: str = "") -> str:
    """A generated diagram, copied into the bundle so the page keeps it."""
    origin = (read_svg_stamp(path) or {}) if path.is_file() and path.suffix == ".svg" else {}
    relative = bundle.copy(
        path, f"diagrams/{path.relative_to(DIAGRAMS)}", kind="diagram", revision=str(origin.get("revision", ""))
    )
    if relative is None:
        return f'<h3>{esc(title)}</h3><p class="state-missing">Missing: run <code>just generate-diagrams</code>.</p>'
    return (
        f'<h3>{esc(title)}</h3><p class="muted">{note} {diagram_origin(bundle, path)} '
        f'<a href="{esc(relative)}">Open full size</a></p>'
        f'<div class="diagram"><img src="{esc(relative)}" alt="{esc(title)}" loading="lazy"></div>'
    )


def page_architecture(bundle: Bundle) -> str:
    architecture = DIAGRAMS / "architecture"
    # The governed packages, not whatever an older run left behind.
    configured = subprocess.run(
        [sys.executable, "scripts/diagrams/arch_graph.py", "--list-packages"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    packages = [architecture / f"{package}.svg" for package in configured]
    body = diagram(
        bundle,
        architecture / "workspace.svg",
        "Backend workspace, by package",
        "Cross-package layering, as import-linter enforces it.",
    )
    body += diagram(bundle, architecture / "gui.svg", "GUI, collapsed", "dependency-cruiser over gui/src.")
    body += (
        "<h3>Per package</h3><details><summary>Show the import graph of each backend package</summary>"
        + "".join(diagram(bundle, p, p.stem) for p in packages)
        + diagram(bundle, architecture / "workspace-modules.svg", "Backend workspace, by module")
        + diagram(bundle, architecture / "gui-core.svg", "GUI, functional core expanded")
        + "</details>"
    )
    body += diagram(
        bundle,
        DIAGRAMS / "domain/evidence.svg",
        "Evidence graph",
        "Which receipts and steps depend on which, from core's audit rules.",
    )
    return section(
        "architecture",
        "Architecture",
        "Import graphs of the backend and the GUI, and the domain's evidence graph.",
        body,
    )


def page_recipes(listed: list[dict[str, Any]], bundle: Bundle) -> str:
    rows = [
        [
            f"<code>{esc(r['name'])}</code>" + (' <span class="badge">private</span>' if r["private"] else ""),
            esc(r["group"]),
            esc(r["doc"]),
            " ".join(f"<code>{esc(p)}</code>" for p in r["parameters"]),
            " ".join(f"<code>{esc(d)}</code>" for d in r["dependencies"]),
        ]
        for r in listed
    ]
    public = sum(not r["private"] for r in listed)
    body = filter_box("recipe-table", "Filter recipes…") + table(
        ["Recipe", "Group", "What it does", "Parameters", "Runs first"], rows, "recipe-table"
    )
    body += diagram(
        bundle,
        DIAGRAMS / "just-recipes.svg",
        "Recipe dependency graph",
        "Prerequisites point to the recipe that consumes them.",
    )
    return section(
        "just-recipes",
        "Just recipes",
        f"{public} public recipes and {len(listed) - public} private ones, from <code>just --dump</code>.",
        body,
    )


def page_configuration() -> str:
    contract = json.loads(ENVIRONMENT.read_text())
    rows = []
    for name, variable in sorted(contract["variables"].items()):
        default = variable.get("schema", {}).get("default", "")
        rows.append(
            [
                f"<code>{esc(name)}</code>",
                esc(variable.get("owner", "")),
                esc(variable.get("kind", "")),
                f"<code>{esc(default)}</code>" if default not in ("", None) else '<span class="muted">—</span>',
            ]
        )
    for pattern, variable in contract.get("patterns", {}).items():
        rows.append(
            [
                f"<code>{esc(pattern)}</code>",
                esc(variable.get("owner", "")),
                esc(variable.get("kind", "")),
                '<span class="muted">pattern</span>',
            ]
        )
    kinds = Counter(v.get("kind", "") for v in contract["variables"].values())
    lede = (
        "The environment-variable contract (<code>contracts/config/environment.json</code>): "
        + ", ".join(f"{n} {k}" for k, n in kinds.most_common())
        + "."
    )
    return section(
        "configuration",
        "Configuration",
        lede,
        filter_box("env-table", "Filter variables…")
        + table(["Variable", "Owner", "Kind", "Default"], rows, "env-table"),
    )


def page_api() -> str:
    spec = json.loads(OPENAPI.read_text())
    rows = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            rows.append(
                [
                    esc(", ".join(operation.get("tags", []))),
                    f"<code>{esc(method.upper())}</code>",
                    f"<code>{esc(path)}</code>",
                    esc(operation.get("summary", "")),
                ]
            )
    rows.sort(key=lambda r: (r[0], r[2]))
    lede = f"{len(rows)} operations on {len(spec['paths'])} paths, from <code>contracts/openapi.json</code>."
    return section(
        "api",
        "API",
        lede,
        filter_box("api-table", "Filter operations…") + table(["Tag", "Method", "Path", "Summary"], rows, "api-table"),
    )


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    teaser: str
    body: str


def frame(page: Page, pages: list[Page], now: Head) -> str:
    """One page of the overview, with the sidebar that links them all."""
    links = "".join(
        f'<a href="{p.slug}.html"{' class="current"' if p.slug == page.slug else ""}>{p.title}</a>' for p in pages
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(page.title)} · repo2ree overview</title><style>{STYLE}</style></head>"
        f'<body><div class="layout"><nav><h1><a href="index.html">repo2ree</a></h1>'
        f'<div class="sub">overview at <code>{now.revision[:8]}</code></div>{links}</nav>'
        f"<main>{page.body}</main></div><script>{SCRIPT}</script></body></html>"
    )


def file_tree(declared: zone_map.Zones, files: list[str]) -> str:
    """The repository's top level, alphabetically, each entry coloured by the zones of the files under it."""
    entries: dict[str, Counter[str]] = defaultdict(Counter)
    for path in files:
        top, separator, _ = path.partition("/")
        found = declared.entry(path)
        entries[top + separator][found.zone if found else "unclaimed"] += 1
    order = [zone.name for zone in declared.zones]
    rows = []
    names = sorted(entries, key=lambda name: name.lstrip(".").lower())
    for index, name in enumerate(names):
        zones = sorted(
            entries[name], key=lambda zone: (-entries[name][zone], order.index(zone) if zone in order else 99)
        )
        main = zones[0]
        branch = "└──" if index == len(names) - 1 else "├──"
        dots = "".join(f'<span class="dot zone-{esc(zone)}"></span>' for zone in zones)
        title = ", ".join(f"{zone} {entries[name][zone]}" for zone in zones)
        rows.append(
            f'<a class="tree-row" href="zones.html#zone-{esc(main)}" title="{esc(title)}">'
            f'<span class="branch">{branch}</span><span class="name zone-text-{esc(main)}">{esc(name)}</span>'
            f'<span class="dots">{dots}</span></a>'
        )
    legend = "".join(
        f'<a class="legend-item" href="zones.html#zone-{esc(zone.name)}">'
        f'<span class="dot zone-{esc(zone.name)}"></span>'
        f"{esc(zone.name)}{' (protected)' if zone.protected else ''}</a>"
        for zone in declared.zones
    )
    return (
        '<section><h2>Repository</h2><p class="lede">The top level, coloured by zone; a directory holding more '
        "than one zone shows a dot for each, largest first. "
        'The <a href="zones.html">Zones</a> page has the details.</p>'
        f'<div class="tree-legend">{legend}</div><div class="tree"><div class="tree-root">repo2ree/</div>'
        f"{''.join(rows)}</div></section>"
    )


def landing(now: Head, found: list[Certificate], pages: list[Page], tree: str) -> str:
    cards = "".join(
        f'<a class="card link" href="{p.slug}.html"><div class="v">{esc(p.title)}</div>'
        f'<div class="muted">{p.teaser}</div></a>'
        for p in pages
    )
    return page_overview(now, found) + tree + f'<section><h2>Pages</h2><div class="cards">{cards}</div></section>'


def bundle_name(now: Head) -> str:
    """The folder an overview of this tree goes to: its commit, marked when the tree differs from it."""
    return now.revision[:12] + ("-dirty" if now.dirty else "")


def provenance(now: Head, receipt: dict[str, Any] | None) -> dict[str, Any]:
    working = git("diff", "HEAD", "--binary") + git("status", "--porcelain")
    return {
        "revision": now.revision,
        "tree": now.tree,
        "dirty": now.dirty,
        "working_tree_sha256": hashlib.sha256(working.encode()).hexdigest() if now.dirty else None,
        "generated": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "command": "python scripts/overview/build.py",
        "receipt_revision": (receipt or {}).get("revision"),
    }


def page_provenance(facts: dict[str, Any]) -> str:
    receipt = facts["receipt_revision"]
    if receipt is None:
        evidence = "no behaviour receipt, so no test evidence"
    elif receipt == facts["revision"]:
        evidence = "test evidence from the receipt for this same commit"
    else:
        evidence = (
            f'<span class="state-stale">test evidence from an older commit, <code>{esc(receipt[:10])}</code></span>'
        )
    tree = "with uncommitted changes" if facts["dirty"] else "clean"
    return (
        '<section><h2>Provenance</h2><p class="lede">'
        f"Built from <code>{esc(facts['revision'][:10])}</code> ({tree}) at {esc(facts['generated'])}, "
        f"with {evidence}. Everything shown from outside the tree is copied into this folder; "
        'see <a href="manifest.json">manifest.json</a>.</p></section>'
    )


def build(output: Path | None) -> Path:
    now = head()
    target = output or OVERVIEWS / bundle_name(now)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    bundle = Bundle(target, now.revision)
    declared = zone_map.load()
    found, receipt = certificates(now)
    runs, tests = bundle_evidence(bundle, receipt)
    edges, rules = suite_coverage(runs)
    extras = suite_extras(runs)
    _, unreached = excuses()
    spec = load_spec()
    listed = recipes()
    environment = json.loads(ENVIRONMENT.read_text())["variables"]
    operations = sum(len(methods) for methods in json.loads(OPENAPI.read_text())["paths"].values())
    protected = sum(1 for e in declared.entries if declared.zone(e.zone).protected)
    coverage = (receipt or {}).get("coverage", {})
    facts = provenance(now, receipt)
    pages = [
        Page(
            "zones",
            "Zones",
            f"{len(declared.zones)} zones; {protected} protected entries humans review",
            page_zones(declared, zone_map.problems(declared, zone_map.tracked())),
        ),
        Page(
            "behaviour-gate",
            "Behaviour gate",
            f"{len((receipt or {}).get('tests', []))} tests in the last receipt; "
            f"{coverage.get('reached', '?')} of {coverage.get('declared', '?')} specified items reached",
            page_gates(receipt, unreached, bundle, tests),
        ),
        Page(
            "vocabulary",
            "Vocabulary",
            f"{len(spec.entities)} entities and {len(spec.boundaries)} boundary owners record, "
            f"{sum(len(e.facts) for e in spec.entities.values())} entity facts",
            page_vocabulary(spec),
        ),
        Page(
            "specification",
            "Specification",
            f"{len(spec.entities)} state machines, "
            f"{sum(len(t) for e in spec.entities.values() for t in e.edges.values())} edges, "
            f"{len(spec.invariants)} invariants",
            page_specification(spec),
        ),
        Page(
            "coverage",
            "Coverage",
            f"How the last receipt's tests exercised the specification: "
            f"{coverage.get('reached', '?')} of {coverage.get('declared', '?')} items reached",
            page_coverage(spec, edges, rules, unreached, extras),
        ),
        Page("architecture", "Architecture", "Import graphs of the backend and the GUI", page_architecture(bundle)),
        Page(
            "just-recipes",
            "Just recipes",
            f"{sum(not r['private'] for r in listed)} public recipes",
            page_recipes(listed, bundle),
        ),
        Page("configuration", "Configuration", f"{len(environment)} environment variables", page_configuration()),
        Page("api", "API", f"{operations} operations", page_api()),
    ]
    tree = file_tree(declared, zone_map.tracked())
    home = Page("index", "Overview", "", landing(now, found, pages, tree) + page_provenance(facts))
    everything = [home, *pages]
    for page in everything:
        (target / f"{page.slug}.html").write_text(frame(page, everything, now), encoding="utf-8")
    manifest = facts | {"copied": bundle.copied, "referenced": bundle.referenced}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if output is None:
        latest = OVERVIEWS / "latest"
        latest.unlink(missing_ok=True)
        latest.symlink_to(target.name)
    copied = sum((target / entry["path"]).stat().st_size for entry in bundle.copied)
    print(
        f"wrote {target} ({len(everything)} pages; {len(bundle.copied)} files copied, {copied / 1e6:.1f} MB; "
        f"{len(bundle.referenced)} referenced by hash)"
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, help="write here instead of reports/overview/<revision>/")
    target = build(parser.parse_args().output)
    print(f"open {target / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
