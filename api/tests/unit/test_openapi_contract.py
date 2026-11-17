"""The generated OpenAPI document is the automation-client contract."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from repo2ree_api.authoring.catalog import STEP_ACTIONS_EXTENSION
from repo2ree_api.main import app
from repo2ree_core.domain.ree.steps import REE_STEPS

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(schema: dict[str, Any]):
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def test_the_contract_is_written_from_the_code_alone(tmp_path: Path) -> None:
    """Importing the app reads no runtime data and starts nothing: run records it cannot read do not stop the
    contract being written, and no thread is started."""
    runs = tmp_path / "runs"
    (runs / "old-run").mkdir(parents=True)
    (runs / "old-run" / "state.json").write_text('{"operation": "no-longer-an-operation"}')
    script = (
        "import threading\n"
        "from repo2ree_api.export_openapi import openapi_document\n"
        "openapi_document()\n"
        "print(sorted(t.name for t in threading.enumerate()))\n"
    )
    environment = {**os.environ, "RUN_REGISTRY_DIR": str(runs), "CONTROL_STATE_DIR": str(tmp_path / "control")}
    done = subprocess.run(
        [sys.executable, "-c", script], env=environment, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "['MainThread']"


def test_public_operations_have_stable_unique_ids_and_tags() -> None:
    schema = app.openapi()
    operations = list(_operations(schema))
    operation_ids = [operation["operationId"] for _, _, operation in operations]

    assert len(operation_ids) == len(set(operation_ids))
    assert all("_api_v1_" not in operation_id for operation_id in operation_ids)
    assert all(operation.get("tags") for _, _, operation in operations)


def test_json_success_responses_have_non_empty_schemas() -> None:
    schema = app.openapi()
    empty: list[tuple[str, str, str]] = []

    for path, method, operation in _operations(schema):
        for status_code, response in operation.get("responses", {}).items():
            if not status_code.startswith("2"):
                continue
            json_content = response.get("content", {}).get("application/json")
            if json_content is not None and not json_content.get("schema"):
                empty.append((path, method, status_code))

    assert empty == []


def test_declared_validation_errors_use_the_error_envelope() -> None:
    schema = app.openapi()
    for _, _, operation in _operations(schema):
        validation_response = operation.get("responses", {}).get("422")
        if validation_response is None:
            continue
        response_schema = validation_response["content"]["application/json"]["schema"]
        assert response_schema == {"$ref": "#/components/schemas/ErrorEnvelope"}


def test_creation_and_source_acquisition_are_separate_contracts() -> None:
    schema = app.openapi()
    create_operation = schema["paths"]["/api/v1/rees"]["post"]
    create_ref = create_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    create_schema = schema["components"]["schemas"][create_ref.rsplit("/", 1)[-1]]

    # Creation names a place (a store), and nothing else: no image, package, command or resource
    # request may enter here. What the REE's scripts need is its check, written afterwards.
    assert set(create_schema["properties"]) == {"name", "store_id"}

    acquire_operation = schema["paths"]["/api/v1/rees/{ree_id}/source:acquire"]["post"]
    acquire_ref = acquire_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    acquire_schema = schema["components"]["schemas"][acquire_ref.rsplit("/", 1)[-1]]

    assert {"origin_url", "source_type", "revision"} <= set(acquire_schema["properties"])


def test_the_contract_says_which_operations_advance_each_authoring_step() -> None:
    schema = app.openapi()
    operation_ids = {operation["operationId"] for _path, _method, operation in _operations(schema)}
    step_actions = schema["paths"]["/api/v1/rees/{ree_id}/ree-steps"]["get"][STEP_ACTIONS_EXTENSION]

    assert list(step_actions) == [step.key for step in REE_STEPS]
    assert all(actions for actions in step_actions.values())
    assert {action for actions in step_actions.values() for action in actions} <= operation_ids
