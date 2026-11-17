"""Draw the committed JSON contracts as graphs: each model a box of its fields, an edge from a field to each model
it holds.

Each contract is drawn from the entry points it names itself, one drawing each, so a drawing shows what one reader
of the contract meets and nothing more: every command's outputs (``cli-schema``), every message, operation's outputs
and read (``protocol-schema``), the models each group of HTTP operations sends and answers with (``openapi``), the
behaviour journal's records (``behaviour-schema``), and the REE document (``ree-schema``). Each is found by that name
in the contract registry, as ``just export-contracts`` exports it.

    python -m repo2ree_repoview contract-graphs -o reports/diagrams/contracts

prints the drawings it wrote, one path a line, and removes the ones of entry points that are gone.
"""

from __future__ import annotations

import argparse
import html
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, JsonValue, ValidationError

from repo2ree_repoview.documents import Document
from repo2ree_repoview.graphviz import inline_svg, quote
from repo2ree_repoview.overview.exports import ContractName, Contracts

Shape = Literal["one", "optional", "list", "map", "union"]
Kind = Literal["entry", "model", "alias"]

INK = "#0f172a"
MUTED = "#475569"
EDGE = "#64748b"
# Fill and frame of each kind of box: the entry point, a model with fields, and a union or enumeration.
COLOURS: dict[Kind, tuple[str, str]] = {
    "entry": ("#e2ece8", "#0f766e"),
    "model": ("#dbeafe", "#3b82f6"),
    "alias": ("#f1f5f9", "#64748b"),
}
# Longer types are cut at this many characters, so a long enumeration does not widen its box past reading.
TYPE_WIDTH = 56


class Node(Document):
    """A JSON Schema, read for what a drawing shows: its fields, the models it holds, and its type."""

    ref: str | None = Field(default=None, alias="$ref")
    title: str | None = None
    type: str | list[str] | None = None
    format: str | None = None
    const: JsonValue = None
    enum: tuple[JsonValue, ...] = ()
    properties: dict[str, Node] = Field(default_factory=dict)
    required: tuple[str, ...] = ()
    any_of: tuple[Node, ...] = Field(default=(), alias="anyOf")
    one_of: tuple[Node, ...] = Field(default=(), alias="oneOf")
    all_of: tuple[Node, ...] = Field(default=(), alias="allOf")
    items: Node | None = None
    additional_properties: Node | bool | None = Field(default=None, alias="additionalProperties")
    content_media_type: str | None = Field(default=None, alias="contentMediaType")

    @property
    def name(self) -> str | None:
        return self.ref.rsplit("/", 1)[-1] if self.ref else None

    @property
    def members(self) -> tuple[Node, ...]:
        return self.one_of or self.any_of

    def held(self, shape: Shape = "one") -> Iterator[tuple[str, Shape]]:
        """Every model this schema holds, and how: itself, one of a union, a list's items, or a map's values."""
        if self.name:
            yield self.name, shape
            return
        for member in (*self.members, *self.all_of):
            nullable = any(other.type == "null" for other in self.members)
            yield from member.held("optional" if nullable and shape == "one" else "union" if shape == "one" else shape)
        if self.items is not None:
            yield from self.items.held("list")
        if isinstance(self.additional_properties, Node):
            yield from self.additional_properties.held("map")

    def text(self) -> str:
        """The schema's type, as short as it reads in a box."""
        if self.name:
            return self.name
        if self.members:
            parts = [member.text() for member in self.members if member.type != "null"]
            optional = "?" if any(member.type == "null" for member in self.members) else ""
            return cut(" | ".join(parts)) + optional
        if self.all_of:
            return " & ".join(member.text() for member in self.all_of)
        if self.const is not None:
            return f"= {self.const}"
        if self.enum:
            return cut(" | ".join(str(value) for value in self.enum))
        if self.content_media_type:
            return "bytes" if "octet-stream" in self.content_media_type else self.content_media_type
        kind = self.type if isinstance(self.type, str) else next((t for t in self.type or () if t != "null"), None)
        if kind == "array":
            return f"[{self.items.text() if self.items else 'any'}]"
        if kind == "object":
            if isinstance(self.additional_properties, Node):
                return f"{{str: {self.additional_properties.text()}}}"
            return "{…}" if not self.properties else "object"
        if self.format == "date-time":
            return "datetime"
        return kind or "any"


