"""Which workbench a fault reaches: in store mode, the one serving the REE's store."""

from __future__ import annotations

import pytest

from repo2ree_testbed.faults import CrashApi, KillWorkbench, LockHistory, PartitionWorkbench
from repo2ree_testbed.stack.injector import Injector, WorkbenchFault


class _StoreStack:
    owner = "run-1"

    def __init__(self) -> None:
        self.faults: list[tuple[str, WorkbenchFault]] = []
        self.crashed = False

    def crash_api(self) -> None:
        self.crashed = True

    def workbench_fault(self, ree_id: str, action: WorkbenchFault) -> None:
        self.faults.append((ree_id, action))


@pytest.mark.parametrize(
    ("fault", "action"),
    [
        (KillWorkbench(ree_id="ree-1"), "kill"),
        (PartitionWorkbench(ree_id="ree-1"), "partition"),
        (LockHistory(ree_id="ree-1"), "lock_history"),
    ],
)
def test_in_store_mode_a_workbench_fault_reaches_the_store_serving_the_ree(fault: object, action: str) -> None:
    stack = _StoreStack()
    injector = Injector(stack)
    try:
        injector.apply(fault)  # type: ignore[arg-type]
    finally:
        injector.stop()

    assert stack.faults == [("ree-1", action)]


def test_a_fault_that_is_no_workbench_fault_goes_to_the_stack_as_before() -> None:
    stack = _StoreStack()
    injector = Injector(stack)
    try:
        injector.apply(CrashApi())
    finally:
        injector.stop()

    assert stack.crashed
    assert stack.faults == []
