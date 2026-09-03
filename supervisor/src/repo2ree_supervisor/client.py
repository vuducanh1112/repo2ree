"""The control plane's separate provider and workbench clients.

The manager depends on two seams with deliberately different authority:
``ProviderClient`` creates, probes, and destroys environments;
``WorkbenchClient`` executes REE commands in one. Their production implementations
use separate outbound WebSockets and credentials.

The workbench dials the control plane and holds one outbound socket — it never
listens, so it works from inside clusters and NATed networks that only permit
egress. Streaming calls yield typed ``Frame`` records; request/response calls
return plain values and raise ``WorkbenchUnavailableError`` when the workbench
reports the backend is gone.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.frames import ErrorFrame, Frame, UnavailableFrame


class WorkbenchUnavailableError(RuntimeError):
    """Raised when the workbench reports the workbench backend is gone or stopping."""


def raise_for_terminal_error(frame: Frame) -> None:
    """Translate a terminal error frame into the caller-facing exception.

    The two failure frames mean different things to the control plane: an
    ``UnavailableFrame`` is the backend being gone (a 503-shaped, retryable
    condition) while an ``ErrorFrame`` is an operation failure. Both the manager
    and ``WsWorkbenchClient`` map them the same way, so the mapping lives here."""
    if isinstance(frame, UnavailableFrame):
        raise WorkbenchUnavailableError(frame.detail)
    if isinstance(frame, ErrorFrame):
        raise RuntimeError(frame.detail)


class ProviderClient(Protocol):
    """The verbs the control plane needs to obtain and release a workbench.

    Placement affinity runs through the ids: ``provider_id`` picks the provider
    that will create the environment (empty means any connected one, valid only
    before the REE is pinned), and every later verb takes the ``workbench_id``
    that provisioning returned, so it reaches the provider holding that bench.
    """

    def resolve_location(self, location_id: str, image: str) -> tuple[str, str]:
        """The provider serving ``location_id``, and the image ref to run there.

        Blank ``image`` resolves to the location's first catalog entry. A ref
        the location did not publish is refused unless the location accepts
        custom images — the only check made here, and not a check on what the
        image contains."""
        ...

    def ensure(
        self,
        provider_id: str,
        allocation: AllocationRequest,
        workbench_id: str,
        enrollment_token: str,
    ) -> Iterator[Frame]: ...

    def release(self, provider_id: str, allocation_id: str) -> None: ...

    def release_best_effort(self, provider_id: str, allocation_id: str) -> bool: ...

    def is_running(self, provider_id: str, allocation_id: str) -> bool: ...


class WorkbenchClient(Protocol):
    """The verbs the control plane needs to drive REE commands in a workbench.

    The ``workbench_id`` routes directly to the resident process. Provider-private
    references never cross this boundary.
    """

    def exec_simple(self, workbench_id: str, argv: list[str], timeout: int = 60) -> None:
        """Run an executor subcommand in the bench, discarding output.

        ``argv`` is the ``repo2ree-exec`` subcommand argv *without* the executor
        binary — the serving backend prepends the bench's entry point."""
        ...

    def exec_query(self, workbench_id: str, argv: list[str], timeout: int = 30) -> bytes: ...

    def exec_query_stream(self, workbench_id: str, argv: list[str], timeout: int = 30) -> Iterator[bytes]: ...

    def exec_action(self, workbench_id: str, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[Frame]: ...

    def cancel_run(self, workbench_id: str, run_id: str) -> None: ...

    def copy_in(self, workbench_id: str, source_path: str, workbench_path: str) -> None:
        """Stream a control-plane-local file into the bench at ``workbench_path``.

        ``source_path`` need only exist on the control plane; the bytes travel
        as a chunked transfer (see ``repo2ree_protocol.workbench``)."""
        ...

    def drain(self, workbench_id: str) -> None: ...

    def wait_for_workbench(self, workbench_id: str, timeout: float = 60.0) -> None: ...

    def reserve_external(self, allocation_id: str, location_id: str) -> str: ...

    def release_reservation(self, workbench_id: str, allocation_id: str) -> None: ...

    def assign(self, workbench_id: str, allocation: AllocationRequest) -> None: ...

    def is_connected(self, workbench_id: str) -> bool: ...