def cut(text: str) -> str:
    return text if len(text) <= TYPE_WIDTH else text[: TYPE_WIDTH - 1] + "…"


# ================================================
# What each contract names as its entry points
# ================================================


@dataclass(frozen=True)
class Entry:
    """One entry point of a contract: the schema a reader starts from, and what its drawing is called."""

    slug: str
    title: str
    root: Node


@dataclass(frozen=True)
class Contract:
    """A contract, its models, and the entry points it is drawn from; keyed by its name in the registry."""

    key: ContractName
    path: str
    title: str
    defs: dict[str, Node]
    entries: tuple[Entry, ...]

    def reached(self, entry: Entry) -> list[str]:
        """The models a drawing of ``entry`` shows: every one it holds, at any depth, in the order met."""
        found: list[str] = []
        todo = [name for _field, name, _shape in fields_of(entry.root)]
        while todo:
            name = todo.pop(0)
            if name in found or name not in self.defs:
                continue
            found.append(name)
            todo += [held for _field, held, _shape in fields_of(self.defs[name])]
        return found


def fields_of(node: Node) -> Iterator[tuple[str, str, Shape]]:
    """Each row of a box, and each model the row holds: its fields, or for a union, its members."""
    for field, schema in node.properties.items():
        for name, shape in schema.held():
            yield field, name, shape
    if not node.properties:
        for index, member in enumerate(node.members):
            for name, shape in member.held():
                yield f"#{index}", name, shape
        if node.items is not None or isinstance(node.additional_properties, Node):
            for name, shape in node.held():
                yield "#items", name, shape
    else:
        for index, member in enumerate(node.members):
            for name, _shape in member.held():
                yield f"#{index}", name, "union"


