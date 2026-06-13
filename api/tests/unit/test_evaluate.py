import pytest


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    from repo2ree_api.settings import service_settings
    from repo2ree_api.storage.init_storage import (
        create_review_storage_if_not_exists,
        create_upload_staging_if_not_exists,
    )

    monkeypatch.setattr(service_settings, "UPLOAD_STAGING_DIR", tmp_path / "upload-staging")
    monkeypatch.setattr(service_settings, "REVIEWS_STORAGE_DIR", tmp_path / "reviews")
    create_upload_staging_if_not_exists()
    create_review_storage_if_not_exists()
    yield tmp_path


def test_get_report_endpoint_404_when_no_workbench():
    # With no workbench registered for the REE, the report endpoint reports 404
    # rather than falling back to any host-side artifact.
    from fastapi import HTTPException

    from repo2ree_api.evaluate import get_workspace_evaluate_report

    with pytest.raises(HTTPException) as excinfo:
        get_workspace_evaluate_report("nonexistent-ree")
    assert excinfo.value.status_code == 404
