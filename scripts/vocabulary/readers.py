"""Where each vocabulary is read from. A reader reads what is written, never what a renderer would write."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any, Literal

from scripts.vocabulary.discover import contract_sets
from scripts.vocabulary.model import CONTRACTS, Context, Located, Reader

# ================================================
# Spelling: how an operation's name is written where it is not written as itself
# ================================================

REVIEW = "review"


def words(operation: str) -> tuple[str, ...]:
    """The `ree` words that run an operation: ``review_run_experiment`` is ``review run-experiment``."""
    if operation.startswith(f"{REVIEW}_"):
        return (REVIEW, operation.removeprefix(f"{REVIEW}_").replace("_", "-"))
    return (operation.replace("_", "-"),)


def camel(operation: str) -> str:
    first, *rest = operation.split("_")
    return first + "".join(word.capitalize() for word in rest)


def route_path(operation: str) -> str:
    """The path of the route named after an operation, before the parameters that follow it."""
    *review, last = words(operation)
    base = "/api/v1/rees/{ree_id}"
    if review:
        base += "/reviews" if operation == f"{REVIEW}_acquire_source" else "/reviews/{review_id}"
    return f"{base}/{last}"


def _parameters_only(rest: str) -> bool:
    return all(part.startswith("{") and part.endswith("}") for part in rest.split("/") if part)


# ================================================
# The specification
# ================================================


@dataclass(frozen=True)
class CatalogueTable(Reader):
    table: Literal["operations", "review_operations"]

    def describe(self) -> str:
        return f"the catalogue's {self.table} (assurance/spec/vocabulary/operation.toml)"

    def read(self, context: Context) -> tuple[Located, ...]:
        return (Located(f"spec:{self.table}", frozenset(getattr(context.spec(), self.table))),)


@dataclass(frozen=True)
class SpecReceipts(Reader):
    """The Ree aggregate's receipts; with ``named_by_producer``, those named after the operation producing them."""

    named_by_producer: bool = False

    def describe(self) -> str:
        what = "receipts named after their producing operation" if self.named_by_producer else "receipts"
        return f"the Ree aggregate's {what} (assurance/spec/aggregates/ree.toml)"

    def read(self, context: Context) -> tuple[Located, ...]:
        receipts = context.spec().aggregates["Ree"].receipts
        names = [
            name for name, receipt in receipts.items() if not self.named_by_producer or receipt.produced_by == name
        ]
        return (Located("spec:aggregates.Ree.receipts", frozenset(names)),)


@dataclass(frozen=True)
class SpecFieldGroups(Reader):
    def describe(self) -> str:
        return "the groups the Ree aggregate's fields are drawn in (assurance/spec/aggregates/ree.toml)"

    def read(self, context: Context) -> tuple[Located, ...]:
        fields = context.spec().aggregates["Ree"].fields.values()
        return (Located("spec:aggregates.Ree.fields.*.group", frozenset(field.group for field in fields)),)


# ================================================
# The contracts
# ================================================


@dataclass(frozen=True)
class ContractSet(Reader):
    """A schema's enum or properties, at every pointer one of ``patterns`` matches; the copies must agree."""

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
    """``declared``: operations a route starts. ``named``: those a route is named after, its operationId the
    name in camel case. ``posted``: those whose named route is a POST to ``route_path``, parameters after it."""

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
    """An ``operation`` property's const values, and the items of ``operations`` and ``x-operations`` lists."""
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
    def describe(self) -> str:
        return "every operation a contract names: an operation const, an operations or x-operations list"

    def read(self, context: Context) -> tuple[Located, ...]:
        names: set[str] = set()
        for contract in CONTRACTS:
            if contract != "behaviour":
                names |= _operations_named(context.contract(contract))
        return (Located("contracts:operation names", frozenset(names)),)


# ================================================
# Source
# ================================================


@dataclass(frozen=True)
class SourceSet(Reader):
    """A literal set of names in source, at the site discovery names it by."""

    site: str

    def describe(self) -> str:
        return self.site

    def claims(self) -> tuple[str, ...]:
        return (self.site,)

    def read(self, context: Context) -> tuple[Located, ...]:
        found = context.sources().get(self.site)
        return (found,) if found else ()
