"""The GUI's vocabulary, rendered from the committed OpenAPI contract: the sets of names it reads off the wire.

``gui/src/core/generated/vocabulary.ts`` holds each set as an ``as const`` array and its type, and
``gui/biome.json`` lets a property be spelled as one of their names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
OPENAPI = ROOT / "contracts/openapi.json"
BIOME = ROOT / "gui/biome.json"

Read = Literal["enum", "properties", "receipt_operations"]


@dataclass(frozen=True)
class GuiSet:
    constant: str
    type_name: str
    schema: str
    read: Read
    property: str = ""

    def names(self, schemas: dict[str, Any]) -> list[str]:
        schema = schemas[self.schema]
        if self.read == "enum":
            return list(schema["properties"][self.property]["enum"])
        if self.read == "properties":
            return list(schema["properties"])
        return [_receipt_operation(schemas, slot) for slot in schema["properties"].values()]

    def pointer(self) -> str:
        pointer = f"#/components/schemas/{self.schema}/properties"
        return f"{pointer}/{self.property}/enum" if self.read == "enum" else pointer


SETS = (
    GuiSet("STEP_KEYS", "StepKey", "ReeStepState", "enum", "key"),
    GuiSet("REVIEW_STEP_KEYS", "ReviewStepKey", "ReviewStepState", "enum", "step"),
    GuiSet("REE_RUN_OPERATIONS", "ReeRunOperation", "RunSummary", "enum", "operation"),
    GuiSet("REE_AUDIT_KEYS", "ReeAuditKey", "ReeAudit", "properties"),
    GuiSet("REE_RECEIPT_KEYS", "ReeReceiptKey", "ReeReceipts", "properties"),
    GuiSet("RECEIPT_OPERATIONS", "ReceiptOperation", "ReeReceipts", "receipt_operations"),
    GuiSet("SCRIPT_KINDS", "ScriptKind", "ScriptTarget", "enum", "kind"),
)


def _receipt_operation(schemas: dict[str, Any], slot: dict[str, Any]) -> str:
    refs = [option["$ref"] for option in slot.get("anyOf", []) if "$ref" in option]
    if "additionalProperties" in slot:
        refs.append(slot["additionalProperties"]["$ref"])
    (ref,) = refs
    operation: str = schemas[ref.rsplit("/", 1)[-1]]["properties"]["operation"]["const"]
    return operation


def _schemas() -> dict[str, Any]:
    schemas: dict[str, Any] = json.loads(OPENAPI.read_text(encoding="utf-8"))["components"]["schemas"]
    return schemas


def vocabulary_module() -> str:
    schemas = _schemas()
    lines = [
        "// Generated from contracts/openapi.json by `python -m scripts.contracts write gui-vocabulary`. Do not edit.",
        "",
    ]
    for gui_set in SETS:
        names = gui_set.names(schemas)
        lines += [
            f"/** {gui_set.pointer()} */",
            f"export const {gui_set.constant} = [",
            *(f'  "{name}",' for name in names),
            "] as const;",
            f"export type {gui_set.type_name} = (typeof {gui_set.constant})[number];",
            "",
        ]
    steps = SETS[0].names(schemas)
    lines += [
        "/** Each step key by its constant name. */",
        "export const STEP = {",
        *(f'  {name.upper()}: "{name}",' for name in steps),
        "} as const satisfies Record<string, StepKey>;",
        "",
    ]
    return "\n".join(lines)


def _wire_names() -> list[str]:
    schemas = _schemas()
    return sorted({name for gui_set in SETS for name in gui_set.names(schemas) if "_" in name})


def biome_config() -> str:
    """``gui/biome.json`` with its naming conventions letting a property be spelled as a wire name."""
    config = json.loads(BIOME.read_text(encoding="utf-8"))
    conventions = config["linter"]["rules"]["style"]["useNamingConvention"]["options"]["conventions"]
    names = "|".join(_wire_names())
    for convention in conventions:
        if "match" in convention:
            brand = "__brand|" if convention["match"].startswith("__brand|") else ""
            convention["match"] = f"{brand}{names}|(.+)"
    return json.dumps(config, indent=2) + "\n"
