from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath

import pytest
from scripts.contracts import FORMAT, REGISTRY, Contract, Name, check, export, fixtures, is_fixture, write

SCHEMA = PurePosixPath("contracts/a/schema.json")
TYPES = PurePosixPath("gui/types.ts")
SEALED = PurePosixPath("contracts/a/fixtures/sealed")


def contract(name: Name, path: PurePosixPath, text: str) -> Contract:
    return Contract(name, path, "summary", "between", lambda: text)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def put(root: Path, path: PurePosixPath, text: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text, encoding="utf-8")


def test_write_writes_what_differs_and_only_the_named(root: Path) -> None:
    registry = (contract(Name.CLI_SCHEMA, SCHEMA, "{}\n"), contract(Name.OPENAPI_TYPES, TYPES, "types\n"))

    assert write((Name.CLI_SCHEMA,), registry=registry, root=root) == [SCHEMA]
    assert not (root / TYPES).exists()
    assert write(registry=registry, root=root) == [TYPES]
    assert write(registry=registry, root=root) == []
    assert (root / SCHEMA).read_text(encoding="utf-8") == "{}\n"


def test_check_finds_missing_stale_and_unaccounted_files(root: Path) -> None:
    registry = (contract(Name.CLI_SCHEMA, SCHEMA, "{}\n"), contract(Name.OPENAPI_TYPES, TYPES, "types\n"))
    put(root, TYPES, "old types\n")
    put(root, SEALED / "one.json", "{}")
    put(root, PurePosixPath("contracts/stray.json"), "{}")
    put(root, PurePosixPath("contracts/fixtures.json"), "{}")

    found = {(problem.path, problem.kind) for problem in check(registry=registry, root=root)}

    assert found == {
        (SCHEMA, "missing"),
        (TYPES, "stale"),
        (PurePosixPath("contracts/stray.json"), "unaccounted"),
        (PurePosixPath("contracts/fixtures.json"), "unaccounted"),
    }
    assert fixtures(root) == [SEALED / "one.json"]


def test_a_contract_is_correct_however_it_was_written(root: Path) -> None:
    registry = (contract(Name.CLI_SCHEMA, SCHEMA, "{}\n"),)
    put(root, SCHEMA, "{}\n")

    assert check(registry=registry, root=root) == []


def operation_contracts(root: Path, *, cli_runs: list[str], protocol_names: str) -> tuple[Contract, ...]:
    behaviour = {"x-operations": {"operations": {"build": "", "run": ""}, "review_operations": {"review_run": ""}}}
    cli = {"commands": [{"operations": cli_runs}]}
    protocol = {"$defs": {"Command": {"properties": {"operation": {"const": protocol_names}}}}}
    documents = {
        Name.BEHAVIOUR_SCHEMA: (PurePosixPath("contracts/behaviour.json"), behaviour),
        Name.CLI_SCHEMA: (PurePosixPath("contracts/cli.json"), cli),
        Name.PROTOCOL_SCHEMA: (PurePosixPath("contracts/protocol.json"), protocol),
    }
    registry = []
    for name, (path, document) in documents.items():
        text = json.dumps(document) + "\n"
        put(root, path, text)
        registry.append(contract(name, path, text))
    return tuple(registry)


def test_check_holds_the_contracts_to_the_catalogue_of_operations(root: Path) -> None:
    kept = operation_contracts(root, cli_runs=["build", "run", "review_run"], protocol_names="build")
    assert check(registry=kept, root=root) == []

    broken = operation_contracts(root, cli_runs=["build", "review_run", "bulid"], protocol_names="remove")
    problems = check(registry=broken, root=root)
    found = {(problem.path.name, problem.kind, problem.hint.split()[0]) for problem in problems}

    assert found == {
        ("cli.json", "uncatalogued", "bulid"),
        ("protocol.json", "uncatalogued", "remove"),
        ("cli.json", "unrun", "no"),
    }


def test_ignored_files_under_contracts_are_not_the_registrys_business(root: Path) -> None:
    put(root, PurePosixPath(".gitignore"), "*.tmp\n")
    put(root, PurePosixPath("contracts/scratch.tmp"), "")

    assert check(registry=(), root=root) == []


def test_the_registry_names_each_contract_once_and_claims_each_path_once() -> None:
    assert [item.name for item in REGISTRY] == list(dict.fromkeys(item.name for item in REGISTRY))
    assert {item.name for item in REGISTRY} == set(Name)
    assert len({item.path for item in REGISTRY}) == len(REGISTRY)
    assert not any(is_fixture(item.path) for item in REGISTRY)


def test_every_fixture_lives_under_contracts() -> None:
    assert fixtures()
    assert all(PurePosixPath("contracts") in path.parents for path in fixtures())


def test_the_export_lists_every_contract_with_what_renders_it() -> None:
    document = json.loads(export())

    assert document["format"] == FORMAT
    assert [entry["name"] for entry in document["contracts"]] == [item.name.value for item in REGISTRY]
    openapi = next(entry for entry in document["contracts"] if entry["name"] == "openapi")
    assert openapi["rendered_by"] == "repo2ree_api.export_openapi.openapi_document"
    assert openapi["write"] == "python -m scripts.contracts write openapi"
