"""The whole REE authoring pipeline over HTTP, captured as one trace record.

The lifecycle test beside this one proves the HTTP envelope on a short path
(source in, file written, sealed). This one exists for a different reason: to
drive *every* authoring stage in one run so the trace file holds the complete
flow, and a reader can follow one REE from an empty workbench to a sealed
bundle. Its assertions are deliberately shallow — that each stage reaches a
terminal ``succeeded`` and leaves the evidence the next stage needs — because
what each handler *does* is already pinned by the unit and core suites. What is
not pinned anywhere else is that the stages compose over the real transport.

Deliberately not a recording. The demo walkthrough
(``api/tests/e2e/api_agent_walkthrough.py``) drives the same surface for a human
audience, with narration and asciinema; it needs a live stack and a person to
read it. This runs in CI and leaves a span record behind
(``test-artifacts/traces/api-integration/``), which is what the trace journal
renders.

Scripts here are trivial by intent. A real Dockerfile build is the walkthrough's
job and needs a network and minutes; this one wants the *shape* of the flow —
which stage feeds which — at a cost CI can pay on every run.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import zipfile
from io import BytesIO
from typing import Any

import pytest
from conftest import ReeFilmstrip, bundles_present
from fastapi.testclient import TestClient

RUN_TIMEOUT_SECONDS = 240
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})

BUILD_SCRIPT = "ree-scripts/build_script.sh"
ACTIVATION_SCRIPT = "ree-scripts/activation.sh"
EXPERIMENT_NAME = "demo"
EXPERIMENT_SCRIPT = f"ree-scripts/experiments/{EXPERIMENT_NAME}.sh"
RUNTIME_ARTIFACT = "runtime.tar"
EXPERIMENT_OUTPUT = "results/demo.txt"

# A real image build, because the SBOM scanner reads ``docker-archive:`` — a
# plain tar is not a runtime it can open. Built ``FROM scratch`` so the bench
# needs no network and the whole stage stays inside the seconds CI can afford;
# the walkthrough is where a realistic base image gets exercised.
#
# A module constant rather than a literal at the call site because the staleness
# stage rewrites this file: the edit has to be a *change* to the same script, so
# both writes must agree on what the original was.
BUILD_SCRIPT_BODY = (
    "#!/bin/sh\n"
    "set -eu\n"
    "mkdir -p image\n"
    "cp README.md requirements.txt app.py image/\n"
    "printf 'FROM scratch\\nCOPY . /\\n' > image/Dockerfile\n"
    "docker build -t pipeline-demo:test image\n"
    f"docker save -o {RUNTIME_ARTIFACT} pipeline-demo:test\n"
)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "version"], capture_output=True).returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available() or not bundles_present(),
    reason="api integration tier needs docker + the executor/tools bundles (run: make e2e-bundles)",
)


# ================================================
# Helpers
# ================================================


def _project_zip() -> bytes:
    """A small source tree with a dependency manifest for the evaluate stage."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.md", "# pipeline demo\n")
        archive.writestr("requirements.txt", "requests==2.31.0\n")
        archive.writestr("app.py", "print('hello')\n")
    return buffer.getvalue()


def _await_run(client: TestClient, ree_id: str, run: dict[str, Any], *, what: str) -> None:
    """Poll one background run to a terminal status, failing with its log tail.

    A stage that fails here is almost never wrong in the way the status says —
    the reason is in the run log, and printing it is the difference between a
    one-line assertion failure and a debugging session against a container that
    no longer exists.
    """
    run_id = run["run_id"]
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    status = ""
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}")
        assert response.status_code == 200, response.text
        status = response.json()["status"]
        if status in TERMINAL_RUN_STATUSES:
            break
        time.sleep(0.5)
    if status != "succeeded":
        logs = client.get(f"/api/v1/rees/{ree_id}/runs/{run_id}/logs")
        tail = logs.json().get("entries", [])[-25:] if logs.status_code == 200 else []
        rendered = "\n".join(f"  [{entry.get('level')}] {entry.get('message')}" for entry in tail)
        pytest.fail(f"{what} run {run_id} ended {status or 'pending'}\n{rendered}")


