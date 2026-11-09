"""An REE whose author's scripts submit their work to Slurm, which the product runs like any other script."""

from __future__ import annotations

import re
import zipfile

from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.showcases import SLURM

F = SLURM


def test_an_experiment_run_as_a_job_is_sealed_and_downloaded(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree()
    client.upload_source(ree_id, F)
    assert client.evaluate(ree_id).status == "succeeded"
    assert client.build(ree_id, F).status == "succeeded"
    assert client.activate(ree_id, F).status == "succeeded"
    run = client.run_experiment(ree_id, F)
    logs = client.logs(ree_id, run)
    assert run.status == "succeeded", logs
    assert re.search(r"ran in Slurm job \d+", logs)

    assert client.seal(ree_id).status == "succeeded"
    assert f"ree/results/{F.experiment}/{RESULT}" in zipfile.ZipFile(client.archive(ree_id, "sealed")).namelist()
