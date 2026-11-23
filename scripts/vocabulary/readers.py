from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Any, Literal

from scripts.vocabulary.discover import ROOT, contract_sets
from scripts.vocabulary.model import CONTRACTS, Context, Contract, Located, Reader

REVIEW = "review"


def words(operation: str) -> tuple[str, ...]:
    if operation.startswith(f"{REVIEW}_"):
        return (REVIEW, operation.removeprefix(f"{REVIEW}_").replace("_", "-"))
    return (operation.replace("_", "-"),)


def camel(operation: str) -> str:
    first, *rest = operation.split("_")
    return first + "".join(word.capitalize() for word in rest)


def route_path(operation: str) -> str:
    *review, last = words(operation)
    base = "/api/v1/rees/{ree_id}"
    if review:
        base += "/reviews" if operation == f"{REVIEW}_acquire_source" else "/reviews/{review_id}"
    return f"{base}/{last}"


def _parameters_only(rest: str) -> bool:
    return all(part.startswith("{") and part.endswith("}") for part in rest.split("/") if part)


@dataclass(frozen=True)
class CatalogueTable(Reader):
    table: Literal["operations", "review_operations"]

    def describe(self) -> str:
        return f"the catalogue's {self.table} (assurance/spec/vocabulary/operation.toml)"

    def read(self, context: Context) -> tuple[Located, ...]:
        return (Located(f"spec:{self.table}", frozenset(getattr(context.spec(), self.table))),)


@dataclass(frozen=True)
class SpecReceipts(Reader):
    def describe(self) -> str:
        return "the Ree aggregate's receipts (assurance/spec/aggregates/ree.toml)"

    def read(self, context: Context) -> tuple[Located, ...]:
        receipts = context.spec().aggregates["Ree"].receipts
        return (Located("spec:aggregates.Ree.receipts", frozenset(receipts)),)


@dataclass(frozen=True)
class SpecUnsettledStates(Reader):
    entity: str

    def describe(self) -> str:
        return f"the states {self.entity} passes before it settles (assurance/spec/vocabulary)"

    def read(self, context: Context) -> tuple[Located, ...]:
        entity = context.spec().entities[self.entity]
        unsettled = frozenset(entity.states) - frozenset(entity.terminal)
        return (Located(f"spec:entities.{self.entity}.states", unsettled),)


@dataclass(frozen=True)
class SpecFieldGroups(Reader):
    def describe(self) -> str:
        return "the groups the Ree aggregate's fields are drawn in (assurance/spec/aggregates/ree.toml)"

    def read(self, context: Context) -> tuple[Located, ...]:
        fields = context.spec().aggregates["Ree"].fields.values()
        return (Located("spec:aggregates.Ree.fields.*.group", frozenset(field.group for field in fields)),)


@dataclass(frozen=True)
class ContractSet(Reader):
    patterns: tuple[str, ...]

    def describe(self) -> str:
        return ", ".join(self.patterns)

    def claims(self) -> tuple[str, ...]:
        return self.patterns

    def read(self, context: Context) -> tuple[Located, ...]:
        found = [
            located
            for contract in CONTRACTS
            for located in contract_sets(contract, context.contract(contract))
            if any(fnmatch.fnmatchcase(located.where, pattern) for pattern in self.patterns)
        ]
        return tuple(found)


def _commands(context: Context) -> list[dict[str, Any]]:
    return list(context.contract("cli")["commands"])


@dataclass(frozen=True)
class CommandsRunByName(Reader):
    def describe(self) -> str:
        return "operations a `ree` command spelled as their name runs (contracts/cli/cli.schema.json)"

    def read(self, context: Context) -> tuple[Located, ...]:
        names = {
            operation
            for command in _commands(context)
            for operation in command["operations"]
            if tuple(command["words"]) == words(operation)
        }
        return (Located("cli:/commands", frozenset(names)),)