def slug(text: str) -> str:
    """An entry point's name as a file and an anchor spell it."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _entry(slug: str, title: str, rows: dict[str, JsonValue]) -> Entry:
    """An entry point drawn as a box of its own, whose rows are the schemas a reader starts from."""
    return Entry(slug, title, Node.model_validate({"properties": rows}))


class _CliCommand(Document):
    words: tuple[str, ...]
    outputs: dict[str, JsonValue] | None = None


class _Cli(Document):
    result: dict[str, JsonValue]
    commands: tuple[_CliCommand, ...]
    defs: dict[str, Node] = Field(default_factory=dict, alias="$defs")


def cli_contract(registry: Contracts) -> Contract:
    found = registry.entry("cli-schema")
    document = _Cli.model_validate_json(found.file.read_bytes())
    entries = [_entry("result", "Every command's result", {"result": document.result})]
    entries += [
        _entry(slug(" ".join(command.words)), f"ree {' '.join(command.words)}", {"outputs": command.outputs})
        for command in document.commands
        if command.outputs
    ]
    return Contract("cli-schema", found.path, "Command line", document.defs, tuple(entries))


class _Read(Document):
    query: dict[str, JsonValue]
    reply: dict[str, JsonValue]


class _Protocol(Document):
    messages: dict[str, dict[str, JsonValue]] = Field(alias="x-messages")
    outputs: dict[str, dict[str, JsonValue]] = Field(alias="x-outputs")
    queries: dict[str, _Read] = Field(alias="x-queries")
    defs: dict[str, Node] = Field(default_factory=dict, alias="$defs")


def protocol_contract(registry: Contracts) -> Contract:
    found = registry.entry("protocol-schema")
    document = _Protocol.model_validate_json(found.file.read_bytes())
    entries = [
        _entry(f"message-{slug(name)}", f"message {name}", {name: schema}) for name, schema in document.messages.items()
    ]
    entries += [
        _entry(f"outputs-{slug(name)}", f"outputs of {name}", {"outputs": schema})
        for name, schema in document.outputs.items()
    ]
    entries += [
        _entry(f"read-{slug(verb)}", f"read {verb}", {"query": read.query, "reply": read.reply})
        for verb, read in document.queries.items()
    ]
    return Contract("protocol-schema", found.path, "Protocol", document.defs, tuple(entries))


class _Media(Document):
    schema_: dict[str, JsonValue] | None = Field(default=None, alias="schema")


class _Body(Document):
    content: dict[str, _Media] = Field(default_factory=dict)

    def carried(self) -> dict[str, JsonValue] | None:
        """What the body carries: its JSON schema, or what kind of bytes."""
        if not self.content:
            return None
        media, carried = next(iter(self.content.items()))
        return carried.schema_ if media == "application/json" else {"contentMediaType": media}


class _Operation(Document):
    operation_id: str = Field(alias="operationId")
    tags: tuple[str, ...] = ()
    request_body: _Body | None = Field(default=None, alias="requestBody")
    responses: dict[str, _Body] = Field(default_factory=dict)


class _Components(Document):
    schemas: dict[str, Node] = Field(default_factory=dict)


class _OpenApi(Document):
    paths: dict[str, dict[str, _Operation | JsonValue]]
    components: _Components


_METHODS = ("get", "post", "put", "patch", "delete")


def openapi_contract(registry: Contracts) -> Contract:
    found = registry.entry("openapi")
    document = _OpenApi.model_validate_json(found.file.read_bytes())
    tagged: dict[str, dict[str, JsonValue]] = {}
    for item in document.paths.values():
        for method, operation in item.items():
            if method not in _METHODS or not isinstance(operation, _Operation):
                continue
            rows = tagged.setdefault(operation.tags[0] if operation.tags else "untagged", {})
            if operation.request_body and (body := operation.request_body.carried()):
                rows[f"{operation.operation_id} ←"] = body
            status = next((code for code in sorted(operation.responses) if code.startswith("2")), None)
            if status and (answer := operation.responses[status].carried()):
                rows[f"{operation.operation_id} → {status}"] = answer
    entries = tuple(_entry(slug(tag), f"{tag} operations", rows) for tag, rows in sorted(tagged.items()) if rows)
    return Contract("openapi", found.path, "HTTP API", document.components.schemas, entries)


class _Rooted(Document):
    """A schema whose root is itself the entry point: its fields, and the records it is one of."""

    properties: dict[str, JsonValue] = Field(default_factory=dict)
    one_of: tuple[JsonValue, ...] = Field(default=(), alias="oneOf")
    required: tuple[str, ...] = ()
    defs: dict[str, Node] = Field(default_factory=dict, alias="$defs")

    def root(self) -> Node:
        return Node.model_validate(
            {"properties": self.properties, "oneOf": list(self.one_of), "required": list(self.required)}
        )


def events_contract(registry: Contracts) -> Contract:
    found = registry.entry("behaviour-schema")
    document = _Rooted.model_validate_json(found.file.read_bytes())
    entries = (Entry("records", "a journal record", document.root()),)
    return Contract("behaviour-schema", found.path, "Behaviour events", document.defs, entries)


def ree_contract(registry: Contracts) -> Contract:
    found = registry.entry("ree-schema")
    document = _Rooted.model_validate_json(found.file.read_bytes())
    entries = (Entry("document", "ree.json", document.root()),)
    return Contract("ree-schema", found.path, "REE document", document.defs, entries)


def contracts(registry: Contracts) -> tuple[Contract, ...]:
    return tuple(
        read(registry) for read in (cli_contract, protocol_contract, openapi_contract, events_contract, ree_contract)
    )


# ================================================
# Drawing
# ================================================


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def port(row: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", row) or "_"


def box(title: str, kind: Kind, node: Node) -> str:
    fill, frame = COLOURS[kind]
    head = (
        f'<TR><TD ALIGN="LEFT" BGCOLOR="{frame}" COLSPAN="2" PORT="_"><FONT COLOR="#ffffff"><B>{esc(title)}</B>'
        "</FONT></TD></TR>"
    )
    rows = [(field, schema.text(), field in node.required) for field, schema in node.properties.items()]
    if not node.properties:
        rows += [(f"#{index}", member.text(), False) for index, member in enumerate(node.members)]
        if not node.members:
            rows.append(("#items", "no fields" if node.type == "object" and not node.items else node.text(), False))
    else:
        rows += [(f"#{index}", f"one of: {member.text()}", False) for index, member in enumerate(node.members)]
    cells = "".join(
        f'<TR><TD ALIGN="LEFT">{_name(field, required or kind == "entry")}</TD>'
        f'<TD ALIGN="LEFT" PORT="{port(field)}"><FONT POINT-SIZE="9" COLOR="{MUTED}">{esc(text)}</FONT></TD></TR>'
        for field, text, required in rows
    )
    return (
        f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" BGCOLOR="{fill}" COLOR="{frame}">'
        f"{head}{cells}</TABLE>"
    )


def _name(field: str, required: bool) -> str:
    """A row's field name, ``?`` when it may be left out; a union member's or a list's row has none."""
    if field.startswith("#"):
        return "&#160;"
    return f'<FONT FACE="Courier" POINT-SIZE="10" COLOR="{INK}">{esc(field)}{"" if required else "?"}</FONT>'


