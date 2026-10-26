"""What an author declares about an REE can be set, changed, and cleared, except the source."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from system_client import EXPERIMENT, RESULT, RUNTIME, Api


def contributor(identifier: str, name: str) -> dict[str, str]:
    return {"identifier": identifier, "name": name, "affiliation_name": "", "affiliation_identifier": ""}


CATALOG: dict[str, Any] = {
    "description": "Prints a greeting",
    "version": "1.0",
    "website": "https://example.org/hello",
    "keywords": ["greeting"],
    "contributors": [contributor("https://orcid.org/0000-0000-0000-0001", "Ada")],
    "corresponding_author_identifier": "https://orcid.org/0000-0000-0000-0001",
}
CHANGED: dict[str, Any] = {
    "description": "Prints a friendlier greeting",
    "version": "1.1",
    "website": "https://example.org/hello/v1.1",
    "keywords": ["greeting", "example"],
    "contributors": [contributor("https://orcid.org/0000-0000-0000-0002", "Grace")],
    "corresponding_author_identifier": "https://orcid.org/0000-0000-0000-0002",
}
CLEARED: dict[str, Any] = {
    "description": "",
    "version": "",
    "website": "",
    "keywords": [],
    "contributors": [],
    "corresponding_author_identifier": None,
}
HARDWARE = {"cpus": {"Any x86-64": {"vendor": "any", "quantity": 1}}}


def definition(api: Api, ree_id: str) -> dict[str, Any]:
    return dict(api.ree(ree_id)["subject"]["definition"])


def test_the_catalog_is_set_changed_and_cleared_but_the_source_is_not_patched(
    api: Api, new_ree: Callable[..., str]
) -> None:
    ree_id = new_ree()
    api.acquire(ree_id)
    for catalog in (CATALOG, CHANGED, CLEARED):
        api.patch(ree_id, {"catalog": catalog})
        assert {key: definition(api, ree_id)["catalog"][key] for key in catalog} == catalog
    api.patch(ree_id, {"name": "renamed"})
    assert definition(api, ree_id)["name"] == "renamed"

    # The source changes only by acquiring or removing it; a whole definition may repeat it unchanged.
    source = definition(api, ree_id)["source"]
    for changed in ({**source, "origin_url": "https://example.org/other.git"}, None):
        assert api.patch(ree_id, {"source": changed}, expect=None).status_code >= 400
    assert definition(api, ree_id)["source"] == source
    api.request("PUT", f"/api/v1/rees/{ree_id}/definition", json={"definition": definition(api, ree_id)})


def test_declared_hardware_runtime_activation_and_experiments_come_and_go(
    api: Api, new_ree: Callable[..., str]
) -> None:
    ree_id = new_ree()
    api.author(ree_id)

    # Declaring hardware makes the step ask for an observation; clearing it leaves the observation standing.
    api.patch(ree_id, {"hardware": HARDWARE})
    api.patch(ree_id, {"hardware": {**HARDWARE, "extra_info": {"note": "any machine"}}})
    api.succeed(ree_id, "generate-hbom")
    api.patch(ree_id, {"hardware": None})
    assert api.audit(ree_id)["hardware"]["evidence"] == "current"

    # Undeclaring what a receipt is about orphans the receipt; declaring it again asks for it anew.
    api.patch(ree_id, {"build_runtime": {"runtime_path": None}})
    assert api.audit(ree_id)["runtime"]["evidence"] == "stale"
    api.patch(ree_id, {"build_runtime": {"runtime_path": f"{RUNTIME}.renamed"}})
    api.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
    api.patch(ree_id, {"test_activation": None})
    assert api.audit(ree_id)["test_activation"]["evidence"] == "stale"
    api.patch(ree_id, {"test_activation": {}})

    experiment = {"name": EXPERIMENT, "output_paths": [RESULT]}
    api.patch(ree_id, {"experiments": [{**experiment, "output_paths": [RESULT, "extra.txt"]}]})
    # Undeclaring an experiment discards its receipt: declared again, it has to run again.
    api.patch(ree_id, {"experiments": []})
    assert api.audit(ree_id)["experiments"] == []
    api.patch(ree_id, {"experiments": [experiment]})
    assert [item["run"]["evidence"] for item in api.audit(ree_id)["experiments"]] == ["missing"]
