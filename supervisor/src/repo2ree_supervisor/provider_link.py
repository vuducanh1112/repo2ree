"""Control-plane transport for Docker capacity providers."""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from uuid import uuid4

from repo2ree_protocol.frames import ErrorFrame, Frame, RunningFrame, UnavailableFrame, WorkbenchRef
from repo2ree_protocol.provider import (
    IsRunningRequest,
    ProviderCancelRequest,
    ProviderHello,
    ProviderRequest,
    ProviderWsRequest,
    ProvisionRequest,
    RemoveRequest,
    WorkbenchSpec,
    provider_ws_message_adapter,
)
from repo2ree_protocol.tracing import current_traceparent
from repo2ree_supervisor.client import WorkbenchUnavailableError, raise_for_terminal_error
from repo2ree_supervisor.workbench_link import (
    DEFAULT_FRAME_GAP_TIMEOUT,
    QUICK_OP_TIMEOUT,
    PendingReply,
    WorkbenchConnection,
    WorkbenchConnectionRegistry,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderInfo:
    provider_id: str
    hostname: str
    version: str
    docker_mode: str
    connected_at: float


class ProviderConnection(WorkbenchConnection):
    """One provider socket accepting capacity requests only."""

    def __init__(self, send_text: Callable[[str], None], hello: ProviderHello | None = None):
        super().__init__(send_text=send_text)
        self.provider_hello = hello

    def on_message(self, text: str) -> None:
        message = provider_ws_message_adapter.validate_json(text)
        with self._lock:
            pending = self._pending.get(message.id)
        if pending is not None:
            pending.put(message.frame)

    def request(  # type: ignore[override]
        self, request: ProviderRequest, *, frame_gap_timeout: float = DEFAULT_FRAME_GAP_TIMEOUT
    ) -> Iterator[Frame]:
        yield from self.start(request).frames(frame_gap_timeout=frame_gap_timeout)

    def start(self, request: ProviderRequest) -> PendingReply:  # type: ignore[override]
        req_id = uuid4().hex
        pending: queue.Queue[Frame] = queue.Queue()
        with self._lock:
            if self._closed:
                raise WorkbenchUnavailableError("provider connection closed")
            self._pending[req_id] = pending
        try:
            self._send_text(
                ProviderWsRequest(id=req_id, request=request, traceparent=current_traceparent()).model_dump_json(
                    exclude_none=True
                )
            )
        except BaseException:
            self._discard(req_id)
            raise
        return PendingReply(self, req_id, pending, request.op)

    def _cancel(self, req_id: str) -> None:
        with self._lock:
            if self._closed:
                return
        with suppress(Exception):
            self._send_text(
                ProviderWsRequest(
                    id=uuid4().hex,
                    request=ProviderCancelRequest(request_id=req_id),
                ).model_dump_json()
            )

    def close(self) -> None:
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            self._pending.clear()
        for reply in pending:
            reply.put(UnavailableFrame(detail="provider connection closed"))


class ProviderConnectionRegistry(WorkbenchConnectionRegistry):
    """Provider-specific registry with capacity vocabulary at its boundary."""

    def register(self, provider_id: str, connection: ProviderConnection) -> None:  # type: ignore[override]
        super().register(provider_id, connection)

    def unregister(self, provider_id: str, connection: ProviderConnection) -> None:  # type: ignore[override]
        super().unregister(provider_id, connection)

    def pick(self, provider_id: str | None = None) -> ProviderConnection:
        connection = super().pick(provider_id)
        if not isinstance(connection, ProviderConnection):
            raise TypeError("provider registry contains a non-provider connection")
        return connection

    def resolve_provider(self, provider_id: str | None = None) -> str:
        return super().resolve(provider_id)

    def list_providers(self) -> list[ProviderInfo]:
        with self._lock:
            providers = [
                ProviderInfo(
                    provider_id=provider_id,
                    hostname=connection.provider_hello.hostname if connection.provider_hello else "",
                    version=connection.provider_hello.version if connection.provider_hello else "",
                    docker_mode=connection.provider_hello.docker_mode if connection.provider_hello else "",
                    connected_at=self._connected_at.get(provider_id, 0.0),
                )
                for provider_id, candidate in self._workbenches.items()
                if isinstance(candidate, ProviderConnection)
                for connection in (candidate,)
            ]
        providers.sort(key=lambda info: (info.hostname, info.provider_id))
        return providers


class WsProviderClient:
    """Docker capacity client backed by a provider-only connection."""

    def __init__(self, registry: ProviderConnectionRegistry):
        self._registry = registry

    def resolve_provider(self, provider_id: str) -> str:
        return self._registry.resolve_provider(provider_id)

    def provision(
        self,
        provider_id: str,
        allocation_id: str,
        workbench_id: str,
        enrollment_token: str,
        ree_id: str,
        spec: WorkbenchSpec,
    ) -> Iterator[Frame]:
        return self._registry.pick(provider_id).request(
            ProvisionRequest(
                allocation_id=allocation_id,
                workbench_id=workbench_id,
                enrollment_token=enrollment_token,
                ree_id=ree_id,
                spec=spec,
            ),
            frame_gap_timeout=DEFAULT_FRAME_GAP_TIMEOUT,
        )

    def remove(self, provider_id: str, ref: WorkbenchRef) -> None:
        self._drain_void(
            self._registry.pick(provider_id).request(RemoveRequest(ref=ref), frame_gap_timeout=QUICK_OP_TIMEOUT)
        )

    def remove_best_effort(self, provider_id: str, ref: WorkbenchRef) -> bool:
        try:
            self.remove(provider_id, ref)
        except (WorkbenchUnavailableError, RuntimeError):
            logger.warning("best-effort provider removal failed for %s", ref.runtime, exc_info=True)
            return False
        return True

    def is_running(self, provider_id: str, ref: WorkbenchRef) -> bool:
        try:
            frames = self._registry.pick(provider_id).request(
                IsRunningRequest(ref=ref), frame_gap_timeout=QUICK_OP_TIMEOUT
            )
            for frame in frames:
                if isinstance(frame, RunningFrame):
                    return frame.running
                if isinstance(frame, ErrorFrame | UnavailableFrame):
                    return False
        except WorkbenchUnavailableError:
            return False
        return False

    @staticmethod
    def _drain_void(frames: Iterator[Frame]) -> None:
        for frame in frames:
            raise_for_terminal_error(frame)
