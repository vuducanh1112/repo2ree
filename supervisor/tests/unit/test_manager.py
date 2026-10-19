from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from repo2ree_protocol import (
    ActionResult,
    AllocationRequest,
    AllocationState,
    AllocationStatusFrame,
    Frame,
    ResultFrame,
)
from repo2ree_protocol.behaviour import close_journal, open_journal
from repo2ree_protocol.command import PatchReeDefinitionArgs, PatchReeDefinitionCommand
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import UnavailableFrame
from repo2ree_protocol.result import HistoryReference
from repo2ree_supervisor import AllocationStore, WorkbenchManager, WorkbenchUnavailableError

_CATALOG_IMAGE = "docker.io/library/docker:29-dind"


class FakeProvider:
    def __init__(self, resolved_image: str = "") -> None:
        self.released: list[str] = []
        self.resolved_image = resolved_image

    def resolve_location(self, location_id: str, image: str) -> tuple[str, str]:
        assert location_id == "lab-1"
        return "provider-1", image or _CATALOG_IMAGE

    def ensure(
        self,
        provider_id: str,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]:
        assert provider_id == "provider-1"
        yield AllocationStatusFrame(
            allocation_id=allocation.allocation_id,
            state=AllocationState.WAITING_FOR_WORKBENCH,
            workbench_id=workbench_id,
            resolved_image=self.resolved_image,
        )

    def release(self, provider_id: str, allocation_id: str) -> None:
        self.released.append(allocation_id)

    def release_best_effort(self, provider_id: str, allocation_id: str) -> bool:
        self.release(provider_id, allocation_id)
        return True

    def is_running(self, provider_id: str, allocation_id: str) -> bool:
        return allocation_id not in self.released


class FakeWorkbench:
    def __init__(self, init_error: Exception | None = None) -> None:
        self.init_error = init_error
        self.assigned: AllocationRequest | None = None
        self.simple_calls: list[list[str]] = []

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        return None

    def assign(self, workbench_id: str, allocation: AllocationRequest) -> None:
        self.assigned = allocation

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        self.simple_calls.append(argv)
        if self.init_error is not None:
            raise self.init_error

    def reserve_external(self, allocation_id: str, location_id: str) -> str:
        return location_id

    def release_reservation(self, workbench_id: str, allocation_id: str) -> None:
        return None

    def drain(self, workbench_id: str) -> None:
        return None

    def is_connected(self, workbench_id: str) -> bool:
        return True

    def exec_action(
        self, workbench_id: str, cmd_json: str, run_id: str, env: dict[str, str], context=None
    ) -> Iterator[Frame]:
        yield ResultFrame(result=ActionResult(status="succeeded"))

    def cancel_run(self, workbench_id: str, run_id: str) -> None:
        return None

    def exec_query(self, workbench_id: str, argv: list[str], timeout: int = 30) -> bytes:
        return b"{}"

    def exec_query_stream(self, workbench_id: str, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        yield b"{}"

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str) -> None:
        return None


def _manager(
    tmp_path: Path, workbench: FakeWorkbench | None = None, provider: FakeProvider | None = None
) -> tuple[WorkbenchManager, AllocationStore, FakeProvider]:
    store = AllocationStore(tmp_path / "allocations.json")
    provider = provider or FakeProvider()
    manager = WorkbenchManager(
        registry=store,
        provider=provider,
        workbench=workbench or FakeWorkbench(),
    )
    return manager, store, provider


def test_provision_records_the_place_and_image_then_assigns(tmp_path: Path) -> None:
    workbench = FakeWorkbench()
    manager, store, _provider = _manager(tmp_path, workbench)

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    assert handle.location_id == "lab-1"
    assert handle.image == _CATALOG_IMAGE
    assert workbench.assigned is not None
    assert workbench.simple_calls == [["init-ree", "--name", "My REE"]]
    assert store.for_ree("ree-1").state == AllocationState.ASSIGNED  # type: ignore[union-attr]


