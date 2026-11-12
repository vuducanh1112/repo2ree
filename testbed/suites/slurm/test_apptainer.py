"""An REE whose experiment environment is a SIF, entered with Apptainer in a Slurm job, all by the author's scripts."""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable

from system_client import RESULT, Api
from typed_client import Client, NewRee

from repo2ree_testbed.showcases import APPTAINER

PLACED = r"ran in job \d+ container \S*runtime\.sif"


def built(api: Api, ree_id: str) -> None:
    api.acquire(ree_id, APPTAINER)
    api.succeed(ree_id, "evaluate")
    run = api.build_experiment_environment(ree_id, fixture=APPTAINER)
    assert run["status"] == "succeeded", api.logs(ree_id, run["run_id"])


def test_a_sif_experiment_environment_is_run_in_a_job_sealed_and_downloaded(
    api: Api, new_ree: Callable[..., str]
) -> None:
    ree_id = new_ree()
    built(api, ree_id)
    activation = api.activate(ree_id, fixture=APPTAINER)
    assert activation["status"] == "succeeded", api.logs(ree_id, activation["run_id"])
    run = api.experiment(ree_id, fixture=APPTAINER)
    assert run["status"] == "succeeded", api.logs(ree_id, run["run_id"])
    assert re.search(PLACED, api.logs(ree_id, run["run_id"]))

    assert api.seal(ree_id)["status"] == "succeeded"
    archive = api.keep_archive(ree_id, "sealed")
    assert archive is not None
    entries = zipfile.ZipFile(io.BytesIO(archive.read_bytes())).namelist()
    assert f"ree/results/{APPTAINER.experiment}/{RESULT}" in entries
    assert any(entry.endswith("runtime.sif") for entry in entries)


def test_a_reviewer_on_the_cluster_reproduces_the_experiment_from_the_sif(client: Client, new_ree: NewRee) -> None:
    reproduction = client.reproduced(new_ree, APPTAINER)

    assert re.search(PLACED, reproduction.logs)
    assert [(item.experiment_name, item.verdict) for item in reproduction.review.experiment_comparisons] == [
        (APPTAINER.experiment, "identical")
    ]


def test_a_failure_in_the_container_fails_the_experiment_and_leaves_no_receipt(
    api: Api, new_ree: Callable[..., str]
) -> None:
    ree_id = new_ree()
    built(api, ree_id)
    broken = APPTAINER.recipe("experiment.sh").replace("exec python", "exit 7; exec python")

    assert api.experiment(ree_id, run=broken, fixture=APPTAINER)["status"] == "failed"
    assert APPTAINER.experiment not in api.ree(ree_id)["subject"]["receipts"]["experiments"]


def test_a_sif_has_no_sbom_and_the_ree_says_so(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    built(api, ree_id)

    assert api.stage(ree_id, "generate-sbom")["status"] == "failed"
    assert api.audit(ree_id)["sbom"]["evidence"] == "missing"
