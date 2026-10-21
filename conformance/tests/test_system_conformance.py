"""The real owners, wired in one process, produce evidence that conforms to the specification.

Only the transport is replaced: the workbench runs core's dispatcher in-process
against a temporary REE instead of over a WebSocket in a container. Run store,
allocation store, supervisor, core capture, and Git history are the production
code paths, and their journals and histories are what the checker reads.

Each scenario drives one behaviour, including faults injected at the boundaries.
Together they must exercise every specified edge, except the ones listed in
``UNEXERCISED`` with the reason no in-process scenario reaches them.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from repo2ree_api.control.run_registry import RunRegistry
from repo2ree_api.storage.json_run_store import JsonRunStore
from repo2ree_conformance import check, load_evidence, load_spec
from repo2ree_conformance.check import CheckResult
from repo2ree_core.operations.dispatch import run_command
from repo2ree_core.operations.initialize import initialize_ree
from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol import ActionResult, AllocationRequest, AllocationState, AllocationStatusFrame, Frame
from repo2ree_protocol.behaviour import close_journal, open_journal
from repo2ree_protocol.behaviour import writer as journal_module
from repo2ree_protocol.command import (
    AcquireSourceArgs,
    AcquireSourceCommand,
    Command,
    EvaluateDependencyScoreCommand,
    PatchReeDefinitionArgs,
    PatchReeDefinitionCommand,
    SealReeCommand,
    command_adapter,
)
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import ResultFrame, UnavailableFrame
from repo2ree_supervisor import AllocationStore, WorkbenchManager, WorkbenchUnavailableError

GIT = os.environ.get("REPO2REE_TOOL_GIT") or shutil.which("git")
# Git histories are evidence under test: without git these tests would check nothing, so they fail rather than skip.
if GIT is None:
    raise RuntimeError("conformance tests need a git executable: put git on PATH or set REPO2REE_TOOL_GIT")
ARCHIVE = Path(__file__).resolve().parents[2] / "examples" / "projects" / "python-hello-world.tar.gz"
SPEC = load_spec()

_PROVIDER_GAP = "needs a provider that loses benches or drains them before assignment"
_DOCKER_GAP = "needs runtime, SBOM, or experiment steps, which require Docker (exercised by demo-gui)"
_ACTIONS_GAP = "the scenarios drive the run registry and owners directly, not the API's routes (the e2e tiers do)"
# Declared edges no in-process scenario reaches, and why. A newly specified edge
# must gain a scenario or be listed here; the coverage test enforces both ways.
UNEXERCISED: dict[str, str] = {
    **{
        f"Allocation {edge}": _PROVIDER_GAP
        for edge in (
            "requested -> draining",
            "requested -> failed",
            "requested -> waiting_for_workbench",
            "provisioning -> draining",
            "provisioning -> lost",
            "waiting_for_workbench -> draining",
            "waiting_for_workbench -> failed",
            "waiting_for_workbench -> lost",
            "ready -> draining",
            "ready -> failed",
            "ready -> lost",
            "assigned -> failed",
            "assigned -> lost",
            "draining -> failed",
            "failed -> draining",
            "lost -> draining",
        )
    },
    "Attempt pending -> capture_failed": "needs the before-snapshot itself to fail",
    "Attempt executing -> capture_failed": "needs the record write between handler and capture to fail",
    "Ree (none) -> sealed": "needs a workbench that baselines an REE sealed elsewhere",
    "Run queued -> canceling": "needs cancellation to win the race against the worker starting",
    "Run queued -> failed": "needs the worker pool to refuse scheduling",
    "Run provisioning -> canceling": "needs cancellation during provisioning",
    "Run provisioning -> failed": "needs provisioning through the API route rather than the supervisor directly",
    "Run provisioning -> succeeded": "needs provisioning through the API route rather than the supervisor directly",
    "Run provisioning -> canceled": "needs cancellation during provisioning",
    "Run queued -> provisioning": "needs provisioning through the API route rather than the supervisor directly",
    "Run running -> canceled": "needs an executor that reports canceled without a cancel request",
    "Run canceling -> succeeded": "needs work to finish after cancellation was requested",
    "Run canceling -> failed": "needs work to fail after cancellation was requested",
    **{
        f"Step {edge}": _DOCKER_GAP
        for edge in (
            "(none) -> current",
            "(none) -> stale",
            "missing -> stale",
            "missing -> not_applicable",
            "current -> missing",
            "current -> not_applicable",
            "stale -> missing",
            "stale -> not_applicable",
            "not_applicable -> stale",
        )
    },
    **{
        f"AuthorApiAction {source} -> {target}": _ACTIONS_GAP
        for source, targets in [
            ("(none)", SPEC.entities["AuthorApiAction"].initial),
            *SPEC.entities["AuthorApiAction"].edges.items(),
        ]
        for target in targets
    },
}


class Provider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def resolve_location(self, location_id: str, image: str) -> tuple[str, str]:
        return "provider-1", image or "docker.io/library/docker:29-dind"

    def ensure(self, provider_id: str, allocation: AllocationRequest, workbench_id: str, token: str) -> Iterator[Frame]:
        if self.fail:
            raise RuntimeError("no capacity")
        yield AllocationStatusFrame(
            allocation_id=allocation.allocation_id,
            state=AllocationState.WAITING_FOR_WORKBENCH,
            workbench_id=workbench_id,
        )

    def release(self, provider_id: str, allocation_id: str) -> None:
        return None

    def release_best_effort(self, provider_id: str, allocation_id: str) -> bool:
        return True


class InProcessWorkbench:
    """A workbench whose executor is core's dispatcher, called directly; faults are injected per operation."""

    def __init__(self, layout: ReeLayout) -> None:
        self.layout = layout
        self.faults: dict[str, Callable[[], list[Frame]]] = {}

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None:
        return None

    def assign(self, workbench_id: str, allocation: AllocationRequest) -> None:
        return None

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        assert argv[0] == "init-ree"
        initialize_ree(self.layout, name=argv[-1])

    def drain(self, workbench_id: str) -> None:
        return None

    def exec_action(
        self, workbench_id: str, cmd_json: str, run_id: str, env: dict[str, str], context: Any = None
    ) -> Iterator[Frame]:
        command = command_adapter.validate_json(cmd_json)
        fault = self.faults.get(str(command.operation))
        if fault is not None:
            yield from fault()
            return
        yield ResultFrame(result=run_command(command, log=lambda *_: None, run_id=run_id, context=context))