def test_dispatch_mints_distinct_attempts_and_preserves_explicit_retry_context(tmp_path):
    contexts = []

    class RecordingWorkbench(FakeWorkbench):
        def exec_action(self, workbench_id, cmd_json, run_id, env, context=None):
            assert "TRACE_RELAY" not in env
            contexts.append(context)
            yield ResultFrame(result=ActionResult(status="succeeded", context=context))

    manager, _, _ = _manager(tmp_path, RecordingWorkbench())
    handle = manager.provision("ree-1", "test", location_id="lab-1")
    command = PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "test"}))
    first = manager.dispatch_action(handle, command, "repeated-run", lambda *args: None)
    second = manager.dispatch_action(handle, command, "repeated-run", lambda *args: None)
    assert first.context is not None
    assert second.context is not None
    retry = ExecutionContext.new(operation_id=first.context.operation_id, ree_id="ree-1")
    third = manager.dispatch_action(handle, command, "repeated-run", lambda *args: None, retry)
    assert third.context is not None
    assert contexts == [first.context, second.context, third.context]
    assert len({c.attempt_id for c in contexts}) == 3
    assert first.context.operation_id == third.context.operation_id
    assert first.context.operation_id != second.context.operation_id


def test_blank_image_falls_back_to_the_locations_own_catalog(tmp_path: Path) -> None:
    manager, _store, _provider = _manager(tmp_path)

    handle = manager.provision("ree-1", "My REE", location_id="lab-1")

    assert handle.image == _CATALOG_IMAGE


def test_a_bench_that_cannot_take_an_ree_fails_and_is_released(tmp_path: Path) -> None:
    """There is no separate gate: init-ree is what proves the bench usable."""
    workbench = FakeWorkbench(init_error=RuntimeError("/ree is not writable"))
    manager, store, provider = _manager(tmp_path, workbench)

    with pytest.raises(RuntimeError, match="not writable"):
        manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    record = store.for_ree("ree-1")
    assert record is not None
    assert record.state == AllocationState.FAILED
    assert provider.released == [record.request.allocation_id]


def test_the_image_the_bench_came_up_on_wins_over_the_one_asked_for(tmp_path: Path) -> None:
    """A tag moves; the record has to cite what actually ran."""
    pinned = "docker.io/library/docker@sha256:" + "a" * 64
    manager, store, _provider = _manager(tmp_path, provider=FakeProvider(resolved_image=pinned))

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    assert handle.image == pinned
    record = store.for_ree("ree-1")
    assert record is not None
    # The request keeps what was asked for, so the two remain distinguishable.
    assert record.request.image == _CATALOG_IMAGE
    assert record.resolved_image == pinned


def test_a_provider_that_reports_no_digest_leaves_the_requested_ref_standing(tmp_path: Path) -> None:
    manager, _store, _provider = _manager(tmp_path, provider=FakeProvider(resolved_image=""))

    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    assert handle.image == _CATALOG_IMAGE


def test_teardown_releases_allocation_and_placement(tmp_path: Path) -> None:
    manager, store, provider = _manager(tmp_path)
    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)

    manager.teardown(handle)

    assert store.get(handle.allocation_id).state == AllocationState.RELEASED  # type: ignore[union-attr]
    assert store.for_ree("ree-1") is None
    assert provider.released == [handle.allocation_id]


def _exchanges(path):
    return [
        (record["kind"], record.get("message"), record["facts"])
        for record in map(json.loads, path.read_text().splitlines())
        if record["kind"] in {"send", "receive", "abandon"}
    ]


