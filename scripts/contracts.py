"""The repository's generated contracts: each file, the function that renders it, and what it binds.

A contract is correct when its file equals what its render function returns now, however the file was written:
by a recipe, by ``write``, or by hand. ``check`` holds every contract to that, and holds ``contracts/`` to holding
nothing but contracts and fixtures: the files written by hand, each under a ``fixtures/`` directory. It holds the
contracts to the specification's catalogue of operations too: each operation a contract names is catalogued, and
each catalogued one is run by the `ree` command spelled as its name in kebab case, and each one a route starts has a
route whose operationId is its name in camel case: a POST to the path ``route_path`` spells for it.

    python -m scripts.contracts write [NAME...]   # every contract, in the order below, or the named ones
    python -m scripts.contracts check             # exit 1 on a missing, stale or unaccounted file
    python -m scripts.contracts export            # the registry as JSON (repo2ree-contracts/1)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal

from scripts.config.export import rendered_contract as environment_contract

from repo2ree_api.export_openapi import openapi_document
from repo2ree_assurance_checker.codegen import render_schema
from repo2ree_assurance_checker.files import load_spec
from repo2ree_cli.export_schema import schema_document as cli_schema
from repo2ree_protocol.export_schema import schema_document as protocol_schema
from repo2ree_protocol.verbs import words_of
from repo2ree_ree.export_schema import schema_document as ree_schema
from repo2ree_ree.layout import layout_document

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = PurePosixPath("contracts")
FIXTURES = "fixtures"
FORMAT = "repo2ree-contracts/1"
OPENAPI = PurePosixPath("contracts/openapi.json")
CATALOGUE = PurePosixPath("assurance/spec/vocabulary/operation.toml")
OPENAPI_TYPESCRIPT = PurePosixPath("gui/node_modules/.bin/openapi-typescript")


class Name(StrEnum):
    REE_SCHEMA = "ree-schema"
    REE_LAYOUT = "ree-layout"
    PROTOCOL_SCHEMA = "protocol-schema"
    CLI_SCHEMA = "cli-schema"
    OPENAPI = "openapi"
    OPENAPI_TYPES = "openapi-types"
    BEHAVIOUR_SCHEMA = "behaviour-schema"
    ENVIRONMENT = "environment"


@dataclass(frozen=True)
class Contract:
    name: Name
    path: PurePosixPath
    summary: str
    between: str
    render: Callable[[], str]

    @property
    def rendered_by(self) -> str:
        return f"{self.render.__module__}.{self.render.__qualname__}"


def is_fixture(path: PurePosixPath) -> bool:
    return FIXTURES in path.parent.parts


def behaviour_schema() -> str:
    return render_schema(load_spec())


def openapi_types() -> str:
    """The GUI's TypeScript view of the committed OpenAPI contract: if that is stale, ``check`` fails on it first."""
    tool = ROOT / OPENAPI_TYPESCRIPT
    if not tool.is_file():
        raise RuntimeError(f"{OPENAPI_TYPESCRIPT} is missing: run `npm ci` in gui/")
    done = subprocess.run(
        [str(tool), str(ROOT / OPENAPI)], cwd=ROOT / "gui", capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise RuntimeError(f"openapi-typescript failed:\n{done.stderr}")
    return done.stdout


# The order `write` with no names follows: a contract rendered from another comes after it.
REGISTRY: tuple[Contract, ...] = (
    Contract(
        Name.REE_SCHEMA,
        PurePosixPath("contracts/ree/ree.schema.json"),
        "The REE document (`ree.json`): definition, receipts, seal.",
        "every reader and writer of an REE",
        ree_schema,
    ),
    Contract(
        Name.REE_LAYOUT,
        PurePosixPath("contracts/ree/layout.json"),
        "The REE's file tree: every path, and how a capture stores it.",
        "core and every reader of an REE's files",
        layout_document,
    ),
    Contract(
        Name.PROTOCOL_SCHEMA,
        PurePosixPath("contracts/protocol/protocol.schema.json"),
        "The commands and reads the workbench runs as `ree` argv, their results and outputs, and the workbench's "
        "WebSocket messages.",
        "the supervisor, the workbench and `ree`",
        protocol_schema,
    ),
    Contract(
        Name.CLI_SCHEMA,
        PurePosixPath("contracts/cli/cli.schema.json"),
        "Every `ree` command: its options, stdin, what it prints and its outputs; exit statuses and the steps.",
        "whoever runs `ree`, by hand or from a program, and `ree`",
        cli_schema,
    ),
    Contract(
        Name.OPENAPI,
        OPENAPI,
        "Every HTTP operation, its request and responses, and the operations that advance each step.",
        "the GUI and HTTP clients, and the API",
        openapi_document,
    ),
    Contract(
        Name.OPENAPI_TYPES,
        PurePosixPath("gui/src/shell/infra/api/generated/openapi.ts"),
        "The OpenAPI contract as the GUI's TypeScript types.",
        "the GUI and the API",
        openapi_types,
    ),
    Contract(
        Name.BEHAVIOUR_SCHEMA,
        PurePosixPath("contracts/behaviour/events.schema.json"),
        "The behaviour events each component journals, from the specification.",
        "the components and the assurance checker",
        behaviour_schema,
    ),
    Contract(
        Name.ENVIRONMENT,
        PurePosixPath("contracts/config/environment.json"),
        "The environment variables each process reads.",
        "a deployment and the processes it starts",
        environment_contract,
    ),
)

ProblemKind = Literal["missing", "stale", "unaccounted", "uncatalogued", "unrun", "unrouted", "misrouted"]


@dataclass(frozen=True)
class Problem:
    path: PurePosixPath
    kind: ProblemKind
    hint: str


def write(
    names: Sequence[Name] = (), *, registry: Sequence[Contract] = REGISTRY, root: Path = ROOT
) -> list[PurePosixPath]:
    """Write the named contracts, or all of them, in registry order; the paths whose content changed."""
    written: list[PurePosixPath] = []
    for contract in registry:
        if names and contract.name not in names:
            continue
        target = root / contract.path
        rendered = contract.render()
        if not target.is_file() or target.read_text(encoding="utf-8") != rendered:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            written.append(contract.path)
    return written


def check(*, registry: Sequence[Contract] = REGISTRY, root: Path = ROOT) -> list[Problem]:
    problems: list[Problem] = []
    for contract in registry:
        target = root / contract.path
        regenerate = f"python -m scripts.contracts write {contract.name}"
        if not target.is_file():
            problems.append(Problem(contract.path, "missing", regenerate))
        elif target.read_text(encoding="utf-8") != contract.render():
            problems.append(Problem(contract.path, "stale", regenerate))
    registered = {contract.path for contract in registry}
    problems.extend(
        Problem(
            path,
            "unaccounted",
            f"register it in scripts/contracts.py, move it under a {FIXTURES}/ directory, or delete it",
        )
        for path in _files(root, CONTRACTS)
        if path not in registered and not is_fixture(path)
    )
    if not problems:
        problems.extend(operation_problems(registry=registry, root=root))
    return problems


def operation_problems(*, registry: Sequence[Contract] = REGISTRY, root: Path = ROOT) -> list[Problem]:
    """Each operation a contract names that the catalogue lacks, and each catalogued one its `ree` words don't run."""
    documents = {
        contract.name: (contract.path, json.loads((root / contract.path).read_text(encoding="utf-8")))
        for contract in registry
        if contract.path.suffix == ".json"
    }
    if Name.BEHAVIOUR_SCHEMA not in documents:
        return []
    _, behaviour = documents[Name.BEHAVIOUR_SCHEMA]
    catalogue = {name for table in behaviour["x-operations"].values() for name in table}
    problems = [
        Problem(path, "uncatalogued", f"{name} is not in {CATALOGUE}: catalogue it or use a catalogued name")
        for name_, (path, document) in documents.items()
        if name_ is not Name.BEHAVIOUR_SCHEMA
        for name in sorted(_operations_named(document) - catalogue)
    ]
    if Name.CLI_SCHEMA in documents:
        cli_path, cli = documents[Name.CLI_SCHEMA]
        run = {
            operation
            for command in cli["commands"]
            for operation in command["operations"]
            if tuple(command["words"]) == words_of(operation)
        }
        problems.extend(
            Problem(cli_path, "unrun", f"{name}: no `ree {' '.join(words_of(name))}` runs it")
            for name in sorted(catalogue - run)
        )
    if Name.OPENAPI in documents:
        openapi_path, openapi = documents[Name.OPENAPI]
        routes = [
            (path, method, route) for path, methods in openapi["paths"].items() for method, route in methods.items()
        ]
        declared = {operation for _, _, route in routes for operation in route.get("x-operations", [])}
        named = {
            operation: (path, method)
            for path, method, route in routes
            for operation in route.get("x-operations", [])
            if route["operationId"] == camel_case(operation)
        }
        problems.extend(
            Problem(openapi_path, "unrouted", f"{name}: no route {camel_case(name)} declares it")
            for name in sorted(declared - set(named))
        )
        problems.extend(
            Problem(openapi_path, "misrouted", f"{name}: {method.upper()} {path}, not POST {route_path(name, path)}")
            for name, (path, method) in sorted(named.items())
            if (path, method) != (route_path(name, path), "post")
        )
    return problems


def route_path(operation: str, path: str) -> str:
    """The path of the route named after ``operation``: its words under the REE, a review's under its review.

    ``review_run_experiment`` is ``/api/v1/rees/{ree_id}/reviews/{review_id}/run-experiment``; the parameters
    ``path`` names after those words, such as an experiment's name, follow them.
    """
    *review, words = words_of(operation)
    base = "/api/v1/rees/{ree_id}"
    if review:
        base += "/reviews" if operation == "review_acquire_source" else "/reviews/{review_id}"
    prefix = f"{base}/{words}"
    rest = path.removeprefix(prefix) if path.startswith(prefix) else ""
    parameters = [part for part in rest.split("/") if part]
    if all(part.startswith("{") and part.endswith("}") for part in parameters):
        return prefix + rest
    return prefix


def camel_case(operation: str) -> str:
    first, *rest = operation.split("_")
    return first + "".join(word.capitalize() for word in rest)


def _operations_named(document: object) -> set[str]:
    """The operation names in a JSON document: an ``operation`` property's values, an ``operations`` list's items."""
    named: set[str] = set()
    if isinstance(document, dict):
        properties = document.get("properties")
        operation = properties.get("operation") if isinstance(properties, dict) else None
        if isinstance(operation, dict) and isinstance(operation.get("const"), str):
            named.add(operation["const"])
        if isinstance(operation, dict) and isinstance(operation.get("enum"), list):
            named.update(item for item in operation["enum"] if isinstance(item, str))
        for key, value in document.items():
            if key in ("operations", "x-operations") and isinstance(value, list):
                named.update(item for item in value if isinstance(item, str))
            else:
                named |= _operations_named(value)
    elif isinstance(document, list):
        for item in document:
            named |= _operations_named(item)
    return named


def fixtures(root: Path = ROOT) -> list[PurePosixPath]:
    return [path for path in _files(root, CONTRACTS) if is_fixture(path)]


def export(*, registry: Sequence[Contract] = REGISTRY, root: Path = ROOT) -> str:
    document = {
        "format": FORMAT,
        "contracts": [
            {
                "name": contract.name.value,
                "path": str(contract.path),
                "summary": contract.summary,
                "between": contract.between,
                "rendered_by": contract.rendered_by,
                "write": f"python -m scripts.contracts write {contract.name}",
            }
            for contract in registry
        ],
        "fixtures": [str(path) for path in fixtures(root)],
    }
    return json.dumps(document, indent=2) + "\n"


def _files(root: Path, directory: PurePosixPath) -> list[PurePosixPath]:
    """The files under ``directory`` that a commit would hold: tracked or unignored, and present."""
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", str(directory)],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted({PurePosixPath(path) for path in listed.split("\0") if path and (root / path).is_file()})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.contracts", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    writing = commands.add_parser("write", help="write every contract, or the named ones")
    writing.add_argument("names", nargs="*", type=Name, choices=list(Name), metavar="NAME")
    commands.add_parser("check", help="exit 1 on a missing, stale or unaccounted file")
    commands.add_parser("export", help="print the registry as JSON")
    args = parser.parse_args(argv)
    if args.command == "write":
        for path in write(args.names):
            sys.stdout.write(f"wrote {path}\n")
        return 0
    if args.command == "export":
        sys.stdout.write(export())
        return 0
    problems = check()
    for problem in problems:
        sys.stderr.write(f"{problem.kind:12} {problem.path}: {problem.hint}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