def render_dot(contract: Contract, entry: Entry) -> str:
    reached = contract.reached(entry)
    lines = [
        "digraph contract {",
        '  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.2; ranksep=0.8;',
        '  node [shape=plain, fontname="Helvetica", fontsize=11];',
        f'  edge [color="{EDGE}", fontname="Helvetica", fontsize=8, fontcolor="{MUTED}", arrowsize=0.6];',
        f'  "entry" [label=<{box(entry.title, "entry", entry.root)}>];',
    ]
    for name in reached:
        node = contract.defs[name]
        kind: Kind = "model" if node.properties else "alias"
        lines.append(f"  {quote(name)} [label=<{box(name, kind, node)}>];")
    marks = {"one": "", "optional": "?", "list": "[*]", "map": "{*}", "union": "|"}
    for source, node in (("entry", entry.root), *((name, contract.defs[name]) for name in reached)):
        for field, held, shape in fields_of(node):
            if held in contract.defs:
                label = f' [label="{marks[shape]}"]' if marks[shape] else ""
                lines.append(f"  {quote(source)}:{quote(port(field))}:e -> {quote(held)}:{quote('_')}:w{label};")
    lines.append("}")
    return "\n".join(lines)


def svg(contract: Contract, entry: Entry) -> str:
    drawing = inline_svg(render_dot(contract, entry))
    drawing = re.sub(r'font-family="Courier[^"]*"', 'font-family="ui-monospace,Menlo,monospace"', drawing)
    return re.sub(r'font-family="Helvetica[^"]*"', 'font-family="system-ui,sans-serif"', drawing)


def drawing_path(output: Path, contract: Contract, entry: Entry) -> Path:
    return output / contract.key / f"{entry.slug}.svg"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--output", type=Path, required=True, help="the directory to draw into")
    parser.add_argument("--contracts", type=Path, help="the contract registry as exported (reports/exports/)")
    args = parser.parse_args()
    try:
        drawn = contracts(Contracts.read(args.contracts) if args.contracts else Contracts.read())
        written: set[Path] = set()
        for contract in drawn:
            for entry in contract.entries:
                target = drawing_path(args.output, contract, entry)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(svg(contract, entry), encoding="utf-8")
                written.add(target)
                print(target)
        for stale in set(args.output.glob("*/*.svg")) - written:
            stale.unlink()
        for folder in args.output.iterdir():
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
    except (OSError, ValueError, ValidationError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