def _stage(client: TestClient, ree_id: str, path: str, payload: dict[str, Any], *, what: str) -> None:
    response = client.post(f"/api/v1/rees/{ree_id}/{path}", json=payload)
    assert response.status_code == 200, f"{what}: {response.text}"
    _await_run(client, ree_id, response.json(), what=what)


def _put_file(client: TestClient, ree_id: str, path: str, content: str) -> None:
    response = client.put(f"/api/v1/rees/{ree_id}/files/content", json={"path": path, "content": content})
    assert response.status_code == 200, f"write {path}: {response.text}"


def _patch_definition(client: TestClient, ree_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    response = client.patch(f"/api/v1/rees/{ree_id}/definition", json={"definition_patch": patch})
    assert response.status_code == 200, response.text
    definition: dict[str, Any] = response.json()["ree"]["subject"]["definition"]
    return definition


def _upload_source(client: TestClient, ree_id: str, data: bytes) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/rees/{ree_id}/source:upload-init",
        json={"file_name": "project.zip", "size": len(data), "content_type": "application/zip"},
    )
    assert response.status_code == 200, response.text
    upload = response.json()

    response = client.put(upload["upload_url"], content=data)
    assert response.status_code == 200, response.text

    response = client.post(
        f"/api/v1/rees/{ree_id}/source:upload-complete",
        json={"upload_token": upload["upload_token"], "archive_name": "project.zip"},
    )
    assert response.status_code == 200, response.text
    summary: dict[str, Any] = response.json()
    return summary


# ================================================
# Flow
# ================================================


