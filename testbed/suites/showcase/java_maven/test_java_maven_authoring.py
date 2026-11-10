"""Another language and toolchain through the same lifecycle: Maven compiles and fetches in the project's own build."""

from __future__ import annotations

import zipfile

from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.api_models import InferenceRule
from repo2ree_testbed.showcases import JAVA_MAVEN

F = JAVA_MAVEN


def test_a_maven_project_is_built_run_sealed_and_released(client: Client, new_ree: NewRee) -> None:
    ree_id = new_ree(image=F.image)
    client.upload_source(ree_id, F)
    assert client.evaluate(ree_id, watch=F.watch).status == "succeeded"

    assert "docker build" in client.infer(ree_id, "build_experiment_environment").body_of(InferenceRule.DOCKERFILE)

    run = client.build_experiment_environment(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    run = client.activate(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    run = client.run_experiment(ree_id, F)
    logs = client.logs(ree_id, run)
    assert run.status == "succeeded", logs
    assert '"greeting": "Hello"' in logs

    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    assert f"ree/results/{F.experiment}/{RESULT}" in zipfile.ZipFile(client.archive(ree_id, "sealed")).namelist()
