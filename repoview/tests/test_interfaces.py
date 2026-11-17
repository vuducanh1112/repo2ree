"""The interfaces and contracts pages say what the committed contracts say: every command, every operation, the
steps both advance, and a graph for each entry point a contract names."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

from repo2ree_repoview.diagrams.contracts import contracts, drawing_path, render_dot
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.contracts import CliSchema, Environment, OpenApi
from repo2ree_repoview.overview.exports import CONTRACTS_EXPORT, Contracts, exported
from repo2ree_repoview.overview.pages.contracts import page_contracts
from repo2ree_repoview.overview.pages.environment import page_environment
from repo2ree_repoview.overview.pages.interfaces import page_api, page_cli, page_interfaces

REGISTRY = Contracts.model_validate_json(exported(CONTRACTS_EXPORT))
CLI = CliSchema.read(REGISTRY)
API = OpenApi.read(REGISTRY)
HUB = html.unescape(page_interfaces(CLI, API).body)
COMMANDS = html.unescape(page_cli(CLI).body)
OPERATIONS = html.unescape(page_api(API).body)


@pytest.fixture(scope="module")
def contracts_page(tmp_path_factory: pytest.TempPathFactory) -> str:
    bundle = Bundle(tmp_path_factory.mktemp("overview") / "bundle", "r" * 40)
    return html.unescape(page_contracts(bundle, REGISTRY, Environment.read(REGISTRY)).body)


def test_the_hub_leads_to_both_surfaces() -> None:
    assert all(f'href="{page}.html"' in HUB for page in ("interfaces-cli", "interfaces-api"))


def test_every_step_is_advanced_on_both_surfaces() -> None:
    assert [step.key for step in CLI.steps] == list(API.step_actions)
    assert all(step.commands for step in CLI.steps)
    assert "none in the contract" not in HUB


def test_the_command_line_page_lists_every_command() -> None:
    assert all(f"ree {' '.join(command.words)}<" in COMMANDS for command in CLI.commands)


def test_the_api_page_lists_every_operation() -> None:
    assert all(f">{operation.operation_id}<" in OPERATIONS for _path, _method, operation in API.each())


def test_every_contract_it_lists_is_committed(contracts_page: str) -> None:
    assert all(contract.file.is_file() for contract in REGISTRY.contracts)
    assert all(contract.path in contracts_page for contract in REGISTRY.contracts)
    assert all(path in contracts_page for path in REGISTRY.fixtures)


def test_every_link_to_a_graph_lands_on_one(contracts_page: str) -> None:
    anchors = set(re.findall(r'<details id="([^"]+)"', contracts_page))
    linked = set(re.findall(r'href="contracts\.html#([^"]+)"', COMMANDS + OPERATIONS))

    assert linked
    assert linked <= anchors
    assert sum(len(contract.entries) for contract in contracts(REGISTRY)) == len(anchors)


def test_a_graph_holds_every_model_its_entry_reaches_and_an_edge_to_each() -> None:
    cli = next(contract for contract in contracts(REGISTRY) if contract.key == "cli-schema")
    status = next(entry for entry in cli.entries if entry.slug == "status")

    reached = cli.reached(status)
    dot = render_dot(cli, status)

    assert reached[0] == "ReeStatusReport"
    assert {"ReeSteps", "ReeAudit", "StepAudit", "ScriptState"} <= set(reached)
    assert all(f'"{name}" [label=' in dot for name in reached)
    assert '"ReeAudit":"experiments":e -> "ExperimentAudit":"_":w [label="[*]"]' in dot


def test_every_model_a_contract_refers_to_is_defined() -> None:
    for contract in contracts(REGISTRY):
        for entry in contract.entries:
            for name in contract.reached(entry):
                assert name in contract.defs, f"{contract.key}: {entry.slug} reaches {name}, which it defines nowhere"


def test_the_drawings_go_one_folder_a_contract(tmp_path: Path) -> None:
    cli = next(contract for contract in contracts(REGISTRY) if contract.key == "cli-schema")
    assert drawing_path(tmp_path, cli, cli.entries[0]) == tmp_path / "cli-schema" / "result.svg"


def test_the_contracts_page_leads_to_the_environment_variables(contracts_page: str) -> None:
    environment = Environment.read(REGISTRY)
    assert 'href="contracts-environment.html"' in contracts_page
    assert f"{len(environment.variables)} variables" in contracts_page


def test_the_environment_page_says_what_renders_its_contract() -> None:
    page = html.unescape(page_environment(Environment.read(REGISTRY)).body)
    assert next(entry for entry in REGISTRY.contracts if entry.name == "environment").rendered_by in page
