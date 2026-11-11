"""Faults the stack injects by real means, at the step a test chooses.

Each test asserts what an author must be able to rely on through the fault; the
behaviour check judges everything the owners recorded around it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from system_client import BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, EXPERIMENT_ENVIRONMENT, Api, fault

from repo2ree_testbed.faults import (
    CrashApi,
    HealWorkbench,
    LockHistory,
    PartitionWorkbench,
    PauseWorkbench,
    RestartWorkbench,
    ResumeWorkbench,
    StartRivalWorkbench,
    StopRivalWorkbench,
    UnlockHistory,
)

# A script no REE starts with: an experiment's verify script, authored before it is declared.
UNWRITTEN_SCRIPT = "ree-scripts/experiments/unwritten.verify.sh"


def build_taking(api: Api, ree_id: str, seconds: int) -> dict[str, Any]:
    """A build that works, and takes ``seconds`` before it does; running once this returns."""
    api.acquire(ree_id)
    api.patch(ree_id, {"experiment_environment": {"artifact_path": EXPERIMENT_ENVIRONMENT}})
    inferred = str(api.infer(ree_id, "build_experiment_environment")["candidates"][0]["body"])
    shebang, _, body = inferred.partition("\n")
    api.write(
        ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, f"{shebang}\necho 'building slowly'\nsleep {seconds}\n{body}"
    )
    run: dict[str, Any] = api.post(f"/api/v1/rees/{ree_id}/build-experiment-environment")
    api.wait_for_status(ree_id, run["run_id"], "running")
    return run


def built(api: Api, ree_id: str, run: dict[str, Any]) -> None:
    """The build ran to its end through the fault: it succeeded, and what it built is the REE's evidence."""
    settled = api.wait(ree_id, run, timeout=300)
    assert settled["status"] == "succeeded", settled
    assert api.audit(ree_id)["experiment_environment"]["evidence"] == "current"


def serving(api: Api, ree_id: str) -> str:
    """The workbench serving the REE's store."""
    store = next(item for item in api.get("/api/v1/rees")["items"] if item["ree_id"] == ree_id)["location_id"]
    return str(next(item for item in api.get("/api/v1/stores")["stores"] if item["store_id"] == store)["workbench_id"])


def disconnected(api: Api, ree_id: str, timeout: float = 60.0) -> bool:
    """Whether the REE's workbench leaves the control plane's list of connected ones within ``timeout``."""
    workbench = serving(api, ree_id)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if workbench not in {item["workbench_id"] for item in api.get("/api/v1/workbenches")["workbenches"]}:
            return True
        time.sleep(1)
    return False


def answers_again(api: Api, ree_id: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if api.request("GET", f"/api/v1/rees/{ree_id}", expect=None).status_code == 200:
            return True
        time.sleep(1)
    return False


def test_a_build_outlives_an_api_crash_and_the_restarted_api_follows_it(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = build_taking(api, ree_id, 30)

    fault(CrashApi())

    assert answers_again(api, ree_id), "the REE's workbench did not come back after the API restarted"
    built(api, ree_id, run)


def test_a_build_outlives_its_workbench_restarting(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = build_taking(api, ree_id, 30)

    fault(RestartWorkbench(ree_id=ree_id))

    built(api, ree_id, run)


def test_a_build_outlives_its_workbench_being_paused(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = build_taking(api, ree_id, 30)

    fault(PauseWorkbench(ree_id=ree_id))
    try:
        assert disconnected(api, ree_id, timeout=120), "the control plane still lists the paused workbench"
    finally:
        fault(ResumeWorkbench(ree_id=ree_id))

    built(api, ree_id, run)


def test_a_build_outlives_a_partition_from_its_workbench(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = build_taking(api, ree_id, 30)

    fault(PartitionWorkbench(ree_id=ree_id))
    try:
        assert disconnected(api, ree_id, timeout=120), "the control plane still lists the partitioned workbench"
    finally:
        fault(HealWorkbench(ree_id=ree_id))

    built(api, ree_id, run)


def test_a_command_for_a_bench_that_lost_its_connection_is_refused(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()

    # The control plane must already know the bench is gone, so the command is sent to no one.
    fault(PartitionWorkbench(ree_id=ree_id))
    try:
        assert disconnected(api, ree_id), "the control plane still lists the partitioned workbench"
        answer = api.write(ree_id, UNWRITTEN_SCRIPT, "#!/bin/sh\n", expect=None)
    finally:
        fault(HealWorkbench(ree_id=ree_id))
    assert answer.status_code == 503, answer.text


def test_a_second_workbench_claiming_a_served_store_is_refused(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    serving_before = serving(api, ree_id)

    # The fault returns once the API has turned the rival away; it keeps dialing until stopped.
    fault(StartRivalWorkbench(ree_id=ree_id))
    try:
        assert serving(api, ree_id) == serving_before
        listed = {item["workbench_id"] for item in api.get("/api/v1/workbenches")["workbenches"]}
        assert not any(workbench.startswith("rival-") for workbench in listed), listed
        # The store's own workbench goes on serving it.
        api.acquire(ree_id)
    finally:
        fault(StopRivalWorkbench(ree_id=ree_id))


def test_a_build_whose_capture_fails_leaves_nothing_behind_and_the_ree_builds_after(
    api: Api, new_ree: Callable[..., str]
) -> None:
    ree_id = new_ree()
    api.acquire(ree_id)
    api.patch(ree_id, {"experiment_environment": {"artifact_path": EXPERIMENT_ENVIRONMENT}})
    inferred = str(api.infer(ree_id, "build_experiment_environment")["candidates"][0]["body"])
    shebang, _, body = inferred.partition("\n")
    # A build that works, slowly enough for the history to be locked while it runs.
    api.write(ree_id, BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, f"{shebang}\nsleep 20\n{body}")
    run: dict[str, Any] = api.post(f"/api/v1/rees/{ree_id}/build-experiment-environment")
    api.wait_for_status(ree_id, run["run_id"], "running")

    fault(LockHistory(ree_id=ree_id))
    try:
        settled = api.wait(ree_id, run, timeout=120)
        # An edit meanwhile cannot be recorded either, and is not kept.
        refused = api.write(ree_id, UNWRITTEN_SCRIPT, "#!/bin/sh\n", expect=None)
    finally:
        fault(UnlockHistory(ree_id=ree_id))

    # The author is told the build failed, and the REE shows nothing of it: no experiment environment evidence.
    assert settled["status"] == "failed", settled
    assert api.audit(ree_id)["experiment_environment"]["evidence"] == "missing"
    assert refused.status_code >= 400, refused.text
    unwritten = api.request("GET", f"/api/v1/rees/{ree_id}/files/raw", params={"path": UNWRITTEN_SCRIPT}, expect=None)
    assert unwritten.status_code == 404, unwritten.text
    assert api.stage(ree_id, "build-experiment-environment")["status"] == "succeeded"
