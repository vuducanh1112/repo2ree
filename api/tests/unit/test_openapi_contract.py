"""The generated OpenAPI document is the automation-client contract."""

from __future__ import annotations

import json
from typing import Any

from repo2ree_api.export_openapi import CONTRACT_PATH, openapi_document
from repo2ree_api.main import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(schema: dict[str, Any]):
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def test_generated_document_matches_committed_contract() -> None:
    """The committed api/openapi.json is the frozen contract; the app is one
    implementation of it. On intentional API changes regenerate with
    `just api-openapi` so the contract change is a reviewable diff."""
    committed = CONTRACT_PATH.read_text()

    # Compare parsed documents first for a readable pytest diff, then the exact
    # serialization so formatting drift can't creep into the committed file.
    assert json.loads(committed) == app.openapi(), "regenerate with `just api-openapi`"
    assert committed == openapi_document(), "regenerate with `just api-openapi`"


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

    assert set(create_schema["properties"]) == {"name", "workbench_image", "agent_id"}

    acquire_operation = schema["paths"]["/api/v1/rees/{ree_id}/source:acquire"]["post"]
    acquire_ref = acquire_operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    acquire_schema = schema["components"]["schemas"][acquire_ref.rsplit("/", 1)[-1]]

    assert {"origin_url", "source_type", "revision"} <= set(acquire_schema["properties"])
