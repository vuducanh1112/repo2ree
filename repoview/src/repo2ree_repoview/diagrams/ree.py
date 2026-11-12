"""Draw the REE contract's anatomy: every part of an REE, the files it is about, and how the two meet.

From the contract alone: contracts/ree/ree.schema.json and the file tree it points into,
contracts/ree/layout.json. The definition's sections stand on the left, the receipts and the bundle in
the middle, the tree on the right. Each digest field is joined to the files it is the digest of
(``x-digest-of``), so a declaration and the receipts that ran it meet at the same file; a path field
names where it is resolved (``x-relative-to``). Where no file joins them, a declared field is joined
straight to the receipt field that records it: the section's own name, the same fields, or the
experiment's name.

    python -m repo2ree_repoview ree-anatomy -o reports/diagrams/ree/anatomy.svg
"""

from __future__ import annotations

import argparse
import html
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from repo2ree_repoview.diagrams import emit
from repo2ree_repoview.documents import Document
from repo2ree_repoview.graphviz import inline_svg, quote
from repo2ree_repoview.repository import ROOT

SCHEMA = ROOT / "contracts/ree/ree.schema.json"
LAYOUT = ROOT / "contracts/ree/layout.json"

Role = Literal["definition", "receipt", "bundle"]
Covers = Literal["file", "tree", "paths", "subject", "outside"]
Capture = Literal["git", "lfs", "never"]
Shape = Literal["one", "optional", "list", "map"]
Pairing = Literal["field", "section", "same fields"]

INK = "#0f172a"
MUTED = "#475569"
ZONE = "#94a3b8"
PAIR = "#0f766e"
DIGEST = "#64748b"
TREE = ("#f8fafc", "#475569")
# How each kind of capture reads in the tree.
CAPTURES: dict[Capture, str] = {"git": "#0f172a", "lfs": "#7c3aed", "never": "#94a3b8"}
# Fill and frame of each role's boxes; the receipts and declared fields as the evidence graph draws them.
COLOURS: dict[Role, tuple[str, str]] = {
    "definition": ("#e2ece8", "#0f766e"),
    "receipt": ("#dbeafe", "#3b82f6"),
    "bundle": ("#f3e8ff", "#7c3aed"),
}


class DigestOf(Document):
    covers: Covers
    entries: tuple[str, ...] = ()
    named_by: str | None = None


class Property(Document):
    ref: str | None = Field(default=None, alias="$ref")
    digest_of: DigestOf | None = Field(default=None, alias="x-digest-of")
    relative_to: tuple[str, ...] = Field(default=(), alias="x-relative-to")
    any_of: tuple[Property, ...] = Field(default=(), alias="anyOf")
    items: Property | None = None
    additional_properties: Property | bool | None = Field(default=None, alias="additionalProperties")
    const: str | int | None = None
    enum: tuple[str | int, ...] = ()
    type: str | None = None
    format: str | None = None

    def target(self) -> tuple[str, Shape] | None:
        """The $def this property holds, and how it holds it."""
        if self.ref:
            return self.ref.rsplit("/", 1)[-1], "one"
        for alternative in self.any_of:
            if alternative.ref:
                return alternative.ref.rsplit("/", 1)[-1], "optional"
        if self.items and self.items.ref:
            return self.items.ref.rsplit("/", 1)[-1], "list"
        if isinstance(self.additional_properties, Property) and self.additional_properties.ref:
            return self.additional_properties.ref.rsplit("/", 1)[-1], "map"
        return None

    def annotated(self) -> Property:
        """Where its ``x-`` annotations sit: on itself, on its non-null branch, or on its items."""
        for place in (self, *self.any_of, *([self.items] if self.items else [])):
            if place.digest_of or place.relative_to:
                return place
        return self

    def text(self) -> str:
        """The property's type, as short as it reads in the drawing."""
        annotated = self.annotated()
        optional = "?" if any(alternative.type == "null" for alternative in self.any_of) else ""
        if annotated.relative_to:
            roots = ", ".join("the root" if root == "." else f"{root}/" for root in annotated.relative_to)
            listed = "paths" if self.items else "path"
            return f"{listed} in {roots}{optional}"
        if annotated.digest_of:
            return {"subject": "digest of the subject", "outside": "digest of an outside thing"}.get(
                annotated.digest_of.covers, "digest"
            ) + optional
        if found := self.target():
            name, shape = found
            return {"one": name, "optional": f"{name}?", "list": f"[{name}]", "map": f"{{name: {name}}}"}[shape]
        if self.const is not None:
            return f"= {self.const}"
        if self.enum:
            return " | ".join(str(value) for value in self.enum)
        types = [alternative.type for alternative in self.any_of] or [self.type]
        named = next((kind for kind in types if kind and kind != "null"), None)
        if named == "array":
            named = f"[{self.items.type if self.items else 'any'}]"
        elif named == "object":
            named = "{…}"
        elif self.format == "date-time":
            named = "datetime"
        for alternative in self.any_of:
            if alternative.format == "date-time":
                named = "datetime"
        return (named or "any") + ("?" if "null" in types else "")


