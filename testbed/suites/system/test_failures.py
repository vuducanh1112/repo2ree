"""Stages that fail, by the author's script or by the system around it.

A failure must leave no evidence behind: no receipt for what did not happen,
and the REE as it stood before. Faults are injected by real means only: a
script that fails, a cancel request, a workbench container the stack kills.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from system_client import (
    BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    EXPERIMENT,
    EXPERIMENT_ENVIRONMENT,
    RECONNECT_BOUND,
    Api,
    fault,
    recipe,
)

from repo2ree_testbed.faults import KillWorkbench

FAILING_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'resolving dependencies'\nexit 3\n"
SILENT_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'built nothing'\n"
SLOW_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'building slowly'\nsleep 120\n"


def prepared(api: Api, ree_id: str) -> None:
    api.acquire(ree_id)
    api.succeed(ree_id, "evaluate")


def test_failing_build_leaves_no_receipt(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)

    failed = api.build_experiment_environment(ree_id, FAILING_BUILD)
    assert failed["status"] == "failed"
    assert "resolving dependencies" in api.logs(ree_id, failed["run_id"])
    assert api.ree(ree_id)["subject"]["receipts"]["build_experiment_environment"] is None
    assert api.audit(ree_id)["experiment_environment"]["evidence"] == "missing"

    # The author fixes the script; the same REE then builds.
    assert api.build_experiment_environment(ree_id)["status"] == "succeeded"
    assert api.audit(ree_id)["experiment_environment"]["evidence"] == "current"


def test_build_that_produces_no_experiment_environment_fails(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)

    failed = api.build_experiment_environment(ree_id, SILENT_BUILD)
    assert failed["status"] == "failed"
    assert f"did not produce {EXPERIMENT_ENVIRONMENT}" in api.logs(ree_id, failed["run_id"])
    assert api.ree(ree_id)["subject"]["receipts"]["build_experiment_environment"] is None


def test_failing_activation_and_unverified_experiment_leave_no_receipts(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    assert api.build_experiment_environment(ree_id)["status"] == "succeeded"

    broken = recipe("activation.sh").replace("print('activation ok')", "raise SystemExit(7)")
    assert api.activate(ree_id, broken)["status"] == "failed"
    assert api.ree(ree_id)["subject"]["receipts"]["test_activation"] is None

    # The run succeeds but its claimed result does not hold: the verify script decides.
    wrong_claim = recipe("experiment.verify.sh").replace("Hello, World!", "Goodbye, World!")
    assert api.experiment(ree_id, verify=wrong_claim)["status"] == "failed"
    assert EXPERIMENT not in api.ree(ree_id)["subject"]["receipts"]["experiments"]

    assert api.activate(ree_id)["status"] == "succeeded"
    assert api.experiment(ree_id)["status"] == "succeeded"


def test_canceling_a_running_build(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    api.patch(ree_id, {"experiment_environment": {"artifact_path": EXPERIMENT_ENVIRONMENT}})
    api.write(ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, SLOW_BUILD)
    run = api.post(f"/api/v1/rees/{ree_id}/build-experiment-environment")
    api.wait_for_status(ree_id, run["run_id"], "running")

    started = time.monotonic()
    api.post(f"/api/v1/rees/{ree_id}/runs/{run['run_id']}:cancel")
    settled = api.wait(ree_id, run, timeout=60)
    assert settled["status"] == "canceled"
    assert time.monotonic() - started < 30, "cancel waited for the script instead of stopping it"
    assert api.ree(ree_id)["subject"]["receipts"]["build_experiment_environment"] is None
    # The attempt ended, it was not abandoned: captured, and canceled. (That its capture changed
    # nothing is witnessed from Git by the behaviour check: canceled-attempts-change-nothing.)
    attempts = [
        item for item in api.get(f"/api/v1/rees/{ree_id}/history")["operations"] if item["run_id"] == run["run_id"]
    ]
    assert [(item["operation_status"], item["capture_status"]) for item in attempts] == [("canceled", "captured")]

    # The workbench is still usable after the canceled build.
    assert api.build_experiment_environment(ree_id)["status"] == "succeeded"


def test_a_store_outlives_its_workbench_killed_during_a_build(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    api.patch(ree_id, {"experiment_environment": {"artifact_path": EXPERIMENT_ENVIRONMENT}})
    api.write(ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, SLOW_BUILD)
    run = api.post(f"/api/v1/rees/{ree_id}/build-experiment-environment")
    api.wait_for_status(ree_id, run["run_id"], "running")
    deadline = time.monotonic() + 60
    while "building slowly" not in api.logs(ree_id, run["run_id"]):
        assert time.monotonic() < deadline, "the build never started"
        time.sleep(0.5)

    # Killed as a crash, and started again as its service manager would.
    fault(KillWorkbench(ree_id=ree_id))

    settled = api.wait(ree_id, run, timeout=90)
    assert settled["status"] == "failed"
    # The REE lives in the store, not in the workbench: it is there, as it was, once its workbench is back.
    deadline = time.monotonic() + RECONNECT_BOUND
    while (answer := api.request("GET", f"/api/v1/rees/{ree_id}", expect=None)).status_code == 503:
        assert time.monotonic() < deadline, answer.text
        time.sleep(1)
    assert answer.status_code == 200, answer.text
    assert api.audit(ree_id)["experiment_environment"]["evidence"] == "missing"
    # Its executor died with it, so the restarted workbench had core roll the attempt back and capture it.
    attempts = [
        item for item in api.get(f"/api/v1/rees/{ree_id}/history")["operations"] if item["run_id"] == run["run_id"]
    ]
    assert [(item["operation_status"], item["capture_status"]) for item in attempts] == [("interrupted", "captured")]


def test_an_ree_refuses_another_command_while_one_runs_in_it(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    prepared(api, ree_id)
    api.patch(ree_id, {"experiment_environment": {"artifact_path": EXPERIMENT_ENVIRONMENT}})
    api.write(ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, SLOW_BUILD)
    run = api.post(f"/api/v1/rees/{ree_id}/build-experiment-environment")
    api.wait_for_status(ree_id, run["run_id"], "running")

    # It waits a minute for the build to end, which takes two, and is refused.
    busy = api.request(
        "PUT",
        f"/api/v1/rees/{ree_id}/files/content",
        json={"path": "ree-scripts/activation.verify.sh", "content": "#!/bin/sh\n"},
        expect=None,
        timeout=120.0,
    )

    api.post(f"/api/v1/rees/{ree_id}/runs/{run['run_id']}:cancel")
    assert api.wait(ree_id, run, timeout=60)["status"] == "canceled"
    assert busy.status_code == 409, busy.text
    assert busy.json()["error"]["code"] == "ree_busy"
    api.write(ree_id, "ree-scripts/activation.verify.sh", "#!/bin/sh\n")
