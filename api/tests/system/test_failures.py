"""Stages that fail, by the author's script or by the system around it.

A failure must leave no evidence behind: no receipt for what did not happen,
and the REE as it stood before. Faults are injected by real means only: a
script that fails, a cancel request, a killed workbench container.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable

import pytest
from system_client import BUILD_SCRIPT, EXPERIMENT, RUNTIME, Api, recipe

FAILING_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'resolving dependencies'\nexit 3\n"
SILENT_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'built nothing'\n"
SLOW_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'building slowly'\nsleep 120\n"


def prepared(api: Api, ree_id: str) -> None:
    api.acquire(ree_id)
    api.succeed(ree_id, "evaluate")


def test_failing_build_leaves_no_receipt(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)

    failed = api.build(ree_id, FAILING_BUILD)
    assert failed["status"] == "failed"
    assert "resolving dependencies" in api.logs(ree_id, failed["run_id"])
    assert api.ree(ree_id)["subject"]["receipts"]["build"] is None
    assert api.audit(ree_id)["runtime"]["evidence"] == "missing"

    # The author fixes the script; the same REE then builds.
    assert api.build(ree_id)["status"] == "succeeded"
    assert api.audit(ree_id)["runtime"]["evidence"] == "current"


def test_build_that_produces_no_runtime_fails(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)

    failed = api.build(ree_id, SILENT_BUILD)
    assert failed["status"] == "failed"
    assert f"did not produce {RUNTIME}" in api.logs(ree_id, failed["run_id"])
    assert api.ree(ree_id)["subject"]["receipts"]["build"] is None


def test_failing_activation_and_unverified_experiment_leave_no_receipts(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    assert api.build(ree_id)["status"] == "succeeded"

    broken = recipe("activation.sh").replace("print('activation ok')", "raise SystemExit(7)")
    assert api.activate(ree_id, broken)["status"] == "failed"
    assert api.ree(ree_id)["subject"]["receipts"]["test_activation"] is None

    # The run succeeds but its claimed result does not hold: the verify script decides.
    wrong_claim = recipe("experiment.verify.sh").replace("Hello, World!", "Goodbye, World!")
    assert api.experiment(ree_id, verify=wrong_claim)["status"] == "failed"
    assert EXPERIMENT not in api.ree(ree_id)["subject"]["receipts"]["experiments"]

    assert api.activate(ree_id)["status"] == "succeeded"
    assert api.experiment(ree_id)["status"] == "succeeded"


@pytest.mark.xfail(
    strict=True,
    reason="product bug: the workbench stops the executor with SIGTERM, which then reports no result (exit -15), "
    "so the run goes canceling -> failed (internal) instead of canceled",
)
def test_canceling_a_running_build(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    api.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
    api.write(ree_id, BUILD_SCRIPT, SLOW_BUILD)
    run = api.post(f"/api/v1/rees/{ree_id}/build-runtime")
    api.wait_for_status(ree_id, run["run_id"], "running")

    started = time.monotonic()
    api.post(f"/api/v1/rees/{ree_id}/runs/{run['run_id']}:cancel")
    settled = api.wait(ree_id, run, timeout=60)
    assert settled["status"] == "canceled"
    assert time.monotonic() - started < 30, "cancel waited for the script instead of stopping it"
    assert api.ree(ree_id)["subject"]["receipts"]["build"] is None

    # The workbench is still usable after the canceled build.
    assert api.build(ree_id)["status"] == "succeeded"


@pytest.mark.xfail(
    strict=True,
    reason="product bug: the run fails ('workbench connection closed') but the allocation stays assigned: "
    "releasing the REE skips the teardown, because WorkbenchManager.lookup returns no handle for a bench "
    "that is not running (api/src/repo2ree_api/control/rees.py delete_ree_route)",
)
def test_workbench_lost_during_a_build(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    api.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
    api.write(ree_id, BUILD_SCRIPT, SLOW_BUILD)
    allocation = next(
        item for item in api.get("/api/v1/allocations")["allocations"] if item["request"]["ree_id"] == ree_id
    )
    run = api.post(f"/api/v1/rees/{ree_id}/build-runtime")
    api.wait_for_status(ree_id, run["run_id"], "running")

    container = f"repo2ree-wb-{allocation['request']['allocation_id']}"
    subprocess.run(["docker", "kill", container], check=True, capture_output=True)

    settled = api.wait(ree_id, run, timeout=90)
    assert settled["status"] == "failed"

    # The supervisor gets a grace period to notice its bench is gone.
    allocation_id = allocation["request"]["allocation_id"]
    deadline = time.monotonic() + 30
    while (record := api.get(f"/api/v1/allocations/{allocation_id}"))["state"] == "assigned":
        if time.monotonic() > deadline:
            break
        time.sleep(1)
    assert record["state"] in {"lost", "failed", "draining", "released"}, record