@pytest.mark.parametrize(
    ("frames", "expected", "raises"),
    [
        (
            [ResultFrame(result=ActionResult(status="succeeded"))],
            [("receive", "result", {"status": "succeeded", "commit": None})],
            None,
        ),
        ([UnavailableFrame(detail="gone")], [("receive", "unavailable", {})], WorkbenchUnavailableError),
        ([], [("abandon", None, {"reason": "closed_without_response"})], None),
    ],
)
def test_dispatch_journals_one_request_and_what_came_back(tmp_path, frames, expected, raises):
    sent_contexts = []

    class ScriptedWorkbench(FakeWorkbench):
        def exec_action(self, workbench_id, cmd_json, run_id, env, context=None):
            sent_contexts.append(context)
            yield from frames

    manager, _, _ = _manager(tmp_path, ScriptedWorkbench())
    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)
    opened = open_journal(tmp_path / "journal", "api", hosts=("supervisor",))
    command = PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "x"}))
    try:
        if raises is None:
            manager.dispatch_action(handle, command, "run-1", lambda *_: None)
        else:
            with pytest.raises(raises):
                manager.dispatch_action(handle, command, "run-1", lambda *_: None)
    finally:
        close_journal()

    sent, *outcomes = _exchanges(opened.path)
    assert sent == ("send", "exec_action", {"operation": "patch_ree_definition", "run_id": "run-1"})
    assert outcomes == expected
    # The command carries the request's journal reference, for the attempt's record to cite.
    request = next(json.loads(line) for line in opened.path.read_text().splitlines() if '"kind":"send"' in line)
    assert [context.dispatch_record for context in sent_contexts] == [f"{opened.path.stem}#{request['seq']}"]


def test_a_result_names_the_commit_that_captured_the_attempt(tmp_path):
    history = HistoryReference(
        selection_version=1,
        attempt_id="a1",
        scope=".",
        capture_status="captured",
        after_snapshot_id="c" * 40,
        operation_status="succeeded",
    )

    class CapturingWorkbench(FakeWorkbench):
        def exec_action(self, workbench_id, cmd_json, run_id, env, context=None):
            cited = history.model_copy(update={"attempt_id": context.attempt_id})
            yield ResultFrame(result=ActionResult(status="succeeded", history=cited))

    manager, _, _ = _manager(tmp_path, CapturingWorkbench())
    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)
    opened = open_journal(tmp_path / "journal", "api", hosts=("supervisor",))
    try:
        command = PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "x"}))
        manager.dispatch_action(handle, command, "run-1", lambda *_: None)
    finally:
        close_journal()
    _, outcome = _exchanges(opened.path)
    assert outcome == ("receive", "result", {"status": "succeeded", "commit": "c" * 40})


def test_dispatch_that_raises_is_journaled_as_abandoned(tmp_path):
    class BrokenWorkbench(FakeWorkbench):
        def exec_action(self, workbench_id, cmd_json, run_id, env, context=None):
            raise TimeoutError("socket stalled")
            yield  # pragma: no cover

    manager, _, _ = _manager(tmp_path, BrokenWorkbench())
    handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)
    opened = open_journal(tmp_path / "journal", "api", hosts=("supervisor",))
    command = PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch={"name": "x"}))
    try:
        with pytest.raises(TimeoutError):
            manager.dispatch_action(handle, command, "run-1", lambda *_: None)
    finally:
        close_journal()
    assert _exchanges(opened.path)[1:] == [("abandon", None, {"reason": "TimeoutError"})]


def test_allocation_lifecycle_is_journaled_by_its_owner(tmp_path):
    opened = open_journal(tmp_path / "journal", "api", hosts=("supervisor",))
    manager, _, _ = _manager(tmp_path)
    try:
        handle = manager.provision("ree-1", "My REE", location_id="lab-1", image=_CATALOG_IMAGE)
        manager.teardown(handle)
    finally:
        close_journal()
    records = [json.loads(line) for line in opened.path.read_text().splitlines()]
    assert [(r["owner"], r["from"], r["to"]) for r in records if r["kind"] == "transition"] == [
        ("supervisor", None, "requested"),
        ("supervisor", "requested", "provisioning"),
        ("supervisor", "provisioning", "waiting_for_workbench"),
        ("supervisor", "waiting_for_workbench", "ready"),
        ("supervisor", "ready", "assigned"),
        ("supervisor", "assigned", "draining"),
        ("supervisor", "draining", "released"),
    ]
