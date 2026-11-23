from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner
from jsonschema import Draft202012Validator

from repo2ree_cli.cli import cli
from repo2ree_cli.export_schema import schema_document

DOCUMENT: dict[str, Any] = json.loads(schema_document())
runner = CliRunner()


def command(*words: str) -> dict[str, Any]:
    return next(entry for entry in DOCUMENT["commands"] if entry["words"] == list(words))


def validator(entry: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator({"$defs": DOCUMENT["$defs"], **entry})


def test_the_contract_is_valid_and_ree_schema_prints_it() -> None:
    Draft202012Validator.check_schema(DOCUMENT)
    result = runner.invoke(cli, ["schema"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == DOCUMENT


def test_a_command_that_runs_names_its_operations_and_a_read_none() -> None:
    assert command("seal-ree")["operations"] == ["seal_ree"]
    assert command("suggest-scripts")["operations"] == ["suggest_scripts", "write_script"]
    assert command("review", "all")["operations"][0] == "review_acquire_source"
    assert command("status")["operations"] == []
    assert [step["commands"] for step in DOCUMENT["steps"] if step["key"] == "seal_ree"] == [["seal-ree"]]


def test_what_ree_prints_conforms_to_the_contract(tmp_path: Path) -> None:
    root = tmp_path / "ree"
    initialized = runner.invoke(cli, ["-C", str(root), "--json", "initialize-ree", "--name", "demo"])
    status = runner.invoke(cli, ["-C", str(root), "--json", "status"])
    refused = runner.invoke(cli, ["-C", str(root), "--json", "evaluate-reproducibility"])

    for result, words in ((initialized, ("initialize-ree",)), (status, ("status",))):
        printed = json.loads(result.stdout)
        validator(DOCUMENT["result"]).validate(printed)
        validator(command(*words)["outputs"]).validate(printed["outputs"])
    validator(DOCUMENT["result"]).validate(json.loads(refused.stdout))
