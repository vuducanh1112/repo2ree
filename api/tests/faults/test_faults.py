"""Faults the stack injects by real means, at the step a test chooses.

Each test asserts what an author must be able to rely on through the fault; the
behaviour check judges everything the owners recorded around it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from system_client import BUILD_SCRIPT, RUNTIME, TERMINAL, Api, fault

from repo2ree_testbed.faults import (
    CrashApi,
    HealWorkbench,
    LockHistory,
    PartitionWorkbench,
    PauseWorkbench,
    ResumeWorkbench,
    UnlockHistory,
)

SLOW_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'building slowly'\nsleep 120\n"


def slow_build(api: Api, ree_id: str) -> dict[str, Any]:
    api.acquire(ree_id)
    api.succeed(ree_id, "evaluate")
    api.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
    api.write(ree_id, BUILD_SCRIPT, SLOW_BUILD)
    run: dict[str, Any] = api.post(f"/api/v1/rees/{ree_id}/build-runtime")
    api.wait_for_status(ree_id, run["run_id"], "running")
    return run


def disconnected(api: Api, ree_id: str, timeout: float = 60.0) -> bool:
    """Whether the REE's workbench leaves the control plane's list of connected ones within ``timeout``."""
    allocations = api.get("/api/v1/allocations")["allocations"]
    workbench = next(item for item in allocations if item["request"]["ree_id"] == ree_id)["workbench_id"]
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


def test_an_api_crash_fails_the_build_in_flight_and_the_ree_builds_after(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = slow_build(api, ree_id)

    fault(CrashApi())

    assert api.wait(ree_id, run, timeout=120)["status"] == "failed"
    assert answers_again(api, ree_id), "the REE's workbench did not come back after the API restarted"
    assert api.build(ree_id)["status"] == "succeeded"


def test_a_paused_workbench_does_not_leave_its_build_running(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = slow_build(api, ree_id)

    fault(PauseWorkbench(ree_id=ree_id))
    try:
        settled = api.wait(ree_id, run, timeout=90)
    finally:
        fault(ResumeWorkbench(ree_id=ree_id))
    assert settled["status"] in TERMINAL - {"succeeded"}


def test_a_partitioned_workbench_fails_its_build(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = slow_build(api, ree_id)

    fault(PartitionWorkbench(ree_id=ree_id))
    try:
        settled = api.wait(ree_id, run, timeout=90)
    finally:
        fault(HealWorkbench(ree_id=ree_id))
    assert settled["status"] == "failed"


def test_a_command_for_a_bench_that_lost_its_connection_is_refused(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()

    # The control plane must already know the bench is gone, so the command is sent to no one.
    fault(PartitionWorkbench(ree_id=ree_id))
    try:
        assert disconnected(api, ree_id), "the control plane still lists the partitioned workbench"
        answer = api.write(ree_id, "notes.txt", "written while the bench is away\n", expect=None)
    finally:
        fault(HealWorkbench(ree_id=ree_id))
    assert answer.status_code == 503, answer.text


def test_a_build_whose_capture_fails_leaves_nothing_behind_and_the_ree_builds_after(
    api: Api, new_ree: Callable[..., str]
) -> None:
    ree_id = new_ree()
    api.acquire(ree_id)
    api.patch(ree_id, {"build_runtime": {"runtime_path": RUNTIME}})
    inferred = str(api.infer(ree_id, "build")["candidates"][0]["body"])
    shebang, _, body = inferred.partition("\n")
    # A build that works, slowly enough for the history to be locked while it runs.
    api.write(ree_id, BUILD_SCRIPT, f"{shebang}\nsleep 20\n{body}")
    run: dict[str, Any] = api.post(f"/api/v1/rees/{ree_id}/build-runtime")
    api.wait_for_status(ree_id, run["run_id"], "running")

    fault(LockHistory(ree_id=ree_id))
    try:
        settled = api.wait(ree_id, run, timeout=120)
        # An edit meanwhile cannot be recorded either, and is not kept.
        refused = api.write(ree_id, "notes.txt", "written while the history is locked\n", expect=None)
    finally:
        fault(UnlockHistory(ree_id=ree_id))

    # The author is told the build failed, and the REE shows nothing of it: no runtime evidence.
    assert settled["status"] == "failed", settled
    assert api.audit(ree_id)["runtime"]["evidence"] == "missing"
    assert refused.status_code >= 400, refused.text
    unwritten = api.request("GET", f"/api/v1/rees/{ree_id}/files/raw", params={"path": "notes.txt"}, expect=None)
    assert unwritten.status_code == 404, unwritten.text
    assert api.stage(ree_id, "build-runtime")["status"] == "succeeded"
