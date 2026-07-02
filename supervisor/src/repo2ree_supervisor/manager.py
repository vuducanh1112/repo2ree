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
    command_metric_attrs,
    current_traceparent,
    get_meter,
    get_tracer,
    record_command_status,
    record_ree_id,
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

    @classmethod
    def from_entry(cls, entry: WorkbenchEntry) -> WorkbenchHandle:
        return cls(
            ree_id=entry.ree_id,
            container_name=entry.container_name,
            volume_name=entry.volume_name,
            image=entry.image,
            agent_id=entry.agent_id,
        )

    @property
    def location(self) -> WorkbenchLocation:
        return WorkbenchLocation(container_name=self.container_name, volume_name=self.volume_name)


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
        # ``agent`` is the runtime seam: every touch of a container runtime goes
        # through it (an HTTP client to a co-located or remote agent). The manager
        # itself never speaks to Docker.
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
        connected agent". Either way we resolve it to the concrete agent the
        workbench lands on and pin the REE to *that*, so later ops route back to
        the same agent even once others join (an empty token could not).
        """
        with tracer.start_as_current_span("workbench.provision") as span:
            record_ree_id(span, ree_id)
            resolved_image = image or self._image
            # Resolve placement up front so the whole provision — and every later
            # op — targets one concrete agent rather than re-picking "any" each time.
            resolved_agent_id = self._agent.resolve_agent(agent_id)

            location = self._consume_lifecycle(self._agent.provision(resolved_agent_id, ree_id, resolved_image), log)
            if location is None:
                raise RuntimeError(f"agent provision for {ree_id} ended without a location")
            self._agent.exec_simple(
                resolved_agent_id,
                location.container_name,
                ["repo2ree-exec", "init-ree", "--ree-id", ree_id, "--name", name],
            )

            entry = WorkbenchEntry(
                ree_id=ree_id,
                container_name=location.container_name,
                volume_name=location.volume_name,
                image=resolved_image,
                agent_id=resolved_agent_id,
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
            # Reprovision from the REE's own image, not the manager default —
            # ``entry.image`` is empty only for pre-image-tracking entries, where
            # falling back to the default is the best we can do.
            handle = WorkbenchHandle.from_entry(entry)
            self._consume_lifecycle(
                self._agent.reprovision(handle.agent_id, ree_id, handle.location, entry.image or self._image), log
            )
            return handle

    def teardown(self, handle: WorkbenchHandle) -> None:
        """Stop + remove the container and its backing storage, unregister."""
        with tracer.start_as_current_span("workbench.teardown") as span:
            record_ree_id(span, handle.ree_id)
            self._agent.remove(handle.agent_id, handle.ree_id, handle.location)
            self._registry.unregister(handle.ree_id)

    def _consume_lifecycle(self, frames: Iterator[AgentFrame], log: LogSink | None) -> WorkbenchLocation | None:
        """Drain a provision/reprovision stream: forward logs, return the location.

        Raises on a terminal error/unavailable frame. Returns the location for a
        provision, or None for a reprovision (which ends with a ``done`` frame).
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
        if not self._agent.is_running(handle.agent_id, handle.container_name):
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
            record_command_status(span, result.status)
            return result

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
        for frame in self._agent.exec_action(handle.agent_id, handle.container_name, cmd_json, run_id, env):
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

        ``argv`` is a ``repo2ree-exec`` subcommand (e.g. ``get-ree``); the executor
        is prepended here. Set ``locked`` for queries that must observe a
        consistent snapshot — they take the per-REE lock so no mutating action
        runs concurrently. Plain reads leave it off and run unsynchronised.
        ``timeout`` bounds the exec itself; raise it for queries whose output
        scales with the REE (archives, large artifacts).
        """
        exec_argv = ["repo2ree-exec", *argv]
        if locked:
            with self._ree_lock(handle.ree_id):
                return self._agent.exec_query(handle.agent_id, handle.container_name, exec_argv, timeout=timeout)
        return self._agent.exec_query(handle.agent_id, handle.container_name, exec_argv, timeout=timeout)

    def get_ree_metadata(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-ree")
        return json.loads(raw)

    def get_workspace(self, handle: WorkbenchHandle) -> dict[str, Any]:
        raw = self.dispatch_query(handle, "get-workspace")
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
        # Zipping a sealed REE scales with its size; 30s is too tight for real
        # projects with data alongside the code.
        return self.dispatch_query(handle, "build-archive", locked=True, timeout=180)

    def list_all_metadata(self) -> list[dict[str, Any]]:
        """Return metadata for every registered workbench, skipping unreachable ones."""
        results = []
        for entry in self._registry.list_all():
            handle = WorkbenchHandle.from_entry(entry)
            if not self._agent.is_running(handle.agent_id, handle.container_name):
                continue
            with suppress(Exception):
                results.append(self.get_ree_metadata(handle))
        results.sort(key=lambda m: m.get("updatedAt", ""), reverse=True)
        return results

    def copy_to_workbench(self, handle: WorkbenchHandle, host_path: str, container_path: str) -> None:
        """Copy a local file into the workbench container.

        ``host_path`` need only exist on the control plane: the agent (which may
        be on a host that shares no filesystem with us) receives the bytes streamed
        in bounded chunks, so neither side buffers the whole file (see WsAgentClient)."""
        self._agent.copy_in(handle.agent_id, handle.container_name, host_path, container_path)
