from __future__ import annotations

import re
import zipfile
from pathlib import PurePosixPath

from offline_reproduction import reproduce_offline
from system_client import RESULT
from typed_client import Client, NewRee

from repo2ree_testbed.api_models import Cpu, InferenceDag, InferenceRule
from repo2ree_testbed.showcases import PYTHON_DOCKER

F = PYTHON_DOCKER
SBOM = "artifacts/sbom.json"
CPU_MODEL = "Intel Core i9-14900K"
CPU = Cpu(vendor="Intel", cores_per_cpu=24)


def authored(client: Client, new_ree: NewRee) -> str:
    ree_id: str = new_ree()

    client.upload_source(ree_id, F)
    source = client.ree(ree_id).subject.receipts.acquire_source
    assert source is not None
    assert source.source_type == "tarball"
    assert re.fullmatch(r"swh:1:dir:[0-9a-f]{40}", source.observed_swhid or "")

    client.declare_name(ree_id, "ree-hello-world")
    client.declare_catalog(ree_id, version="1.0.0", description="A hello world.")
    assert client.ree(ree_id).subject.definition.catalog.version == "1.0.0"

    assert client.evaluate(ree_id, watch=F.watch).status == "succeeded"

    build = client.infer(ree_id, "build_experiment_environment")
    assert build.decision.dag == InferenceDag.BUILD_EXPERIMENT_ENVIRONMENT
    assert len(build.rules()) == 2, build.rules()
    assert "docker build" in build.body_of(InferenceRule.DOCKERFILE)

    run = client.build_experiment_environment(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    client.declare_cpu(ree_id, CPU_MODEL, CPU)
    hardware = client.ree(ree_id).subject.definition.hbom
    assert hardware is not None
    assert hardware.cpus[CPU_MODEL] == CPU

    assert client.generate_sbom(ree_id, watch=F.watch).status == "succeeded"
    sbom = client.ree(ree_id).subject.receipts.generate_sbom
    assert sbom is not None
    assert sbom.sbom_path == SBOM
    assert client.cross_check_sbom(ree_id, watch=F.watch).status == "succeeded"

    activate = client.infer(ree_id, "activate_experiment_environment").first_body()
    assert "docker load --input" in activate
    assert 'exec docker run --rm -v "$PWD:$PWD" -w "$PWD"' in activate
    run = client.activate(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    client.declare_experiment(ree_id, F)
    assert "exit 64" in client.infer(ree_id, "experiment_run", experiment=F.experiment).first_body()
    run = client.run_experiment(ree_id, F)
    assert run.status == "succeeded", client.logs(ree_id, run)

    audit = client.audit(ree_id)
    for step in (
        audit.acquire_source,
        audit.evaluate_reproducibility,
        audit.build_experiment_environment,
        audit.generate_sbom,
        audit.cross_check_sbom,
        audit.activate_experiment_environment,
    ):
        assert step.evidence == "current", step
    return ree_id


def test_provision_through_seal_offline_reproduction_and_release(client: Client, new_ree: NewRee) -> None:
    ree_id = authored(client, new_ree)
    assert client.seal(ree_id, watch=F.watch).status == "succeeded"
    assert client.sign(ree_id).status == "succeeded"
    archive = client.archive(ree_id, "sealed")
    entries = zipfile.ZipFile(archive).namelist()
    assert f"ree/results/{F.experiment}/{RESULT}" in entries
    assert f"ree/{SBOM}" in entries

    output = reproduce_offline(archive)
    assert "Reusing sealed experiment environment" in output
    assert "Pandas Hello World" in output
    assert "VERIFIED: fail" not in output
    assert "VERIFIED: pass" in output
    assert "All steps completed." in output

    client.release(ree_id)
    assert not client.exists(ree_id)


def test_the_example_ree_is_sealed_without_its_experiment_environment(client: Client, new_ree: NewRee) -> None:
    ree_id = authored(client, new_ree)
    sealed = client.seal(ree_id, experiment_environment_included=False, watch=F.watch)
    assert sealed.status == "succeeded"
    assert client.sign(ree_id).status == "succeeded"
    entries = zipfile.ZipFile(client.archive(ree_id, "sealed")).namelist()
    assert f"ree/results/{F.experiment}/{RESULT}" in entries
    assert f"ree/{SBOM}" in entries
    assert f"ree/artifacts/{PurePosixPath(F.experiment_environment_path).name}" not in entries

    client.release(ree_id)