class Definition(Document):
    properties: dict[str, Property] = Field(default_factory=dict)


class TreeEntry(Document):
    name: str
    kind: Literal["file", "directory"]
    origin: str
    capture: Capture
    description: str
    key: str | None = None
    named_by: str | None = None
    ree_root: bool = False
    children: tuple[TreeEntry, ...] = ()

    def walk(self, at: str = "", depth: int = 0) -> Iterator[tuple[str, int, TreeEntry]]:
        """Every entry below this one, depth first, by its path from the root as the tree spells it."""
        for child in self.children:
            path = f"{at}/{child.name}" if at else child.name
            yield path, depth, child
            yield from child.walk(path, depth + 1)


class Layout(Document):
    format: Literal["repo2ree-ree-layout/1"]
    root: TreeEntry


class Schema(Document):
    defs: dict[str, Definition] = Field(alias="$defs")
    properties: dict[str, Property]

    def of(self, prop: Property) -> Definition:
        found = prop.target()
        if found is None:
            raise ValueError("the property holds no $def")
        return self.defs[found[0]]


@dataclass(frozen=True)
class Box:
    """One part of an REE: a $def with the fields it shows."""

    name: str
    role: Role
    type: str
    fields: dict[str, Property]
    note: str = ""
    title: str = ""

    @property
    def node(self) -> str:
        return f"{self.role}:{self.name}"


@dataclass(frozen=True)
class Pair:
    """A declared field, and the receipt field that records what a run took it to be."""

    section: str
    field: str | None
    receipt: str
    receipt_field: str
    pairing: Pairing


@dataclass(frozen=True)
class Link:
    """A digest field, and an entry of the tree it is the digest of (``.`` for the root)."""

    node: str
    field: str
    role: Role
    entry: str


@dataclass(frozen=True)
class Anatomy:
    boxes: tuple[Box, ...]
    shared: tuple[str, ...]
    pairs: tuple[Pair, ...]
    tree: TreeEntry
    links: tuple[Link, ...]


def anatomy(schema: Schema, layout: Layout) -> Anatomy:
    """Every part of an REE, from the schema's root down to the sections of its definition and receipts."""
    subject = schema.of(schema.properties["subject"])
    definition = schema.of(subject.properties["definition"])
    receipts = schema.of(subject.properties["receipts"])
    receipt_fields = {name: schema.of(prop).properties for name, prop in receipts.properties.items()}
    shared = tuple(
        name for name in next(iter(receipt_fields.values())) if all(name in f for f in receipt_fields.values())
    )

    boxes: list[Box] = []
    scalars = {name: prop for name, prop in definition.properties.items() if prop.target() is None}
    if scalars:
        boxes.append(Box("definition", "definition", "ReeDefinition", scalars))
    for name, prop in definition.properties.items():
        if found := prop.target():
            title = f"{name}[*]" if found[1] == "list" else name
            boxes.append(Box(name, "definition", prop.text(), schema.of(prop).properties, title=title))
    for name, prop in receipts.properties.items():
        fields = schema.of(prop).properties
        operation = fields.get("operation")
        note = f"by {operation.const}" if operation and operation.const is not None else ""
        kept = {field: p for field, p in fields.items() if field not in shared}
        found = prop.target()
        title = f"{name}{{name}}" if found and found[1] == "map" else name
        boxes.append(Box(name, "receipt", prop.text(), kept, note, title))
    parts = [(n, p) for n, p in subject.properties.items() if n not in ("definition", "receipts")]
    parts += [(n, p) for n, p in schema.properties.items() if n != "subject"]
    for name, prop in parts:
        if prop.target() is not None:
            boxes.append(Box(name, "bundle", prop.text(), expanded(schema, schema.of(prop).properties)))
    declared = {name: schema.of(prop).properties for name, prop in definition.properties.items() if prop.target()}
    paired = [pair for pair in pairs(schema, definition, receipt_fields, set(shared)) if not in_tree(declared, pair)]
    return Anatomy(tuple(boxes), shared, tuple(paired), layout.root, tuple(links(boxes, layout.root)))