@dataclass
class System:
    tmp: Path
    layout: ReeLayout
    store: JsonRunStore
    manager: WorkbenchManager
    registry: RunRegistry
    workbench: InProcessWorkbench

    def provision(self) -> Any:
        return self.manager.provision("ree-1", "demo", location_id="lab-1")

    def dispatch(self, handle: Any, command: Command, run_id: str = "sync") -> ActionResult:
        return self.manager.dispatch_action(handle, command, run_id, lambda *_: None)

    def start(self, operation: str, runner: Callable[[str, str], ActionResult]) -> str:
        started = self.registry.start_background("ree-1", operation, {}, operation, runner)  # type: ignore[arg-type]
        return str(started["run_id"])

    def run(self, handle: Any, command: Command, operation: str = "evaluate") -> str:
        run_id = self.start(operation, lambda ree_id, run: self.dispatch(handle, command, run))
        return self.settle(run_id)

    def wait_for(self, run_id: str, *statuses: str) -> str:
        for _ in range(500):
            run = self.store.get("ree-1", run_id)
            if run is not None and run.status in statuses:
                return run.status
            time.sleep(0.01)
        raise AssertionError(f"run never reached {statuses}")

    def settle(self, run_id: str) -> str:
        return self.wait_for(run_id, "succeeded", "failed", "canceled")

    def stage(self, archive: Path) -> str:
        token = uuid.uuid4().hex
        staging = self.layout.root / "upload-staging"
        staging.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, staging / f"{token}.bin")
        return token

    def evidence(self, *, journal: bool = True, git: bool = True) -> CheckResult:
        stores = self.tmp / "stores"
        if (self.tmp / "runs").exists():
            shutil.copytree(self.tmp / "runs", stores / "runs", dirs_exist_ok=True)
        if (self.tmp / "allocations.json").exists():
            stores.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.tmp / "allocations.json", stores / "allocations.json")
        journals = [self.tmp / "journal"] if journal else []
        repositories = [self.layout.root] if git and (self.layout.root / ".git").exists() else []
        return check(SPEC, load_evidence(journals, repositories, str(GIT), [stores] if stores.exists() else []))

    def finish(self) -> CheckResult:
        self.registry.shutdown()
        close_journal()
        return self.evidence()