def _routes(context: Context) -> list[tuple[str, str, dict[str, Any]]]:
    paths: dict[str, dict[str, dict[str, Any]]] = context.contract("openapi")["paths"]
    return [(path, method, route) for path, methods in paths.items() for method, route in methods.items()]


Http = Literal["declared", "named", "posted"]


@dataclass(frozen=True)
class RoutedOperations(Reader):
    which: Http

    def describe(self) -> str:
        return {
            "declared": "operations a route declares in x-operations",
            "named": "operations a route that declares them is named after (operationId in camel case)",
            "posted": "operations whose named route is a POST to their words under the REE or its review",
        }[self.which] + " (contracts/openapi.json)"

    def read(self, context: Context) -> tuple[Located, ...]:
        names: set[str] = set()
        for path, method, route in _routes(context):
            for operation in route.get("x-operations", []):
                if self.which == "declared":
                    names.add(operation)
                elif route["operationId"] == camel(operation):
                    prefix = route_path(operation)
                    posted = path.startswith(prefix) and _parameters_only(path.removeprefix(prefix))
                    if self.which == "named" or (posted and method == "post"):
                        names.add(operation)
        return (Located(f"openapi:/paths ({self.which})", frozenset(names)),)


def _operations_named(document: object) -> set[str]:
    named: set[str] = set()
    if isinstance(document, dict):
        properties = document.get("properties")
        operation = properties.get("operation") if isinstance(properties, dict) else None
        if isinstance(operation, dict) and isinstance(operation.get("const"), str):
            named.add(operation["const"])
        for key, value in document.items():
            if key in ("operations", "x-operations") and isinstance(value, list):
                named.update(item for item in value if isinstance(item, str))
            else:
                named |= _operations_named(value)
    elif isinstance(document, list):
        for item in document:
            named |= _operations_named(item)
    return named


@dataclass(frozen=True)
class OperationsNamed(Reader):
    contract: Contract | None = None

    def describe(self) -> str:
        named = f"{self.contract} names" if self.contract else "a contract names"
        return f"every operation {named}: an operation const, an operations or x-operations list"

    def read(self, context: Context) -> tuple[Located, ...]:
        contracts = [self.contract] if self.contract else [name for name in CONTRACTS if name != "behaviour"]
        names: set[str] = set()
        for contract in contracts:
            names |= _operations_named(context.contract(contract))
        where = f"{self.contract}:operation names" if self.contract else "contracts:operation names"
        return (Located(where, frozenset(names)),)


@dataclass(frozen=True)
class SourceSet(Reader):
    site: str

    def describe(self) -> str:
        return self.site

    def claims(self) -> tuple[str, ...]:
        return (self.site,)

    def read(self, context: Context) -> tuple[Located, ...]:
        found = context.sources().get(self.site)
        return (found,) if found else ()


@dataclass(frozen=True)
class SourceSites(Reader):
    pattern: str
    combine: Literal["copies", "union"]

    def describe(self) -> str:
        return self.pattern if self.combine == "copies" else f"every set at {self.pattern}, together"

    def claims(self) -> tuple[str, ...]:
        return (self.pattern,)

    def read(self, context: Context) -> tuple[Located, ...]:
        found = [at for site, at in context.sources().items() if fnmatch.fnmatchcase(site, self.pattern)]
        if self.combine == "copies" or not found:
            return tuple(found)
        return (Located(self.pattern, frozenset().union(*(at.names for at in found))),)


GUI_VOCABULARY = "gui/src/core/generated/vocabulary.ts"


@dataclass(frozen=True)
class GuiVocabularySet(Reader):
    constant: str

    def describe(self) -> str:
        return f"{GUI_VOCABULARY}::{self.constant}"

    def read(self, context: Context) -> tuple[Located, ...]:
        source = (ROOT / GUI_VOCABULARY).read_text(encoding="utf-8")
        found = re.search(rf"export const {self.constant} = \[(.*?)\] as const;", source, re.DOTALL)
        if not found:
            return ()
        return (Located(self.describe(), frozenset(re.findall(r'"([a-z_]+)"', found.group(1)))),)
