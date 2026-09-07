from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_api.settings import Settings, service_settings


def test_unit_tier_redirects_every_durable_api_path_to_one_temporary_root() -> None:
    parents = {
        service_settings.UPLOAD_STAGING_DIR.parent,
        service_settings.ALLOCATION_STORE_FILE.parent,
        service_settings.REE_INDEX_FILE.parent,
        service_settings.RUN_REGISTRY_DIR.parent,
    }

    assert len(parents) == 1
    assert parents != {Path(".repo2ree")}


def test_service_does_not_implicitly_load_a_dotenv_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RUN_MAX_WORKERS", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("RUN_MAX_WORKERS=99\n")

    assert Settings().RUN_MAX_WORKERS == 4