def make_system(tmp: Path, monkeypatch: pytest.MonkeyPatch, provider: Provider | None = None) -> System:
    monkeypatch.setenv("REPO2REE_TOOL_GIT", str(GIT))
    layout = ReeLayout(root=tmp / "ree")
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    open_journal(tmp / "journal", "api", hosts=("api", "supervisor"))
    store = JsonRunStore(tmp / "runs")
    workbench = InProcessWorkbench(layout)
    manager = WorkbenchManager(
        registry=AllocationStore(tmp / "allocations.json"),
        provider=provider or Provider(),  # type: ignore[arg-type]
        workbench=workbench,  # type: ignore[arg-type]
    )
    return System(tmp, layout, store, manager, RunRegistry(lambda ree_id: None, store, max_workers=1), workbench)


@pytest.fixture
def system(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[System]:
    built = make_system(tmp_path, monkeypatch)
    try:
        yield built
    finally:
        built.registry.shutdown()
        close_journal()


def verdicts(result: CheckResult) -> dict[str, str]:
    return {rule.rule: str(rule.verdict) for rule in result.rules} | {"overall": str(result.verdict)}


def assert_conforms(result: CheckResult, *triggered: str) -> None:
    found = verdicts(result)
    problems = {rule: verdict for rule, verdict in found.items() if verdict not in {"passed", "not_triggered"}}
    assert problems == {}, [finding for rule in result.rules for finding in rule.findings]
    assert {rule: found[rule] for rule in triggered if found[rule] != "passed"} == {}


def patch(definition: dict[str, Any]) -> PatchReeDefinitionCommand:
    return PatchReeDefinitionCommand(args=PatchReeDefinitionArgs(patch=definition))


# ================================================
# Scenarios
# ================================================


def lifecycle(system: System) -> CheckResult:
    handle = system.provision()
    system.dispatch(handle, patch({"name": "synchronous"}))
    assert system.run(handle, patch({"name": "background"})) == "succeeded"
    system.manager.teardown(handle)
    return system.finish()


def authoring_and_sealing(system: System) -> CheckResult:
    handle = system.provision()
    token = system.stage(ARCHIVE)
    upload = AcquireSourceArgs(mode="upload", upload_token=token, archive_name=ARCHIVE.name)
    assert system.run(handle, AcquireSourceCommand(args=upload), "source") == "succeeded"
    assert system.run(handle, EvaluateDependencyScoreCommand(), "evaluate") == "succeeded"
    declared = system.dispatch(handle, patch({"name": "authored"})).outputs["definition"]["source"]
    # Re-pointing the declared source makes the source receipt stale, so sealing must refuse.
    system.dispatch(handle, patch({"source": {**declared, "origin_url": "https://example.org/other.tar.gz"}}))
    assert system.dispatch(handle, SealReeCommand()).status == "failed"
    # Restoring the declaration makes the same receipt current again; now sealing succeeds.
    system.dispatch(handle, patch({"source": declared}))
    assert system.run(handle, SealReeCommand(), "seal") == "succeeded"
    assert system.dispatch(handle, patch({"name": "too late"})).status == "failed"
    system.manager.teardown(handle)
    return system.finish()


def faults_at_the_boundary(system: System) -> CheckResult:
    handle = system.provision()
    system.workbench.faults["patch_ree_definition"] = lambda: [UnavailableFrame(detail="bench gone")]
    assert system.run(handle, patch({"name": "lost"}), "evaluate") == "failed"
    system.workbench.faults["patch_ree_definition"] = list  # The stream ends without any terminal frame.
    assert system.dispatch(handle, patch({"name": "silent"})).status == "failed"
    system.manager.teardown(handle)
    return system.finish()


def cancellation(system: System) -> CheckResult:
    handle = system.provision()
    released = threading.Event()

    def runner(ree_id: str, run_id: str) -> ActionResult:
        released.wait(5)
        return ActionResult(status="canceled")

    run_id = system.start("build", runner)
    system.wait_for(run_id, "running")
    system.registry.mark_cancel_requested("ree-1", run_id)
    released.set()
    assert system.settle(run_id) == "canceled"
    system.manager.teardown(handle)
    return system.finish()


def capture_failure(system: System, monkeypatch: pytest.MonkeyPatch) -> CheckResult:
    handle = system.provision()

    def broken(self: GitHistory, **kwargs: Any) -> tuple[str, bool]:
        raise HistoryCaptureError("disk full")

    with monkeypatch.context() as patched:
        patched.setattr(GitHistory, "commit_operation", broken)
        assert system.dispatch(handle, patch({"name": "unrecorded"})).status == "failed"
    system.manager.teardown(handle)
    return system.finish()


def provisioning_failure(system: System) -> CheckResult:
    system.manager._provider = Provider(fail=True)  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="no capacity"):
        system.provision()
    return system.finish()


