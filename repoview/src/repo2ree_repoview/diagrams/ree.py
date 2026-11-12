"""Draw the REE contract's anatomy: every part of an REE, and which declared field each receipt repeats.

From contracts/ree/ree.schema.json alone. The definition's sections stand on the left, the receipts
on the right, the bundle and seal apart. An edge joins a declared field to the receipt field that
records what a run took it to be: the same name, the section's own name, or the same fields.

    python -m repo2ree_repoview ree-anatomy -o reports/diagrams/ree/anatomy.svg
"""

from __future__ import annotations

import argparse
import html
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from repo2ree_repoview.diagrams import emit
from repo2ree_repoview.documents import Document
from repo2ree_repoview.graphviz import inline_svg, quote
from repo2ree_repoview.repository import ROOT

SCHEMA = ROOT / "contracts/ree/ree.schema.json"

Role = Literal["definition", "receipt", "bundle"]
Shape = Literal["one", "optional", "list", "map"]
Pairing = Literal["field", "section", "same fields"]

INK = "#0f172a"
MUTED = "#475569"
ZONE = "#94a3b8"
PAIR = "#0f766e"
# Fill and frame of each role's boxes; the receipts and declared fields as the evidence graph draws them.
COLOURS: dict[Role, tuple[str, str]] = {
    "definition": ("#e2ece8", "#0f766e"),
    "receipt": ("#dbeafe", "#3b82f6"),
    "bundle": ("#f3e8ff", "#7c3aed"),
}


class Property(Document):
    ref: str | None = Field(default=None, alias="$ref")
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

    def text(self) -> str:
        """The property's type, as short as it reads in the drawing."""
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
class Anatomy:
    boxes: tuple[Box, ...]
    shared: tuple[str, ...]
    pairs: tuple[Pair, ...]


def anatomy(schema: Schema) -> Anatomy:
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
            boxes.append(Box(name, "bundle", prop.text(), schema.of(prop).properties))
    return Anatomy(tuple(boxes), shared, tuple(pairs(schema, definition, receipt_fields, set(shared))))


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


CLUSTERS: dict[Role, str] = {
    "definition": '<B>definition</B>  <FONT POINT-SIZE="10">what the author declares</FONT>',
    "receipt": '<B>receipts</B>  <FONT POINT-SIZE="10">what a run observed</FONT>',
    "bundle": "<B>bundle and seal</B>",
}


def render_dot(drawn: Anatomy) -> str:
    lines = [
        "digraph anatomy {",
        '  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.25; ranksep=1.6;',
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
        lines.extend(f"    {quote(box.node)} [label=<{table(box)}>];" for box in drawn.boxes if box.role == role)
        lines.append("  }")
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
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")
    args = parser.parse_args()
    try:
        emit(svg(anatomy(Schema.model_validate_json(args.schema.read_text(encoding="utf-8")))), args.output)
    except (OSError, ValueError, ValidationError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