def expanded(schema: Schema, fields: dict[str, Property]) -> dict[str, Property]:
    """A bundle part's fields, with the fields of each list item beneath its list, e.g. ``entries[*].digest``."""
    shown: dict[str, Property] = {}
    for name, prop in fields.items():
        shown[name] = prop
        if (found := prop.target()) and found[1] == "list":
            shown |= {f"{name}[*].{inner}": item for inner, item in schema.of(prop).properties.items()}
    return shown


def in_tree(declared: dict[str, dict[str, Property]], pair: Pair) -> bool:
    """Whether the declared field is about a file, so the two meet in the tree rather than by a pairing."""
    if pair.field is None:
        return False
    annotated = declared[pair.section][pair.field].annotated()
    return annotated.digest_of is not None or bool(annotated.relative_to)


def links(boxes: Iterable[Box], tree: TreeEntry) -> Iterator[Link]:
    known = {".", *(path for path, _, _ in tree.walk())}
    for box in boxes:
        for name, prop in box.fields.items():
            of = prop.annotated().digest_of
            if of is None:
                continue
            entries = ("ree.json",) if of.covers == "subject" else of.entries
            for entry in entries:
                if entry not in known:
                    raise ValueError(f"{box.name}.{name} is the digest of {entry}, which the tree does not name")
                yield Link(box.node, name, box.role, entry)


def pairs(
    schema: Schema, definition: Definition, receipts: dict[str, dict[str, Property]], shared: set[str]
) -> Iterator[Pair]:
    for section, prop in definition.properties.items():
        if prop.target() is None:
            continue
        fields = schema.of(prop).properties
        singular = section.removesuffix("s")
        for receipt, recorded in receipts.items():
            if section in recorded:
                yield Pair(section, None, receipt, section, "section")
            for field in fields:
                if field in recorded and field not in shared:
                    yield Pair(section, field, receipt, field, "field")
                elif singular != section and f"{singular}_{field}" in recorded:
                    yield Pair(section, field, receipt, f"{singular}_{field}", "field")
            for name, other in recorded.items():
                if other.target() and set(schema.of(other).properties) == set(fields) and name != section:
                    yield Pair(section, None, receipt, name, "same fields")


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def table(box: Box) -> str:
    fill, frame = COLOURS[box.role]
    title = box.title or box.name
    head = (
        f'<TR><TD ALIGN="LEFT" BGCOLOR="{frame}" COLSPAN="2" PORT="_"><FONT COLOR="#ffffff"><B>{esc(title)}</B>  '
        f'<FONT POINT-SIZE="9">{esc(box.type)}</FONT></FONT></TD></TR>'
    )
    note = (
        f'<TR><TD ALIGN="LEFT" COLSPAN="2"><FONT POINT-SIZE="9" COLOR="{MUTED}">{esc(box.note)}</FONT></TD></TR>'
        if box.note
        else ""
    )
    rows = "".join(
        f'<TR><TD ALIGN="LEFT" PORT="{esc(name)}">'
        f'<FONT FACE="Courier" POINT-SIZE="10" COLOR="{INK}">{esc(name)}</FONT></TD>'
        f'<TD ALIGN="LEFT" PORT="{esc(name)}__type">'
        f'<FONT POINT-SIZE="9" COLOR="{MUTED}">{esc(prop.text())}</FONT></TD></TR>'
        for name, prop in box.fields.items()
    )
    return (
        f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" BGCOLOR="{fill}" COLOR="{frame}">'
        f"{head}{note}{rows}</TABLE>"
    )


