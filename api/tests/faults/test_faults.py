"""Faults the stack injects by real means, at the step a test chooses.

Each test asserts what an author must be able to rely on through the fault; the
behaviour check judges everything the owners recorded around it.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pytest
from system_client import BUILD_SCRIPT, LIGHTWEIGHT_IMAGE, RUNTIME, TERMINAL, Api, fault

from repo2ree_testbed.faults import (
    CrashApi,
    HealWorkbench,
    MisdirectProviders,
    PartitionWorkbench,
    PauseWorkbench,
    RestoreProviders,
    ResumeWorkbench,
)

SLOW_BUILD = "#!/usr/bin/env sh\nset -eu\necho 'building slowly'\nsleep 120\n"
NO_SUCH_IMAGE = "docker.io/library/repo2ree-no-such-image:never"


def allocation(api: Api, ree_id: str) -> str:
    allocations = api.get("/api/v1/allocations")["allocations"]
    return str(next(item for item in allocations if item["request"]["ree_id"] == ree_id)["request"]["allocation_id"])


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


def provision(api: Api, image: str) -> dict[str, Any]:
    created: dict[str, Any] = api.post(
        "/api/v1/rees", {"name": "fault-provision", "location_id": api.location(), "image": image}
    )
    settled: dict[str, Any] = api.wait(str(created["ree_id"]), created, timeout=150)
    return settled | {"ree_id": created["ree_id"]}


@pytest.mark.xfail(
    strict=True,
    reason="product bug: workbench enrollments live only in the API's memory (EnrollmentRegistry), so after an API "
    "restart every provider-managed bench is refused on reconnect ('unknown workbench enrollment') and its REE "
    "stays unavailable",
)
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
    bench = allocation(api, ree_id)

    fault(PauseWorkbench(allocation_id=bench))
    try:
        settled = api.wait(ree_id, run, timeout=90)
    finally:
        fault(ResumeWorkbench(allocation_id=bench))
    assert settled["status"] in TERMINAL - {"succeeded"}


def test_a_partitioned_workbench_fails_its_build(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    run = slow_build(api, ree_id)
    bench = allocation(api, ree_id)

    fault(PartitionWorkbench(allocation_id=bench))
    try:
        settled = api.wait(ree_id, run, timeout=90)
    finally:
        fault(HealWorkbench(allocation_id=bench))
    assert settled["status"] == "failed"


def test_a_command_for_a_bench_that_lost_its_connection_is_refused(api: Api, new_ree: Callable[..., str]) -> None:
    ree_id = new_ree()
    bench = allocation(api, ree_id)

    # The control plane must already know the bench is gone, so the command is sent to no one.
    fault(PartitionWorkbench(allocation_id=bench))
    try:
        assert disconnected(api, ree_id), "the control plane still lists the partitioned workbench"
        answer = api.write(ree_id, "notes.txt", "written while the bench is away\n", expect=None)
    finally:
        fault(HealWorkbench(allocation_id=bench))
    assert answer.status_code == 503, answer.text


def test_provisioning_an_image_nobody_has_fails(api: Api) -> None:
    provisioned = provision(api, NO_SUCH_IMAGE)
    api.release(str(provisioned["ree_id"]))

    assert provisioned["status"] == "failed"
    assert all(item["state"] != "assigned" for item in api.get("/api/v1/allocations")["allocations"])


def test_a_bench_that_cannot_call_home_fails_provisioning_and_the_next_one_works(
    api: Api, new_ree: Callable[..., str]
) -> None:
    fault(MisdirectProviders())
    try:
        provisioned = provision(api, LIGHTWEIGHT_IMAGE)
    finally:
        fault(RestoreProviders())
    api.release(str(provisioned["ree_id"]))

    assert provisioned["status"] == "failed"
    assert new_ree()
