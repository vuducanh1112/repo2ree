"""Authoring an REE end to end, on a bench with no Docker daemon and nothing to download."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable

from system_client import BUILD_SCRIPT, EXPERIMENT, RESULT, Api, recipe

AUTHORED_STEPS = ("source", "evaluation", "hardware", "runtime", "test_activation")


def test_author_seal_and_download(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)

    audit = api.audit(ree_id)
    for step in AUTHORED_STEPS:
        assert audit[step]["evidence"] == "current", (step, audit[step])
    assert [(item["name"], item["run"]["evidence"]) for item in audit["experiments"]] == [(EXPERIMENT, "current")]

    assert api.seal(ree_id)["status"] == "succeeded"
    sealed = api.ree(ree_id)
    assert sealed["seal"]["ree_digest"].startswith("sha256:")
    receipts = sealed["subject"]["receipts"]
    for name in ("source", "evaluation", "hardware_observation", "build", "test_activation"):
        assert receipts[name] is not None, name
    assert EXPERIMENT in receipts["experiments"]

    archive = api.keep_archive(ree_id, "sealed")
    assert archive is not None
    entries = zipfile.ZipFile(io.BytesIO(archive.read_bytes())).namelist()
    assert f"ree/results/{EXPERIMENT}/{RESULT}" in entries
    assert any(entry.endswith(BUILD_SCRIPT) for entry in entries)


def test_sealed_ree_is_frozen(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    assert api.seal(ree_id)["status"] == "succeeded"
    digest = api.ree(ree_id)["seal"]["ree_digest"]

    assert api.write(ree_id, "notes.txt", "after the seal\n", expect=None).status_code >= 400
    assert api.patch(ree_id, {"name": "renamed after the seal"}, expect=None).status_code >= 400
    rebuild = api.request("POST", f"/api/v1/rees/{ree_id}/build-runtime", json={}, expect=None)
    if rebuild.status_code == 200:
        assert api.wait(ree_id, rebuild.json())["status"] == "failed"
    else:
        assert rebuild.status_code >= 400

    assert api.ree(ree_id)["seal"]["ree_digest"] == digest


def test_a_bundle_never_loads_into_a_sealed_ree(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)
    draft = api.keep_archive(ree_id, "draft")
    assert draft is not None
    assert api.seal(ree_id)["status"] == "succeeded"
    digest = api.ree(ree_id)["seal"]["ree_digest"]

    # The REE's own draft, loaded back over its seal: either step may refuse it.
    data = draft.read_bytes()
    upload = api.request(
        "POST",
        f"/api/v1/rees/{ree_id}/ree:upload-init",
        json={"file_name": "ree.zip", "size": len(data), "content_type": "application/zip"},
        expect=None,
    )
    if upload.status_code == 200:
        api.request("PUT", upload.json()["upload_url"], content=data)
        loading = api.request(
            "POST",
            f"/api/v1/rees/{ree_id}/ree:load",
            json={"upload_token": upload.json()["upload_token"], "archive_name": "ree.zip"},
            expect=None,
        )
        if loading.status_code == 200:
            assert api.wait(ree_id, loading.json())["status"] == "failed"
        else:
            assert loading.status_code >= 400
    else:
        assert upload.status_code >= 400

    seal = api.ree(ree_id).get("seal")
    assert seal is not None, "the load unsealed the REE"
    assert seal["ree_digest"] == digest, seal


def test_stale_evidence_blocks_seal_until_rebuilt(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    api.author(ree_id)

    # Editing the build after its receipt exists makes that receipt stop speaking for the REE.
    body = api.request("GET", f"/api/v1/rees/{ree_id}/files/raw", params={"path": f"workspace/{BUILD_SCRIPT}"}).text
    api.write(ree_id, BUILD_SCRIPT, body + "# touched after the build\n")
    stale = api.audit(ree_id)["runtime"]
    assert stale["evidence"] == "stale", stale
    assert "runtime build script changed" in stale["reasons"], stale

    sealing = api.request(
        "POST",
        f"/api/v1/rees/{ree_id}/ree:seal",
        json={"include_source": True, "include_runtime": True, "include_results": True},
        expect=None,
    )
    if sealing.status_code == 200:
        assert api.wait(ree_id, sealing.json())["status"] == "failed"
    else:
        assert sealing.status_code >= 400
    assert api.ree(ree_id).get("seal") is None

    # Rebuilding returns the runtime to current; whatever ran on the old runtime runs again.
    assert api.stage(ree_id, "build-runtime")["status"] == "succeeded"
    assert api.audit(ree_id)["runtime"]["evidence"] == "current"
    assert api.activate(ree_id, recipe("activation.sh"))["status"] == "succeeded"
    assert api.experiment(ree_id)["status"] == "succeeded"
    assert api.seal(ree_id)["status"] == "succeeded"


def test_sealed_bundle_loads_into_a_fresh_ree(api: Api, new_ree: Callable[..., str]) -> None:
    author = new_ree("bundle-author")
    api.author(author)
    assert api.seal(author)["status"] == "succeeded"
    sealed = api.ree(author)
    archive = api.keep_archive(author, "bundle")
    assert archive is not None
    data = archive.read_bytes()

    reader = new_ree("bundle-reader")
    upload = api.post(
        f"/api/v1/rees/{reader}/ree:upload-init",
        {"file_name": "ree.zip", "size": len(data), "content_type": "application/zip"},
    )
    api.request("PUT", upload["upload_url"], content=data)
    loaded = api.stage(reader, "ree:load", {"upload_token": upload["upload_token"], "archive_name": "ree.zip"})
    assert loaded["status"] == "succeeded", api.logs(reader, loaded["run_id"])

    restored = api.ree(reader)
    assert restored["seal"] == sealed["seal"]
    assert restored["subject"]["receipts"]["build"] == sealed["subject"]["receipts"]["build"]
