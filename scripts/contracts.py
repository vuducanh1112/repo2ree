"""The repository's generated contracts: each file, the function that renders it, and what it binds.

A contract is correct when its file equals what its render function returns now, however the file was written:
by a recipe, by ``write``, or by hand. ``check`` holds every contract to that, and holds ``contracts/`` to holding
nothing but contracts and fixtures: the files written by hand, each under a ``fixtures/`` directory. The names the
contracts spell are held to the catalogue of operations by the vocabulary graph (``python -m scripts.vocabulary``).

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
from scripts.gui_vocabulary import biome_config, vocabulary_module

from repo2ree_api.export_openapi import openapi_document
from repo2ree_assurance_checker.codegen import render_schema
from repo2ree_assurance_checker.files import load_spec
from repo2ree_cli.export_schema import schema_document as cli_schema
from repo2ree_protocol.export_schema import schema_document as protocol_schema
from repo2ree_ree.export_schema import schema_document as ree_schema
from repo2ree_ree.layout import layout_document
from repo2ree_testbed.exercise import schema_document as exercise_schema

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = PurePosixPath("contracts")
FIXTURES = "fixtures"
FORMAT = "repo2ree-contracts/1"
OPENAPI = PurePosixPath("contracts/openapi.json")
OPENAPI_TYPESCRIPT = PurePosixPath("gui/node_modules/.bin/openapi-typescript")


class Name(StrEnum):
    REE_SCHEMA = "ree-schema"
    REE_LAYOUT = "ree-layout"
    PROTOCOL_SCHEMA = "protocol-schema"
    CLI_SCHEMA = "cli-schema"
    OPENAPI = "openapi"
    OPENAPI_TYPES = "openapi-types"
    GUI_VOCABULARY = "gui-vocabulary"
    BIOME_NAMING = "biome-naming"
    BEHAVIOUR_SCHEMA = "behaviour-schema"
    ENVIRONMENT = "environment"
    EXERCISE_SCHEMA = "exercise-schema"


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
        Name.GUI_VOCABULARY,
        PurePosixPath("gui/src/core/generated/vocabulary.ts"),
        "The sets of names the GUI reads off the wire, from the OpenAPI contract.",
        "the GUI and the API",
        vocabulary_module,
    ),
    Contract(
        Name.BIOME_NAMING,
        PurePosixPath("gui/biome.json"),
        "The GUI's lint configuration, whose naming conventions let a property be spelled as a wire name.",
        "the GUI's sources",
        biome_config,
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
    Contract(
        Name.EXERCISE_SCHEMA,
        PurePosixPath("contracts/exercise/exercise.schema.json"),
        "One replayable input to the domain: the REEs it works in, the operations it runs in each, and its faults.",
        "whatever generates, stores or replays exercises",
        exercise_schema,
    ),
)

ProblemKind = Literal["missing", "stale", "unaccounted"]


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
    return problems


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