def process_restart(system: System) -> CheckResult:
    """The API dies mid-run; the next process epoch settles the run as interrupted."""
    blocker = threading.Event()

    def runner(ree_id: str, run_id: str) -> ActionResult:
        blocker.wait(5)
        return ActionResult(status="succeeded")

    run_id = system.start("build", runner)
    system.wait_for(run_id, "running")
    # Simulated process death: the old journal is abandoned without its closing record,
    # and the successor process opens the next epoch and settles what it finds active.
    journal_module._current = journal_module.FileJournal(system.tmp / "journal", "api", ("api", "supervisor"))
    JsonRunStore(system.tmp / "runs").interrupt_incomplete()
    close_journal()
    # Evidence is taken while the old worker is still blocked: a dead process writes nothing more.
    result = system.evidence(git=False)
    blocker.set()
    system.registry._executor.shutdown(wait=True)
    return result


# ================================================
# Conformance of each scenario
# ================================================


def test_authoring_lifecycle_conforms(system: System) -> None:
    assert_conforms(
        lifecycle(system),
        "machine:Allocation",
        "machine:Run",
        "machine:Attempt",
        "machine:Ree",
        "machine:Step",
        "boundary:dispatch",
        "run-success-is-backed",
        "dispatch-success-is-captured",
        "execution-was-dispatched",
        "allocation-ends",
        "ree-changes-through-operations",
        "reconciliation",
    )


def test_authoring_staleness_and_sealing_conform(system: System) -> None:
    result = authoring_and_sealing(system)
    assert_conforms(
        result,
        "sealed-without-stale-evidence",
        "source-receipts-come-from-acquisition",
        "evaluation-receipts-come-from-evaluation",
        "ree-changes-through-operations",
    )
    edges = result.coverage.transitions
    assert edges["Step"]["current -> stale"] >= 1
    assert edges["Step"]["stale -> current"] >= 1
    assert edges["Ree"]["draft -> sealed"] == 1


def test_boundary_faults_conform(system: System) -> None:
    result = faults_at_the_boundary(system)
    assert_conforms(result, "boundary:dispatch")
    assert result.coverage.messages["dispatch"]["unavailable"] == 1
    assert result.coverage.messages["dispatch"]["abandoned"] == 1


def test_cancellation_conforms(system: System) -> None:
    result = cancellation(system)
    assert_conforms(result, "machine:Run")
    assert result.coverage.transitions["Run"]["canceling -> canceled"] == 1


def test_capture_failure_conforms(system: System, monkeypatch: pytest.MonkeyPatch) -> None:
    result = capture_failure(system, monkeypatch)
    assert_conforms(result, "machine:Attempt")
    assert result.coverage.transitions["Attempt"]["completed -> capture_failed"] == 1


def test_provisioning_failure_conforms(system: System) -> None:
    result = provisioning_failure(system)
    assert verdicts(result)["machine:Allocation"] == "passed"
    assert result.coverage.transitions["Allocation"]["provisioning -> failed"] == 1


def test_an_interrupted_process_is_settled_by_its_successor(system: System) -> None:
    result = process_restart(system)
    assert verdicts(result)["machine:Run"] == "passed"
    assert verdicts(result)["reconciliation"] == "passed"
    assert result.coverage.transitions["Run"]["running -> failed"] == 1


