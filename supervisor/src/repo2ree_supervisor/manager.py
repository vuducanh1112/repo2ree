"""Control-plane workbench lifecycle and command dispatch.

Each REE has exactly one always-on workbench with its volume mounted at /ree.
The manager provisions new workbenches, dispatches typed Commands, and issues
cheap queries/mutations — but it does none of the runtime I/O itself. Every
touch of the underlying runtime goes through the split client seams, so the
manager's responsibilities are purely control-plane: the registry of
REE→reference, per-REE locking, tracing, metrics, and the semantic query
wrappers.

Streaming: dispatch_action consumes the workbench's ``Frame`` stream, forwards
log/span frames as they arrive, and returns the terminal result frame's
``ActionResult``.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from repo2ree_protocol.allocation import AllocationRecord, AllocationRequest, AllocationState, WorkbenchProfile
from repo2ree_protocol.command import Command
from repo2ree_protocol.frames import (
    AllocationStatusFrame,
    ErrorFrame,
    Frame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
)
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.substrate import ObservedCapabilities
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    SpanSink,
    WorkbenchSpanAttrs,
    command_metric_attrs,
    get_meter,
    get_tracer,
    record_command_status,
    record_exit_code,
    record_failure,
    record_ree_id,
    record_span_facts,
)
from repo2ree_supervisor.allocation_store import AllocationStore
from repo2ree_supervisor.client import (
    ProviderClient,
    WorkbenchClient,
    WorkbenchUnavailableError,
    raise_for_terminal_error,
)
from repo2ree_supervisor.enrollment import EnrollmentRegistry
from repo2ree_supervisor.matching import check_compatibility, describe_issues

__all__ = [
    "WorkbenchHandle",
    "WorkbenchManager",
    "WorkbenchUnavailableError",
]

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)

# ================================================
# Metrics
# ================================================

_container_gone_counter = _meter.create_counter(
    "workbench.container_gone",
    description="Number of docker exec failures due to container gone or stopping.",
)
_exec_duration = _meter.create_histogram(
    "workbench.execute_duration_seconds",
    description="Wall-clock duration of workbench command execution (lock held, docker exec running).",
    unit="s",
)
_lock_wait_duration = _meter.create_histogram(
    "workbench.lock_wait_seconds",
    description="Time a dispatch blocked on the per-REE lock before execution (another run in progress).",
    unit="s",
)


# ================================================
# Utility Classes
# ================================================


@dataclass(frozen=True)
class WorkbenchHandle:
    ree_id: str
    # The workbench this REE is pinned to; every op on this handle routes to it.
    workbench_id: str = ""
    allocation_id: str = ""
    provider_id: str = ""
    mode: str = "provider_managed"
    location_id: str = ""
    profile_id: str = ""
    profile_revision: str = ""
    observation: ObservedCapabilities | None = None

    @classmethod
    def from_record(cls, record: AllocationRecord) -> WorkbenchHandle:
        request = record.request
        return cls(
            ree_id=request.ree_id,
            workbench_id=record.workbench_id or "",
            allocation_id=request.allocation_id,
            provider_id=record.provider_id or "",
            mode="provider_managed" if record.provider_id else "external",
            location_id=request.location_id,
            profile_id=request.profile_id,
            profile_revision=request.profile_revision,
            observation=record.observation,
        )


# ================================================
# Manager
# ================================================


class WorkbenchManager:
    def __init__(
        self,
        registry: AllocationStore,
        provider: ProviderClient,
        workbench: WorkbenchClient,
        enrollment: EnrollmentRegistry | None = None,
        span_sink: SpanSink | None = None,
    ):
        self._registry = registry
        self._span_sink = span_sink
        # The manager's two roles, spoken to through separate seams: the
        # provider obtains and releases environments, the workbench executes
        # inside one. Today's composition passes the same combined-workbench client
        # for both; the split constructor is what lets that change without
        # touching any method below.
        self._provider = provider
        self._workbench = workbench
        self._enrollment = enrollment or EnrollmentRegistry()
        self._ree_locks: dict[str, threading.Lock] = {}
        self._ree_locks_lock = threading.Lock()

    def _ree_lock(self, ree_id: str) -> threading.Lock:
        with self._ree_locks_lock:
            if ree_id not in self._ree_locks:
                self._ree_locks[ree_id] = threading.Lock()
            return self._ree_locks[ree_id]

    # ------------------------------------------------
    # Lifecycle
    # ------------------------------------------------

    def provision(
        self,
        ree_id: str,
        name: str,
        log: LogSink | None = None,
        location_id: str = "",
        profile_id: str = "standard",
    ) -> WorkbenchHandle:
        """Allocate exactly the selected profile, validate it, and initialise the REE."""
        with self._ree_lock(ree_id), tracer.start_as_current_span("workbench.provision") as span:
            record_ree_id(span, ree_id)
            allocation_id = f"alloc-{uuid4().hex}"
            provider_id, profile = self._provider.resolve_profile(location_id, profile_id)
            workbench_id = f"wb-{uuid4().hex}"
            request = AllocationRequest(
                allocation_id=allocation_id,
                ree_id=ree_id,
                location_id=profile.location_id,
                profile_id=profile.id,
                profile_revision=profile.revision,
            )
            self._registry.create(request, provider_id=provider_id, workbench_id=workbench_id)
            self._registry.update(allocation_id, AllocationState.PROVISIONING)
            enrollment_token = secrets.token_urlsafe(32)
            self._enrollment.expect(allocation_id, workbench_id, enrollment_token)
            WorkbenchSpanAttrs(workbench_id=workbench_id).apply(span)
            try:
                self._consume_lifecycle(
                    self._provider.ensure(
                        provider_id,
                        request,
                        workbench_id,
                        enrollment_token,
                    ),
                    log,
                )
                self._registry.update(allocation_id, AllocationState.WAITING_FOR_WORKBENCH)
                self._workbench.wait_for_workbench(workbench_id)
                return self._validate_assign_initialise(request, profile, workbench_id, name)
            except BaseException as exc:
                self._enrollment.discard(allocation_id)
                record = self._registry.get(allocation_id)
                if record and record.state not in {AllocationState.INCOMPATIBLE, AllocationState.FAILED}:
                    self._registry.update(allocation_id, AllocationState.FAILED, detail=str(exc))
                self._provider.release_best_effort(provider_id, allocation_id)
                raise

    def reserve_external(self, ree_id: str, name: str, location_id: str, profile_id: str) -> WorkbenchHandle:
        """Assign the exact externally managed location/profile selected by the user."""
        with self._ree_lock(ree_id), tracer.start_as_current_span("workbench.reserve_external"):
            allocation_id = f"alloc-{uuid4().hex}"
            workbench_id, profile = self._workbench.reserve_external(allocation_id, location_id, profile_id)
            request = AllocationRequest(
                allocation_id=allocation_id,
                ree_id=ree_id,
                location_id=profile.location_id,
                profile_id=profile.id,
                profile_revision=profile.revision,
            )
            self._registry.create(request, provider_id=None, workbench_id=workbench_id)
            self._registry.update(allocation_id, AllocationState.WAITING_FOR_WORKBENCH)
            try:
                return self._validate_assign_initialise(request, profile, workbench_id, name)
            except BaseException as exc:
                record = self._registry.get(allocation_id)
                if record and record.state not in {AllocationState.INCOMPATIBLE, AllocationState.FAILED}:
                    self._registry.update(allocation_id, AllocationState.FAILED, detail=str(exc))
                raise

    def _validate_assign_initialise(
        self, request: AllocationRequest, profile: WorkbenchProfile, workbench_id: str, name: str
    ) -> WorkbenchHandle:
        observation = self._workbench.observation(workbench_id)
        issues = check_compatibility(profile, observation)
        if issues:
            self._registry.update(
                request.allocation_id,
                AllocationState.INCOMPATIBLE,
                observation=observation,
                incompatibilities=issues,
                detail="workbench does not satisfy the selected profile",
            )
            raise RuntimeError("workbench is incompatible: " + describe_issues(issues))
        self._registry.update(request.allocation_id, AllocationState.READY, observation=observation)
        self._workbench.assign(workbench_id, request)
        self._workbench.exec_simple(workbench_id, ["init-ree", "--name", name])
        record = self._registry.update(request.allocation_id, AllocationState.ASSIGNED)
        return WorkbenchHandle.from_record(record)

    def teardown(self, handle: WorkbenchHandle) -> None:
        """Stop + remove the container and its backing storage, unregister."""
        with self._ree_lock(handle.ree_id), tracer.start_as_current_span("workbench.teardown") as span:
            record_ree_id(span, handle.ree_id)
            WorkbenchSpanAttrs(workbench_id=handle.workbench_id).apply(span)
            # Let the resident process finish in-flight executors and exit before
            # the provider destroys the environment. Removal remains the final
            # authority and still runs if the execution connection is already gone.
            with suppress(WorkbenchUnavailableError):
                self._workbench.drain(handle.workbench_id)
            self._registry.update(handle.allocation_id, AllocationState.DRAINING)
            if handle.mode == "provider_managed":
                self._provider.release(handle.provider_id, handle.allocation_id)
                self._enrollment.discard(handle.allocation_id)
            self._registry.update(handle.allocation_id, AllocationState.RELEASED)
            self._registry.remove_placement(handle.ree_id)

    def _consume_lifecycle(self, frames: Iterator[Frame], log: LogSink | None) -> AllocationStatusFrame:
        status: AllocationStatusFrame | None = None
        for frame in frames:
            if isinstance(frame, LogFrame):
                if log is not None:
                    log(frame.stream, frame.level, frame.message)
            elif isinstance(frame, AllocationStatusFrame):
                status = frame
            else:
                raise_for_terminal_error(frame)
        if status is None:
            raise RuntimeError("provider ensure ended without allocation status")
        return status

    def is_registered(self, ree_id: str) -> bool:
        """True if a workbench is registered for ree_id (regardless of run state)."""
        record = self._registry.for_ree(ree_id)
        return record is not None and record.state == AllocationState.ASSIGNED

    def lookup(self, ree_id: str) -> WorkbenchHandle | None:
        """Return the handle for ree_id, or None if not registered or not running."""
        record = self._registry.for_ree(ree_id)
        if record is None or record.state != AllocationState.ASSIGNED:
            return None
        handle = WorkbenchHandle.from_record(record)
        running = (
            self._provider.is_running(handle.provider_id, handle.allocation_id)
            if handle.mode == "provider_managed"
            else self._workbench.is_connected(handle.workbench_id)
        )
        if not running:
            logger.warning(
                "workbench allocation %s not running for %s — returning None",
                handle.allocation_id,
                ree_id,
            )
            return None
        return handle

    # ------------------------------------------------
    # Action dispatch
    # ------------------------------------------------

    def dispatch_action(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
    ) -> ActionResult:
        """Run a typed Command inside the workbench; stream logs to log."""
        with tracer.start_as_current_span("workbench.dispatch_action") as span:
            CommandSpanAttrs(operation=str(cmd.operation), run_id=run_id, ree_id=handle.ree_id).apply(span)
            WorkbenchSpanAttrs(
                workbench_id=handle.workbench_id,
            ).apply(span)
            # The whole command as dispatched — envelope and args — recorded
            # before it runs, for the reason core's own dispatch records its
            # inputs first: a command that is killed or times out still carries
            # what it was asked to do. Without this the span reports only what
            # came back, which is half a wide event.
            #
            # Namespaced ``cmd`` rather than ``arg`` because it is the whole
            # envelope, not the argument object a handler receives; core's
            # ``repo2ree.arg.*`` remains the inner view of the same call.
            record_span_facts(span, cmd.model_dump(), namespace="cmd")
            # Time spent blocked here is per-REE lock contention (another run in
            # progress); record it on acquisition so wait is a first-class metric
            # rather than something inferred from the dispatch/execute span gap.
            _lock_t0 = time.monotonic()
            with self._ree_lock(handle.ree_id):
                _lock_wait_duration.record(
                    time.monotonic() - _lock_t0,
                    command_metric_attrs(str(cmd.operation)),
                )
                with tracer.start_as_current_span("workbench.execute"):
                    _t0 = time.monotonic()
                    result = self._dispatch_action_locked(handle, cmd, run_id, log)
                    _exec_duration.record(
                        time.monotonic() - _t0,
                        command_metric_attrs(str(cmd.operation), status=result.status),
                    )
            # Mirror the executor's wide event host-side: the command span's
            # outputs travel over the best-effort span relay, so this dispatch
            # span is the copy guaranteed to reach the collector.
            record_exit_code(span, result.exit_code)
            record_span_facts(span, result.outputs, namespace="output")
            record_failure(span, result.failure)
            record_command_status(span, result.status)
            return result

    def cancel_run(self, handle: WorkbenchHandle, run_id: str) -> None:
        """Ask the workbench executor to stop a running action.

        This deliberately does not take the per-REE dispatch lock: the command we
        are canceling is usually the one holding that lock.
        """
        self._workbench.cancel_run(handle.workbench_id, run_id)

    def _dispatch_action_locked(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
    ) -> ActionResult:
        cmd_json = cmd.model_dump_json()

        # No TRACEPARENT here on purpose. The workbench injects it at the hop that
        # actually spawns the executor, so a context set from this span would be
        # overwritten one layer down — two propagation points with the later
        # silently winning. What this span does own is asking for the relay:
        # when the API injected a span_sink the executor should stream its spans
        # back over stderr, having no path to the collector itself.
        env: dict[str, str] = {}
        if self._span_sink is not None:
            env["TRACE_RELAY"] = "1"

        # Consume the workbench's frame stream live: forward log frames to the sink
        # and relayed span frames to the span_sink as they arrive (not buffered to
        # the end) so a command that hangs or gets killed still ships what it
        # emitted before stalling — the case a trace is most useful. The span_sink
        # is non-blocking (it enqueues for a background forwarder), so export never
        # sits on this loop, the per-REE lock, or the measured execute window.
        result: ActionResult | None = None
        for frame in self._workbench.exec_action(handle.workbench_id, cmd_json, run_id, env):
            if isinstance(frame, LogFrame):
                log(frame.stream, frame.level, frame.message)
            elif isinstance(frame, SpanFrame):
                if self._span_sink is not None:
                    self._span_sink([frame.payload])
            elif isinstance(frame, ResultFrame):
                result = frame.result
            elif isinstance(frame, UnavailableFrame):
                _container_gone_counter.add(1, command_metric_attrs(str(cmd.operation)))
                raise WorkbenchUnavailableError(frame.detail)
            elif isinstance(frame, ErrorFrame):
                raise RuntimeError(frame.detail)

        if result is None:
            # Stream ended without a terminal result frame: the executor exited
            # or the connection dropped before reporting an outcome.
            return ActionResult.failed(
                "internal",
                f"{cmd.operation} ended without a result",
                origin="supervisor",
                retryable=True,
            )
        return result

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: WorkbenchHandle, *argv: str, locked: bool = False, timeout: int = 30) -> bytes:
        """Run a read-only CLI subcommand and return its stdout bytes.

        ``argv`` is a ``repo2ree-exec`` subcommand (e.g. ``get-ree-manifest``);
        the workbench service prepends the bench's executor entry point. Set
        ``locked`` for
        queries that must observe a consistent snapshot — they take the per-REE
        lock so no mutating action runs concurrently. Plain reads leave it off
        and run unsynchronised. ``timeout`` bounds the exec itself; raise it for
        queries whose output scales with the REE (archives, large artifacts).
        """
        exec_argv = list(argv)
        if locked:
            with self._ree_lock(handle.ree_id):
                return self._workbench.exec_query(handle.workbench_id, exec_argv, timeout=timeout)
        return self._workbench.exec_query(handle.workbench_id, exec_argv, timeout=timeout)

    def dispatch_query_stream(
        self, handle: WorkbenchHandle, *argv: str, locked: bool = False, timeout: int = 30
    ) -> Iterator[bytes]:
        """Run a read-only CLI subcommand and stream stdout bytes."""
        exec_argv = list(argv)

        def query() -> Iterator[bytes]:
            return self._workbench.exec_query_stream(handle.workbench_id, exec_argv, timeout=timeout)

        def stream() -> Iterator[bytes]:
            if locked:
                with self._ree_lock(handle.ree_id):
                    yield from query()
                return
            yield from query()

        return stream()

    def _query_json(self, handle: WorkbenchHandle, *argv: str) -> dict[str, Any]:
        """Run a read-only CLI subcommand and parse its stdout as a JSON object.

        The one place the workbench's untyped JSON becomes a typed value, so the
        ``Any`` that ``json.loads`` returns is narrowed once rather than at each
        of the five call sites below.
        """
        parsed: dict[str, Any] = json.loads(self.dispatch_query(handle, *argv))
        return parsed

    def get_ree_manifest(self, handle: WorkbenchHandle) -> dict[str, Any]:
        return self._query_json(handle, "get-ree-manifest")

    def get_ree_document(self, handle: WorkbenchHandle) -> dict[str, Any]:
        return self._with_handle(handle, self._query_json(handle, "get-ree-document"))

    def get_ree_state(self, handle: WorkbenchHandle) -> dict[str, Any]:
        """Return composed REE state without embedding text file contents."""
        return self._with_handle(handle, self._query_json(handle, "get-ree-document", "--summary"))

    @staticmethod
    def _with_handle(handle: WorkbenchHandle, document: dict[str, Any]) -> dict[str, Any]:
        """Add the control-plane handle the workbench has no way to know.

        ``ree_id`` names a registry entry and the container and volume built
        from it — all of it host-side. A workbench sees only its own volume,
        mounted at the same ``/ree`` in every REE, so the document it returns
        carries no identity of its own and this is where one is supplied.
        """
        document["ree_id"] = handle.ree_id
        return document

    def get_reviews(self, handle: WorkbenchHandle) -> dict[str, Any]:
        return self._query_json(handle, "get-reviews")

    def read_ree_file_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        # REE files can include large runtime and result artifacts.
        return self.dispatch_query(handle, "read-ree-file", "--path", path, timeout=120)

    def build_archive(self, handle: WorkbenchHandle) -> bytes:
        return b"".join(self.build_archive_stream(handle))

    def build_archive_stream(self, handle: WorkbenchHandle) -> Iterator[bytes]:
        # Zipping a sealed REE scales with its size, hence the generous timeout;
        # the per-REE lock stays held until the caller finishes consuming.
        return self.dispatch_query_stream(handle, "build-archive", locked=True, timeout=180)

    def list_all_manifests(self) -> list[tuple[WorkbenchHandle, dict[str, Any]]]:
        """Every reachable workbench, paired with its REE document as it arrived.

        The document stays unparsed on purpose: the "Supervisor speaks only
        protocol" contract forbids this package from knowing the domain shape,
        so the control plane, which ships with core, parses it instead.

        Unreachable or unreadable workbenches are skipped rather than raised:
        this backs a listing, and one sick bench must not empty it.
        """
        manifests: list[tuple[WorkbenchHandle, dict[str, Any]]] = []
        for record in self._registry.list():
            if record.state != AllocationState.ASSIGNED:
                continue
            handle = WorkbenchHandle.from_record(record)
            running = (
                self._provider.is_running(handle.provider_id, handle.allocation_id)
                if handle.mode == "provider_managed"
                else self._workbench.is_connected(handle.workbench_id)
            )
            if not running:
                continue
            with suppress(Exception):
                manifests.append((handle, self.get_ree_manifest(handle)))
        return manifests

    def copy_to_workbench(self, handle: WorkbenchHandle, host_path: str, workbench_path: str) -> None:
        """Copy a control-plane-local file into the workbench.

        ``host_path`` need only exist here; the workbench may share no filesystem
        with us (see ``WorkbenchClient.copy_in``)."""
        self._workbench.copy_in(handle.workbench_id, host_path, workbench_path)
