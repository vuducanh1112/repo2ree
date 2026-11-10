"""The docker-less branch of the pipeline: a pip venv packed as the experiment environment on the bench."""

from __future__ import annotations

import zipfile

from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.api_models import InferenceDag, InferenceRule
from repo2ree_testbed.showcases import PYTHON_VENV

F = PYTHON_VENV


def test_a_pip_venv_is_inferred_built_run_sealed_and_released(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree(image=F.image)
    client.upload_source(ree_id, F)
    assert client.evaluate(ree_id, watch=F.watch).status == "succeeded"

    build = client.infer(ree_id, "build_experiment_environment")
    assert build.decision.dag == InferenceDag.BUILD_EXPERIMENT_ENVIRONMENT
    body = build.body_of(InferenceRule.PIP_REQUIREMENTS)
    assert "python -m venv" in body
    assert "docker build" not in body

    run = client.build_experiment_environment(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    activate = client.infer(ree_id, "activate_experiment_environment").first_body()
    assert "tar -xzf" in activate
    assert "VENV_DIR=/tmp/ree-venv" in activate
    assert 'exec "$@"' in activate
    scaffold = client.infer(ree_id, "activation_run").first_body()
    assert "exit 64" in scaffold
    assert "tar -xzf" not in scaffold
    run = client.activate(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    # Inference comes before declaring: declaring an experiment needs its run script.
    assert "exit 64" in client.infer(ree_id, "experiment_run", experiment=F.experiment).first_body()
    run = client.run_experiment(ree_id, F)
    logs = client.logs(ree_id, run)
    assert run.status == "succeeded", logs
    assert "Pandas Hello World" in logs

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    assert f"ree/results/{F.experiment}/{RESULT}" in zipfile.ZipFile(client.archive(ree_id, "sealed")).namelist()
