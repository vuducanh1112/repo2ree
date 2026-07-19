"""Control-plane workbench lifecycle and command dispatch.

Each REE has exactly one always-on workbench with its volume mounted at /ree.
The manager provisions new workbenches, dispatches typed Commands, and issues
cheap queries/mutations — but it does none of the runtime I/O itself. Every
touch of the underlying runtime goes through an ``AgentClient``, so the
manager's responsibilities are purely control-plane: the registry of
REE→location, per-REE locking, tracing, metrics, and the semantic query
wrappers.

Streaming: dispatch_action consumes the agent's ``AgentFrame`` stream, forwards
log/span frames as they arrive, and returns the terminal result frame's
``ActionResult``.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from repo2ree_protocol.agent import (
    AgentFrame,
    ErrorFrame,
    LocationFrame,
    LogFrame,
    ResultFrame,
    SpanFrame,
    UnavailableFrame,
    WorkbenchLocation,
)
from repo2ree_protocol.command import Command
from repo2ree_protocol.log import LogSink
from repo2ree_protocol.result import ActionResult
from repo2ree_protocol.tracing import (
    CommandSpanAttrs,
    SpanSink,
    WorkbenchSpanAttrs,
    command_metric_attrs,
    current_traceparent,
    get_meter,
    get_tracer,
    record_command_status,
    record_exit_code,
    record_ree_id,
    record_span_facts,
)
from repo2ree_supervisor.client import AgentClient, WorkbenchUnavailableError, raise_for_terminal_error
from repo2ree_supervisor.registry import WorkbenchEntry, WorkbenchRegistry

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
_reprovision_counter = _meter.create_counter(
    "workbench.reprovision",
    description="Number of workbench container reprovisioning operations.",
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
    container_name: str
    volume_name: str
    image: str = ""
    # The agent this REE is pinned to; every op on this handle routes to it.
    agent_id: str = ""
    # The bench's executor entry point, as minted by the agent (see
    # WorkbenchLocation.exec_path). Carried, never interpreted.
    exec_path: str = "repo2ree-exec"

    @classmethod
    def from_entry(cls, entry: WorkbenchEntry) -> WorkbenchHandle:
        return cls(
            ree_id=entry.ree_id,
            container_name=entry.container_name,
            volume_name=entry.volume_name,
            image=entry.image,
            agent_id=entry.agent_id,
            exec_path=entry.exec_path,
        )

    @property
    def location(self) -> WorkbenchLocation:
        return WorkbenchLocation(
            container_name=self.container_name, volume_name=self.volume_name, exec_path=self.exec_path
        )


# ================================================
# Manager
# ================================================


class WorkbenchManager:
    def __init__(
        self,
        registry: WorkbenchRegistry,
        workbench_image: str,
        agent: AgentClient,
        span_sink: SpanSink | None = None,
    ):
        self._registry = registry
        self._image = workbench_image
        self._span_sink = span_sink
        self._agent = agent
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
        image: str | None = None,
        agent_id: str = "",
    ) -> WorkbenchHandle:
        """Create backing storage + workbench, initialise the REE, register handle.

        ``image`` overrides the manager's default workbench image for this REE.
        ``agent_id`` places the workbench on a specific agent; empty means "any
        connected agent", resolved up front to a concrete id and pinned (see
        ``AgentClient.resolve_agent``).
        """
        with tracer.start_as_current_span("workbench.provision") as span:
            record_ree_id(span, ree_id)
            resolved_image = image or self._image
            resolved_agent_id = self._agent.resolve_agent(agent_id)
            WorkbenchSpanAttrs(image=resolved_image, agent_id=resolved_agent_id).apply(span)

            location = self._consume_lifecycle(self._agent.provision(resolved_agent_id, ree_id, resolved_image), log)
            if location is None:
                raise RuntimeError(f"agent provision for {ree_id} ended without a location")
            WorkbenchSpanAttrs(container=location.container_name).apply(span)
            self._agent.exec_simple(
                resolved_agent_id,
                location,
                ["init-ree", "--ree-id", ree_id, "--name", name],
            )

            entry = WorkbenchEntry(
                ree_id=ree_id,
                container_name=location.container_name,
                volume_name=location.volume_name,
                image=resolved_image,
                agent_id=resolved_agent_id,
                exec_path=location.exec_path,
            )
            self._registry.register(entry)
            return WorkbenchHandle.from_entry(entry)

    def reprovision(self, ree_id: str, log: LogSink | None = None) -> WorkbenchHandle:
        """Replace the container with a fresh one from the same image, keeping backing storage."""
        _reprovision_counter.add(1)
        with tracer.start_as_current_span("workbench.reprovision") as span:
            record_ree_id(span, ree_id)
            entry = self._registry.lookup(ree_id)
            if entry is None:
                raise KeyError(f"no workbench registered for {ree_id}")
            # Reprovision from the REE's own image, not the manager default.
            handle = WorkbenchHandle.from_entry(entry)
            WorkbenchSpanAttrs(
                container=handle.container_name,
                image=entry.image,
                agent_id=handle.agent_id,
            ).apply(span)
            location = self._consume_lifecycle(
                self._agent.reprovision(handle.agent_id, ree_id, handle.location, entry.image), log
            )
            if location is not None and location != handle.location:
                # The replacement bench re-decided how it is driven (e.g. its
                # executor entry point); persist the fresh location.
                entry = WorkbenchEntry(
                    ree_id=ree_id,
                    container_name=location.container_name,
                    volume_name=location.volume_name,
                    image=entry.image,
                    agent_id=entry.agent_id,
                    exec_path=location.exec_path,
                )
                self._registry.register(entry)
                handle = WorkbenchHandle.from_entry(entry)
            return handle

    def teardown(self, handle: WorkbenchHandle) -> None:
        """Stop + remove the container and its backing storage, unregister."""
        with tracer.start_as_current_span("workbench.teardown") as span:
            record_ree_id(span, handle.ree_id)
            WorkbenchSpanAttrs(container=handle.container_name, agent_id=handle.agent_id).apply(span)
            self._agent.remove(handle.agent_id, handle.ree_id, handle.location)
            self._registry.unregister(handle.ree_id)
            # Drop the per-REE lock with the REE, or the map grows for the
            # process lifetime. A dispatch still holding it keeps its reference;
            # the workbench it guards is gone either way.
            with self._ree_locks_lock:
                self._ree_locks.pop(handle.ree_id, None)

    def _consume_lifecycle(self, frames: Iterator[AgentFrame], log: LogSink | None) -> WorkbenchLocation | None:
        """Drain a provision/reprovision stream: forward logs, return the location.

        Raises on a terminal error/unavailable frame. Both provision and
        reprovision end with a ``location`` frame; None only if the stream ended
        without one (an older agent's reprovision, which ends with ``done``).
        """
        location: WorkbenchLocation | None = None
        for frame in frames:
            if isinstance(frame, LogFrame):
                if log is not None:
                    log(frame.stream, frame.level, frame.message)
            elif isinstance(frame, LocationFrame):
                location = frame.location
            else:
                raise_for_terminal_error(frame)
        return location

    def is_registered(self, ree_id: str) -> bool:
        """True if a workbench is registered for ree_id (regardless of run state)."""
        return self._registry.lookup(ree_id) is not None

    def lookup(self, ree_id: str) -> WorkbenchHandle | None:
        """Return the handle for ree_id, or None if not registered or not running."""
        entry = self._registry.lookup(ree_id)
        if entry is None:
            return None
        handle = WorkbenchHandle.from_entry(entry)
        if not self._agent.is_running(handle.agent_id, handle.location):
            logger.warning(
                "workbench container %s not running for %s — returning None",
                handle.container_name,
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
                container=handle.container_name,
                image=self.image_for(handle),
                agent_id=handle.agent_id,
            ).apply(span)
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
            record_command_status(span, result.status)
            return result

    def cancel_run(self, handle: WorkbenchHandle, run_id: str) -> None:
        """Ask the workbench executor to stop a running action.

        This deliberately does not take the per-REE dispatch lock: the command we
        are canceling is usually the one holding that lock.
        """
        self._agent.cancel_run(handle.agent_id, handle.location, run_id)

    def _dispatch_action_locked(
        self,
        handle: WorkbenchHandle,
        cmd: Command,
        run_id: str,
        log: LogSink,
    ) -> ActionResult:
        cmd_json = cmd.model_dump_json()

        # Carry the active trace context into the executor so its spans hang
        # under this dispatch span. When the API injected a span_sink, ask the
        # executor to relay its spans back over stderr (it has no path to the
        # collector itself); we forward them after the command completes.
        env: dict[str, str] = {}
        traceparent = current_traceparent()
        if traceparent:
            env["TRACEPARENT"] = traceparent
        if self._span_sink is not None:
            env["TRACE_RELAY"] = "1"

        # Consume the agent's frame stream live: forward log frames to the sink
        # and relayed span frames to the span_sink as they arrive (not buffered to
        # the end) so a command that hangs or gets killed still ships what it
        # emitted before stalling — the case a trace is most useful. The span_sink
        # is non-blocking (it enqueues for a background forwarder), so export never
        # sits on this loop, the per-REE lock, or the measured execute window.
        result: ActionResult | None = None
        for frame in self._agent.exec_action(handle.agent_id, handle.location, cmd_json, run_id, env):
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
            # Stream ended without a terminal result frame.
            return ActionResult(status="failed", exit_code=1)
        return result

    # ------------------------------------------------
    # Query / mutation dispatch
    # ------------------------------------------------

    def dispatch_query(self, handle: WorkbenchHandle, *argv: str, locked: bool = False, timeout: int = 30) -> bytes:
        """Run a read-only CLI subcommand and return its stdout bytes.

        ``argv`` is a ``repo2ree-exec`` subcommand (e.g. ``get-ree``); the agent's
        runtime prepends the bench's executor entry point. Set ``locked`` for
        queries that must observe a consistent snapshot — they take the per-REE
        lock so no mutating action runs concurrently. Plain reads leave it off
        and run unsynchronised. ``timeout`` bounds the exec itself; raise it for
        queries whose output scales with the REE (archives, large artifacts).
        """
        exec_argv = list(argv)
        if locked:
            with self._ree_lock(handle.ree_id):
                return self._agent.exec_query(handle.agent_id, handle.location, exec_argv, timeout=timeout)
        return self._agent.exec_query(handle.agent_id, handle.location, exec_argv, timeout=timeout)

    def dispatch_query_stream(
        self, handle: WorkbenchHandle, *argv: str, locked: bool = False, timeout: int = 30
    ) -> Iterator[bytes]:
        """Run a read-only CLI subcommand and stream stdout bytes."""
        exec_argv = list(argv)

        def stream() -> Iterator[bytes]:
            if locked:
                with self._ree_lock(handle.ree_id):
                    yield from self._agent.exec_query_stream(
                        handle.agent_id, handle.location, exec_argv, timeout=timeout
                    )
                return
            yield from self._agent.exec_query_stream(handle.agent_id, handle.location, exec_argv, timeout=timeout)

        return stream()

    def get_ree_metadata(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-ree")
        return json.loads(raw)

    def get_workspace(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-workspace")
        return json.loads(raw)

    def get_workspace_state(self, handle: WorkbenchHandle) -> dict[str, Any]:
        """Return workspace state without embedding text file contents."""
        raw = self.dispatch_query(handle, "get-workspace", "--summary")
        return json.loads(raw)

    def get_scorecard(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-scorecard")
        return json.loads(raw)

    def image_for(self, handle: WorkbenchHandle) -> str:
        """The image this REE's workbench runs, falling back to the manager default."""
        return handle.image or self._image

    def read_file_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        return self.dispatch_query(handle, "read-file", "--path", path)

    def read_artifact_bytes(self, handle: WorkbenchHandle, path: str) -> bytes:
        # Artifacts (run outputs) can be large; give the read room to stream.
        return self.dispatch_query(handle, "read-artifact", "--path", path, timeout=120)

    def build_archive(self, handle: WorkbenchHandle) -> bytes:
        return b"".join(self.build_archive_stream(handle))

    def build_archive_stream(self, handle: WorkbenchHandle) -> Iterator[bytes]:
        # Zipping a sealed REE scales with its size, hence the generous timeout;
        # the per-REE lock stays held until the caller finishes consuming.
        return self.dispatch_query_stream(handle, "build-archive", locked=True, timeout=180)

    def list_all_metadata(self) -> list[dict[str, Any]]:
        """Return metadata for every registered workbench, skipping unreachable ones."""
        results = []
        for entry in self._registry.list_all():
            handle = WorkbenchHandle.from_entry(entry)
            if not self._agent.is_running(handle.agent_id, handle.location):
                continue
            with suppress(Exception):
                results.append(self.get_ree_metadata(handle))
        results.sort(key=lambda m: m.get("updated_at", ""), reverse=True)
        return results

    def copy_to_workbench(self, handle: WorkbenchHandle, host_path: str, container_path: str) -> None:
        """Copy a control-plane-local file into the workbench container.

        ``host_path`` need only exist here; the agent may share no filesystem
        with us (see ``AgentClient.copy_in``)."""
        self._agent.copy_in(handle.agent_id, handle.location, host_path, container_path)
