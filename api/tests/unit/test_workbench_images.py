"""The workbench image catalog endpoint (GET /api/v1/workbench/images)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from repo2ree_api.workbench.catalog import WORKBENCH_IMAGE_CATALOG, default_workbench_image


def test_list_workbench_images_returns_catalog(client: TestClient) -> None:
    resp = client.get("/api/v1/workbench/images")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    ids = [image["id"] for image in body["images"]]
    assert ids == [image.id for image in WORKBENCH_IMAGE_CATALOG]
    # The default id is one of the listed images.
    assert body["defaultId"] == default_workbench_image().id
    assert body["defaultId"] in ids
    # Every offered image carries the fields the selector renders.
    for image in body["images"]:
        assert image["ref"]
        assert image["label"]
        assert "description" in image
