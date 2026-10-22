"""Every operation of the API contract, fuzzed against a running stack.

Generated requests go to one real REE wherever an operation takes an REE, so they
reach past the lookup into the code behind it. The API must never answer with a
server error, and every answer must be one the contract declares.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.checks import not_a_server_error
from schemathesis.generation.case import Case
from schemathesis.specs.openapi.checks import response_schema_conformance, status_code_conformance
from system_client import BASE_URL, ROOT, Api

SCHEMA = (
    schemathesis.openapi.from_path(ROOT / "contracts/openapi.json")
    .exclude(path="/api/v1/rees", method="POST")
    .exclude(path="/api/v1/rees/{ree_id}", method="DELETE")
)


@pytest.fixture(scope="module")
def ree(api: Api) -> Iterator[str]:
    ree_id = api.create("fuzzed")
    yield ree_id
    api.keep_archive(ree_id, "fuzzed")
    api.release(ree_id)


@SCHEMA.parametrize()
@settings(max_examples=5, deadline=None, suppress_health_check=list(HealthCheck))
def test_the_api_keeps_its_contract(case: Case[Any], ree: str) -> None:
    if "ree_id" in (case.path_parameters or {}):
        case.path_parameters = {**(case.path_parameters or {}), "ree_id": ree}
    case.call_and_validate(
        base_url=BASE_URL,
        checks=[not_a_server_error, status_code_conformance, response_schema_conformance],
    )
