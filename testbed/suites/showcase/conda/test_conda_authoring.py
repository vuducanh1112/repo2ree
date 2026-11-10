"""A conda environment made by micromamba, which every script that runs in it activates first."""

from __future__ import annotations

import zipfile

from typed_client import Client, NewRee

from repo2ree_testbed.showcases import CONDA, RESULT

F = CONDA


def test_a_conda_environment_is_built_activated_run_and_sealed(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree(image=F.image)
    client.author(ree_id, F)

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    result = zipfile.ZipFile(client.archive(ree_id, "sealed")).read(f"ree/results/{F.experiment}/{RESULT}")
    assert "environment: /tmp/ree-conda-runtime/env" in result.decode().splitlines()
