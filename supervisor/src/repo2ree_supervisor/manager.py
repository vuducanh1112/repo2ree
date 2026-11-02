"""Control-plane workbench lifecycle: provider-managed and external allocations.

The manager sets workbenches up and tears them down, keeps the allocation each REE is
served by, and knows when a provider reports a bench gone. Commands and queries go
through its ``dispatcher`` (``repo2ree_supervisor.dispatcher``) under the same per-REE
locks, so setting up or tearing down an REE never overlaps a command on it.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Iterator
from contextlib import suppress
from uuid import uuid4

from pydantic import ValidationError

from repo2ree_protocol.allocation import AllocationRequest, AllocationState
from repo2ree_protocol.frames import (
    AllocationStatusFrame,
    Frame,
    LogFrame,
    LogSink,
)
from repo2ree_ree.model import Ree
from repo2ree_supervisor.allocation_state import IllegalTransitionError
from repo2ree_supervisor.allocation_store import AllocationStore
from repo2ree_supervisor.client import (
    ProviderClient,
    WorkbenchClient,
    WorkbenchUnavailableError,
    raise_for_terminal_error,
)
from repo2ree_supervisor.dispatcher import CommandDispatcher
from repo2ree_supervisor.enrollment import EnrollmentRegistry
from repo2ree_supervisor.handle import WorkbenchHandle
from repo2ree_supervisor.locks import ReeLocks
from repo2ree_telemetry.bootstrap import get_meter, get_tracer
from repo2ree_telemetry.relay import SpanSink
from repo2ree_telemetry.spans import (
    WorkbenchSpanAttrs,
    record_ree_id,
)

__all__ = [
    "WorkbenchHandle",
    "WorkbenchManager",
    "WorkbenchUnavailableError",
]

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
_meter = get_meter(__name__)


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
        self._ree_lock = ReeLocks()
        # Commands and queries go through the dispatcher, under the same per-REE locks; a bench
        # that stops answering one is asked about here, where allocations are known.
        self.dispatcher = CommandDispatcher(workbench, self._ree_lock, span_sink, on_unavailable=self._notice_lost)

    # ------------------------------------------------
    # Lifecycle
    # ------------------------------------------------

    def provision(
        self,
        ree_id: str,
        name: str,
        log: LogSink | None = None,
        location_id: str = "",
        image: str = "",
    ) -> WorkbenchHandle:
        """Allocate a bench from the selected location and image, and initialise the REE."""
        with self._ree_lock(ree_id), tracer.start_as_current_span("workbench.provision") as span:
            record_ree_id(span, ree_id)
            allocation_id = f"alloc-{uuid4().hex}"
            provider_id, image_ref = self._provider.resolve_location(location_id, image)
            workbench_id = f"wb-{uuid4().hex}"
            request = AllocationRequest(
                allocation_id=allocation_id,
                ree_id=ree_id,
                location_id=location_id,
                image=image_ref,
            )
            self._registry.create(request, provider_id=provider_id, workbench_id=workbench_id)
            self._registry.update(allocation_id, AllocationState.PROVISIONING)
            enrollment_token = secrets.token_urlsafe(32)
            self._enrollment.expect(allocation_id, workbench_id, enrollment_token)
            WorkbenchSpanAttrs(workbench_id=workbench_id).apply(span)
            try:
                status = self._consume_lifecycle(
                    self._provider.ensure(
                        provider_id,
                        request,
                        workbench_id,
                        enrollment_token,
                    ),
                    log,
                )
                # The provider is the only one that can say which image the
                # bench actually came up on: the request named a ref, and a tag
                # moves. Recording it here is what lets the bench readout — and
                # anything later reading this REE's provenance — cite a digest.
                self._registry.update(
                    allocation_id,
                    AllocationState.WAITING_FOR_WORKBENCH,
                    resolved_image=status.resolved_image or None,
                )
                self._workbench.wait_for_workbench(workbench_id)
                return self._assign_and_initialise(request, workbench_id, name)
            except BaseException as exc:
                self._fail(allocation_id, exc)
                self._release_settled(ree_id, allocation_id, provider_id)
                raise

    def reserve_external(self, ree_id: str, name: str, location_id: str) -> WorkbenchHandle:
        """Assign the externally managed bench the user selected by location.

        There is no image to choose: the bench was provisioned outside this
        control plane, so the request records the place and nothing else.
        """
        with self._ree_lock(ree_id), tracer.start_as_current_span("workbench.reserve_external"):
            allocation_id = f"alloc-{uuid4().hex}"
            workbench_id = self._workbench.reserve_external(allocation_id, location_id)
            request = AllocationRequest(allocation_id=allocation_id, ree_id=ree_id, location_id=location_id)
            self._registry.create(request, provider_id=None, workbench_id=workbench_id)
            self._registry.update(allocation_id, AllocationState.WAITING_FOR_WORKBENCH)
            try:
                return self._assign_and_initialise(request, workbench_id, name)
            except BaseException as exc:
                self._fail(allocation_id, exc)
                self._release_settled(ree_id, allocation_id, None)
                raise

    def _assign_and_initialise(self, request: AllocationRequest, workbench_id: str, name: str) -> WorkbenchHandle:
        """Bind the bench to the allocation and put an empty REE on it.

        Nothing is inspected first. The provider already failed the provision if
        the bench could not run the executor or write /ree (its doctor probe),
        and ``init-ree`` below is the check for everything else — an externally
        managed bench that cannot take an REE fails here, on the operation that
        needed it, rather than against a separate model of what a bench is.
        """
        self._registry.update(request.allocation_id, AllocationState.READY)
        self._workbench.assign(workbench_id, request)
        self._workbench.exec_simple(workbench_id, ["init-ree", "--name", name], ree_id=request.ree_id)
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
                try:
                    self._provider.release(handle.provider_id, handle.allocation_id)
                except Exception as exc:
                    # Failed, not stranded draining: releasing the REE again reaches it (release_unreachable).
                    self._registry.update(
                        handle.allocation_id, AllocationState.FAILED, detail=f"provider release failed: {exc}"
                    )
                    raise
                self._enrollment.discard(handle.allocation_id)
            self._registry.update(handle.allocation_id, AllocationState.RELEASED)
            self._registry.remove_placement(handle.ree_id)

    def release_unreachable(self, ree_id: str) -> str | None:
        """Release the REE's lost or failed allocation; its id, or None if it has none.

        Nothing is left to drain: the bench is gone or never came up, so the
        provider is asked to remove what remains and the allocation settles.
        """
        with self._ree_lock(ree_id), tracer.start_as_current_span("workbench.release_unreachable") as span:
            record_ree_id(span, ree_id)
            record = self._registry.for_ree(ree_id)
            if record is None or record.state not in {AllocationState.LOST, AllocationState.FAILED}:
                return None
            self._release_settled(ree_id, record.request.allocation_id, record.provider_id)
            return record.request.allocation_id

    def fail_interrupted(self) -> list[str]:
        """Fail every allocation a previous API process was still setting up; their ids.

        The process that was provisioning them is gone and nothing resumes a provision,
        so each would otherwise stay where it stopped. An assigned allocation is kept: its
        bench dials back in. Releasing the REE then settles a failed one as any other.
        """
        interrupted = {
            AllocationState.REQUESTED,
            AllocationState.PROVISIONING,
            AllocationState.WAITING_FOR_WORKBENCH,
            AllocationState.READY,
        }
        failed: list[str] = []
        for record in self._registry.list():
            if record.state not in interrupted:
                continue
            allocation_id = record.request.allocation_id
            with self._ree_lock(record.request.ree_id):
                self._enrollment.discard(allocation_id)
                self._registry.update(
                    allocation_id, AllocationState.FAILED, detail="the API restarted while setting it up"
                )
            failed.append(allocation_id)
        return failed

    def _fail(self, allocation_id: str, exc: BaseException) -> None:
        record = self._registry.get(allocation_id)
        if record and record.state != AllocationState.FAILED:
            self._registry.update(allocation_id, AllocationState.FAILED, detail=str(exc))

    def _release_settled(self, ree_id: str, allocation_id: str, provider_id: str | None) -> None:
        """Drain and release an allocation that has failed or been lost; a release that fails leaves it failed."""
        self._enrollment.discard(allocation_id)
        self._registry.update(allocation_id, AllocationState.DRAINING)
        if provider_id and not self._provider.release_best_effort(provider_id, allocation_id):
            self._registry.update(allocation_id, AllocationState.FAILED, detail="provider release failed")
            return
        self._registry.update(allocation_id, AllocationState.RELEASED)
        self._registry.remove_placement(ree_id)

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
        """True if a workbench is registered for ree_id (regardless of run state), lost ones included."""
        record = self._registry.for_ree(ree_id)
        return record is not None and record.state in {AllocationState.ASSIGNED, AllocationState.LOST}

    def lookup(self, ree_id: str) -> WorkbenchHandle | None:
        """Return the handle for ree_id, or None if not registered or not running."""
        record = self._registry.for_ree(ree_id)
        if record is None or record.state != AllocationState.ASSIGNED:
            return None
        handle = WorkbenchHandle.from_record(record)
        if handle.mode == "provider_managed":
            state = self._notice_lost(handle)
            running = state is not None and state not in {
                AllocationState.LOST,
                AllocationState.RELEASED,
                AllocationState.FAILED,
            }
        else:
            # An external bench that is not connected may come back; only a provider can say a bench is gone.
            running = self._workbench.is_connected(handle.workbench_id)
        if not running:
            logger.warning(
                "workbench allocation %s not running for %s — returning None",
                handle.allocation_id,
                ree_id,
            )
            return None
        return handle

    def _notice_lost(self, handle: WorkbenchHandle) -> AllocationState | None:
        """Ask the provider about a provider-managed bench, and record it lost if the provider says so."""
        if handle.mode != "provider_managed":
            return None
        state = self._provider.inspect(handle.provider_id, handle.allocation_id)
        if state == AllocationState.LOST:
            # A teardown may have moved the allocation on meanwhile; then it is not lost, it is going.
            with suppress(IllegalTransitionError):
                self._registry.update(
                    handle.allocation_id, AllocationState.LOST, detail="the provider reports the bench gone"
                )
        return state

    # ------------------------------------------------
    # Listing
    # ------------------------------------------------

    def list_all_manifests(self) -> list[tuple[WorkbenchHandle, Ree]]:
        """Every reachable workbench, paired with its REE.

        Unreachable or unreadable workbenches are skipped rather than raised:
        this backs a listing, and one sick bench must not empty it. A document
        that does not parse is skipped too, with a warning, since it is the
        same event to a caller: a workbench this node cannot report on.
        """
        manifests: list[tuple[WorkbenchHandle, Ree]] = []
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
                try:
                    manifests.append((handle, self.dispatcher.get_ree_manifest(handle)))
                except ValidationError:
                    logger.warning("REE %s has a document this control plane cannot parse; omitting it", handle.ree_id)
        return manifests