def test_full_authoring_pipeline(client: TestClient, ree: dict[str, Any], filmstrip: ReeFilmstrip) -> None:
    ree_id = ree["ree_id"]
    # One frame per authoring act, recording what the REE became. The labels
    # are the stage names above them, so the capture reads as this test does.
    filmstrip.frame(ree_id, "provisioned")

    # --- source ---------------------------------------------------------
    _await_run(client, ree_id, _upload_source(client, ree_id, _project_zip()), what="source")

    filmstrip.frame(ree_id, "source")

    # --- evaluate: reads the declared dependencies off the source --------
    _stage(client, ree_id, "evaluate", {}, what="evaluate")

    filmstrip.frame(ree_id, "evaluate")

    # --- hardware: an observation of the machine this runs on ------------
    _stage(client, ree_id, "generate-hbom", {}, what="hbom")

    filmstrip.frame(ree_id, "hbom")

    # --- build: declare where the runtime lands, then produce it ---------
    # The declaration comes first on purpose: the build receipt binds this path
    # to what it finds there, so a build with nowhere to look is refused.
    _put_file(client, ree_id, BUILD_SCRIPT, BUILD_SCRIPT_BODY)
    definition = _patch_definition(client, ree_id, {"build_runtime": {"runtime_path": RUNTIME_ARTIFACT}})
    assert definition["build_runtime"]["runtime_path"] == RUNTIME_ARTIFACT
    filmstrip.frame(ree_id, "declare runtime")
    _stage(client, ree_id, "build-runtime", {}, what="build")

    state = client.get(f"/api/v1/rees/{ree_id}").json()
    assert any(item.get("path") == RUNTIME_ARTIFACT for item in state["workspace_files"]), (
        "the build did not leave a runtime at the declared path"
    )

    filmstrip.frame(ree_id, "build")

    # --- staleness: a receipt stops speaking for what it describes -------
    # Editing the build script after its receipt exists is the ordinary way an
    # REE goes stale, and until here nothing exercised it over the transport.
    # Placed before the SBOM so only the runtime step has evidence to lose: the
    # scan and the cross-check have not run, so the edit stales exactly one
    # step, and the rebuild below returns it to current before anything
    # downstream is built on it.
    _put_file(client, ree_id, BUILD_SCRIPT, BUILD_SCRIPT_BODY + "# touched after the build\n")
    stale = client.get(f"/api/v1/rees/{ree_id}/state").json()["audit"]
    assert stale["runtime"]["evidence"] == "stale", stale["runtime"]
    assert "runtime build script changed" in stale["runtime"]["reasons"], stale["runtime"]
    filmstrip.frame(ree_id, "edit build script")

    _stage(client, ree_id, "build-runtime", {}, what="rebuild")
    recovered = client.get(f"/api/v1/rees/{ree_id}/state").json()["audit"]
    assert recovered["runtime"]["evidence"] == "current", recovered["runtime"]
    filmstrip.frame(ree_id, "rebuild")

    # --- sbom: scan what the build produced, then reconcile it -----------
    # The scan reads the runtime archive, not the source; the cross-check then
    # compares that against the dependencies the evaluate stage read off the
    # source, so it needs both of the stages above to have run.
    _stage(client, ree_id, "generate-sbom", {"produced_runtime_path": RUNTIME_ARTIFACT}, what="sbom")
    filmstrip.frame(ree_id, "sbom")
    _stage(client, ree_id, "cross-check-sbom", {}, what="sbom cross-check")

    filmstrip.frame(ree_id, "sbom cross-check")

    # --- activation: does the runtime come up at all ---------------------
    _put_file(client, ree_id, ACTIVATION_SCRIPT, "#!/bin/sh\nset -eu\ntar -tf runtime.tar > /dev/null\n")
    _patch_definition(client, ree_id, {"test_activation": {}})
    filmstrip.frame(ree_id, "declare activation")
    _stage(client, ree_id, "activation-test", {}, what="activation")

    filmstrip.frame(ree_id, "activation")

    # --- experiment: the runnable the REE exists to reproduce ------------
    _put_file(
        client,
        ree_id,
        EXPERIMENT_SCRIPT,
        f"#!/bin/sh\nset -eu\nmkdir -p results\necho 'experiment output' > {EXPERIMENT_OUTPUT}\n",
    )
    definition = _patch_definition(
        client,
        ree_id,
        {"experiments": [{"name": EXPERIMENT_NAME, "output_paths": [EXPERIMENT_OUTPUT]}]},
    )
    assert [item["name"] for item in definition["experiments"]] == [EXPERIMENT_NAME]
    filmstrip.frame(ree_id, "declare experiment")
    _stage(client, ree_id, f"experiments/{EXPERIMENT_NAME}:run", {}, what="experiment")

    filmstrip.frame(ree_id, "experiment")

    # --- catalog: what a reader is told this REE is ----------------------
    # The one authoring act that rests on nothing and that nothing rests on:
    # citation metadata is not evidence, so writing it moves no audit verdict.
    # Placed last because that is when an author knows what they have — and it
    # is the case that proves the audit answers for evidence rather than for
    # every edit the definition accepts.
    before = client.get(f"/api/v1/rees/{ree_id}/state").json()["audit"]
    definition = _patch_definition(
        client,
        ree_id,
        {
            "catalog": {
                "description": "A minimal reproducible environment exercised by the pipeline test.",
                "version": "1.0.0",
                "keywords": ["reproducibility", "pipeline", "demo"],
                "contributors": [
                    {
                        "identifier": "https://orcid.org/0000-0002-1825-0097",
                        "name": "Josiah Carberry",
                        "affiliation_name": "Brown University",
                    }
                ],
                "corresponding_author_identifier": "https://orcid.org/0000-0002-1825-0097",
            }
        },
    )
    assert definition["catalog"]["version"] == "1.0.0"
    after = client.get(f"/api/v1/rees/{ree_id}/state").json()["audit"]
    assert after == before, "describing an REE is not evidence and must not disturb the audit"
    filmstrip.frame(ree_id, "describe")

    # --- seal: refused if any receipt above has gone stale ---------------
    response = client.post(f"/api/v1/rees/{ree_id}/ree:seal", json={})
    assert response.status_code == 200, response.text
    sealed = response.json()["ree"]
    assert sealed["seal"]["ree_digest"].startswith("sha256:")
    filmstrip.frame(ree_id, "sealed")

    # Every stage that ran left a receipt the seal is now bound to.
    receipts = sealed["subject"]["receipts"]
    assert receipts["source"] is not None
    assert receipts["evaluation"] is not None
    assert receipts["hardware_observation"] is not None
    assert receipts["build"] is not None
    assert receipts["sbom"] is not None
    assert receipts["sbom_cross_check"] is not None
    assert receipts["test_activation"] is not None
    assert EXPERIMENT_NAME in receipts["experiments"]

    response = client.get(f"/api/v1/rees/{ree_id}/ree-archive")
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist()
