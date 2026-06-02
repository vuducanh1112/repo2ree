import pytest


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    from repo2ree_api.settings import service_settings
    from repo2ree_api.storage.init_storage import (
        create_review_storage_if_not_exists,
        create_upload_staging_if_not_exists,
    )

    monkeypatch.setattr(
        service_settings, "UPLOAD_STAGING_DIR", tmp_path / "upload-staging"
    )
    monkeypatch.setattr(service_settings, "REVIEWS_STORAGE_DIR", tmp_path / "reviews")
    create_upload_staging_if_not_exists()
    create_review_storage_if_not_exists()
    yield tmp_path


def test_ree_from_metadata_normalizes_legacy_invalid_hardware_description_payload():
    from repo2ree_core.domain.ree import REE

    ree = REE.from_metadata(
        {
            "reeDraft": {
                "name": "legacy-hbom",
                "hardware_description": {
                    "memory": "asdasd",
                    "cpu": "awdasd",
                    "gpu": "awdwad",
                },
            }
        }
    )

    assert ree.hardware_description.memory == {}
    assert ree.hardware_description.cpus == {}
    assert ree.hardware_description.gpus == {}
    assert ree.hardware_description.extra_info == {
        "memory": "asdasd",
        "cpu": "awdasd",
        "gpu": "awdwad",
    }
