"""An REE whose scripts are each launched as a Slurm job step, through the launch inference proposes."""

from __future__ import annotations

import zipfile

from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.showcases import SLURM

F = SLURM


def test_an_experiment_run_as_a_job_is_sealed_and_downloaded(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree()
    client.upload_source(ree_id, F)
    assert client.evaluate(ree_id).status == "succeeded"
    assert client.build_experiment_environment(ree_id, F).status == "succeeded"
    activation = client.activate(ree_id, F)
    assert activation.status == "succeeded", client.logs(ree_id, activation)
    run = client.run_experiment(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)
    launched = client.ree(ree_id).subject.receipts.experiments[F.experiment].launched
    assert launched is not None
    assert launched.slurm_job_id is not None

    assert client.seal(ree_id).status == "succeeded"
    entries = zipfile.ZipFile(client.archive(ree_id, "sealed")).namelist()
    assert f"ree/results/{F.experiment}/{RESULT}" in entries
    assert "ree/overlay/ree-scripts/launch.sh" in entries