def tree_table(tree: TreeEntry) -> str:
    """The tree as one listing: each entry indented under its directory, with how a capture carries it."""
    fill, frame = TREE
    head = (
        f'<TR><TD ALIGN="LEFT" BGCOLOR="{frame}" PORT=".&lt;"><FONT COLOR="#ffffff"><B>./</B></FONT></TD>'
        f'<TD ALIGN="LEFT" BGCOLOR="{frame}"><FONT COLOR="#ffffff">'
        '<FONT POINT-SIZE="9">an REE root</FONT></FONT></TD></TR>'
    )
    rows = []
    for path, depth, entry in tree.walk():
        colour = CAPTURES[entry.capture]
        name = entry.name + ("/" if entry.kind == "directory" else "")
        notes: list[str] = [entry.capture]
        if entry.named_by:
            notes.append(f"named by {entry.named_by.removeprefix('definition.')}")
        if entry.ree_root:
            notes.append("an REE root too")
        rows.append(
            f'<TR><TD ALIGN="LEFT" PORT="{esc(path)}&lt;">{"&#160;" * 3 * depth}'
            f'<FONT FACE="Courier" POINT-SIZE="10" COLOR="{colour}">{esc(name)}</FONT></TD>'
            '<TD ALIGN="LEFT">'
            f'<FONT POINT-SIZE="9" COLOR="{colour}">{esc(" · ".join(notes))}</FONT></TD></TR>'
        )
    return (
        f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" BGCOLOR="{fill}" COLOR="{frame}">'
        f"{head}{''.join(rows)}</TABLE>"
    )


CLUSTERS: dict[Role | Literal["tree"], str] = {
    "definition": '<B>definition</B>  <FONT POINT-SIZE="10">what the author declares</FONT>',
    "receipt": '<B>receipts</B>  <FONT POINT-SIZE="10">what a run observed</FONT>',
    "bundle": "<B>bundle and seal</B>",
    "tree": '<B>file tree</B>  <FONT POINT-SIZE="10">contracts/ree/layout.json</FONT>',
}


def render_dot(drawn: Anatomy) -> str:
    lines = [
        "digraph anatomy {",
        '  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.25; ranksep=1.4;',
        '  node [shape=plain, fontname="Helvetica", fontsize=11];',
        f'  edge [color="{PAIR}", fontname="Helvetica", fontsize=9, fontcolor="{MUTED}", arrowsize=0.6];',
        (
            f'  graph [fontname="Helvetica", fontsize=12, fontcolor="{INK}", color="{ZONE}",'
            ' style="rounded,dashed", labeljust=l];'
        ),
    ]
    for role, label in CLUSTERS.items():
        if role == "receipt" and drawn.shared:
            every = esc(", ".join(drawn.shared))
            label += f'<BR ALIGN="LEFT"/><FONT POINT-SIZE="9" COLOR="{MUTED}">every receipt also carries {every}</FONT>'
        lines.append(f"  subgraph cluster_{role} {{ margin=14; label=<{label}>;")
        if role == "tree":
            lines.append(f'    "tree" [label=<{tree_table(drawn.tree)}>];')
        lines.extend(f"    {quote(box.node)} [label=<{table(box)}>];" for box in drawn.boxes if box.role == role)
        lines.append("  }")
    for link in drawn.links:
        row = f'"tree":{quote(link.entry + "<")}:w'
        lines.append(f'  {quote(link.node)}:{quote(link.field + "__type")}:e -> {row} [color="{DIGEST}"];')
    for pair in drawn.pairs:
        tail = f"{quote('definition:' + pair.section)}:" + (
            f"{quote(pair.field + '__type')}:e" if pair.field else f"{quote('_')}:e"
        )
        head = f"{quote('receipt:' + pair.receipt)}:{quote(pair.receipt_field)}:w"
        style = {"field": "", "section": " [penwidth=2]", "same fields": ' [style=dashed, label="same fields"]'}
        lines.append(f"  {tail} -> {head}{style[pair.pairing]};")
    lines.append("}")
    return "\n".join(lines)


def svg(drawn: Anatomy) -> str:
    drawing = inline_svg(render_dot(drawn))
    drawing = re.sub(r'font-family="Courier[^"]*"', 'font-family="ui-monospace,Menlo,monospace"', drawing)
    return re.sub(r'font-family="Helvetica[^"]*"', 'font-family="system-ui,sans-serif"', drawing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--schema", type=Path, default=SCHEMA, help="the REE contract's JSON Schema")
    parser.add_argument("--layout", type=Path, default=LAYOUT, help="the REE file tree the schema points into")
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()
    try:
        schema = Schema.model_validate_json(args.schema.read_text(encoding="utf-8"))
        layout = Layout.model_validate_json(args.layout.read_text(encoding="utf-8"))
        emit(svg(anatomy(schema, layout)), args.output)
    except (OSError, ValueError, ValidationError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