def test_scenarios_cover_every_specified_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every declared edge is exercised by some scenario or listed in UNEXERCISED with a reason."""
    scenarios: list[Callable[[System], CheckResult]] = [
        lifecycle,
        authoring_and_sealing,
        faults_at_the_boundary,
        cancellation,
        provisioning_failure,
        process_restart,
        lambda system: capture_failure(system, monkeypatch),
    ]
    exercised: Counter[str] = Counter()
    for index, scenario in enumerate(scenarios):
        system = make_system(tmp_path / str(index), monkeypatch)
        try:
            result = scenario(system)
        finally:
            system.registry.shutdown()
            close_journal()
        for entity, edges in result.coverage.transitions.items():
            exercised.update({f"{entity} {edge}": count for edge, count in edges.items()})
    gaps = {edge for edge, count in exercised.items() if not count} - set(UNEXERCISED)
    assert gaps == set(), "specified edges no scenario exercises: add a scenario or list them in UNEXERCISED"
    stale = {edge for edge in UNEXERCISED if exercised[edge]}
    assert stale == set(), "exercised edges still listed as unexercised: remove them from UNEXERCISED"
    assert set(UNEXERCISED) <= set(exercised), "UNEXERCISED names edges the specification no longer declares"


# ================================================
# Violations the checker must catch in real code paths
# ================================================


def test_a_run_that_claims_success_without_an_attempt_is_a_violation(system: System) -> None:
    handle = system.provision()
    system.dispatch(handle, patch({"name": "real"}))
    phantom = ExecutionContext.new(ree_id="ree-1")
    run_id = system.start("evaluate", lambda ree_id, run: ActionResult(status="succeeded", context=phantom))
    assert system.settle(run_id) == "succeeded"
    result = verdicts(system.finish())
    assert result["run-success-is-backed"] == "violated"
    assert result["overall"] == "violated"


def test_an_attempt_nobody_dispatched_is_a_violation(system: System) -> None:
    handle = system.provision()
    system.dispatch(handle, patch({"name": "dispatched"}))
    run_command(patch({"name": "smuggled"}), log=lambda *_: None, context=ExecutionContext.new(ree_id="ree-1"))
    assert verdicts(system.finish())["execution-was-dispatched"] == "violated"


def test_an_unjournaled_state_change_is_a_violation(system: System) -> None:
    handle = system.provision()
    assert system.run(handle, patch({"name": "x"})) == "succeeded"
    system.registry.shutdown()
    close_journal()
    state = next((system.tmp / "runs").glob("*/state.json"))
    # A write path that bypasses the store, and with it the journal.
    state.write_text(state.read_text().replace('"status": "succeeded"', '"status": "failed"'))
    assert verdicts(system.evidence())["reconciliation"] == "violated"


def test_a_change_to_a_sealed_ree_outside_operations_is_a_violation(system: System) -> None:
    handle = system.provision()
    assert system.run(handle, SealReeCommand(), "seal") == "succeeded"
    (system.layout.root / "run.sh").write_text("#!/bin/sh\necho tampered\n")
    system.dispatch(handle, patch({"name": "refused"}))  # Its before-snapshot records the tampering.
    result = verdicts(system.finish())
    assert result["machine:Ree"] == "violated"
    assert result["ree-changes-through-operations"] == "violated"


def test_a_receipt_that_appears_without_its_operation_is_a_violation(system: System, monkeypatch) -> None:
    handle = system.provision()
    token = system.stage(ARCHIVE)
    upload = AcquireSourceArgs(mode="upload", upload_token=token, archive_name=ARCHIVE.name)
    with monkeypatch.context() as patched:
        # A bug that records the acquisition under another operation's name.
        patched.setattr(AcquireSourceCommand, "model_dump", lambda self, **kw: {"operation": "write_file", "args": {}})
        system.run(handle, AcquireSourceCommand(args=upload), "source")
    assert verdicts(system.finish())["source-receipts-come-from-acquisition"] == "violated"


def test_a_crashed_journal_leaves_cross_component_rules_inconclusive(system: System) -> None:
    handle = system.provision()
    system.dispatch(handle, patch({"name": "first"}))
    close_journal()
    journal_file = next((system.tmp / "journal").glob("api-*.ndjson"))
    lines = journal_file.read_text().splitlines()
    send = next(index for index, line in enumerate(lines) if '"kind":"send"' in line)
    journal_file.write_text("\n".join(lines[:send] + lines[send + 1 :]) + "\n")
    result = verdicts(system.evidence())
    assert result["evidence"] == "inconclusive"
    assert result["execution-was-dispatched"] == "inconclusive"


def test_unavailable_workbench_is_an_answered_dispatch(system: System) -> None:
    handle = system.provision()
    system.workbench.faults["patch_ree_definition"] = lambda: [UnavailableFrame(detail="gone")]
    with pytest.raises(WorkbenchUnavailableError):
        system.dispatch(handle, patch({"name": "unreachable"}))
    assert verdicts(system.finish())["boundary:dispatch"] == "passed"
