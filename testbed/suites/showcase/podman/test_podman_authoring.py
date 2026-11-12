"""An REE whose author's scripts build a Containerfile and run it with rootless Podman, on the machine."""

from __future__ import annotations

import zipfile

from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.showcases import PODMAN

F = PODMAN


def test_a_containerfile_built_with_podman_is_run_sealed_and_downloaded(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree()
    client.upload_source(ree_id, F)
    assert client.evaluate(ree_id, watch=F.watch).status == "succeeded"
    build = client.build_experiment_environment(ree_id, F)
    assert build.status == "succeeded", client.logs(ree_id, build)
    activation = client.activate(ree_id, F)
    assert activation.status == "succeeded", client.logs(ree_id, activation)
    run = client.run_experiment(ree_id, F)
    logs = client.logs(ree_id, run)
    assert run.status == "succeeded", logs
    assert "--- Podman Hello World ---" in logs

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    entries = zipfile.ZipFile(client.archive(ree_id, "sealed")).namelist()
    assert f"ree/results/{F.experiment}/{RESULT}" in entries
    # The image Podman saved is sealed with it, so a reviewer can run it without rebuilding.
    assert "ree/artifacts/runtime.tar" in entries
