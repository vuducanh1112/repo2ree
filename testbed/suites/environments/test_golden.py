"""The golden path, the same on every machine a workbench is installed on."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable

from system_client import EXPERIMENT, RESULT, Api


def test_an_ree_is_authored_sealed_and_downloaded(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    assert api.seal(ree_id)["status"] == "succeeded"
    assert api.ree(ree_id)["seal"]["ree_digest"].startswith("sha256:")

    archive = api.keep_archive(ree_id, "sealed")
    assert archive is not None
    assert f"ree/results/{EXPERIMENT}/{RESULT}" in zipfile.ZipFile(io.BytesIO(archive.read_bytes())).namelist()
