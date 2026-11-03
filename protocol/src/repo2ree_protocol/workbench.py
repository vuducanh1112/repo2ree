"""The execution wire vocabulary: driving REE commands in an existing workbench.

These are the requests the control plane sends to the *workbench service* — the
process that executes REE commands through short-lived executors. They address
a bench exclusively by its opaque ``WorkbenchRef``; nothing here can create,
replace, or destroy an environment (that is ``repo2ree_protocol.provider``'s
vocabulary, and keeping the two disjoint is what lets their authority differ).

Byte payloads never ride one frame — they are too big for the transport's
receive caps — so both directions chunk. Reading out (exec_query: a sealed
archive, a workspace file) streams ``bytes_chunk`` frames ending in ``done``.
Copying a file in is a *chunked transfer*: ``copy_open`` mints a ``transfer``
handle, each ``copy_chunk`` appends bounded bytes and acks with ``done``, and
``copy_close`` (or ``copy_abort`` to drop a half-written one) ends it. Either
way, no frame approaches the transport's size cap.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.allocation import AllocationRequest
from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame

# ================================================
# Identity
# ================================================


class WorkbenchCapabilities(BaseModel):
    """What a workbench offers the scripts it runs, so REEs that need it can be sent there."""

    model_config = ConfigDict(extra="ignore")

    arch: str = ""
    # Whether a container engine is installed beside the workbench.
    container_engine: bool = False
    # The engine a script can reach: none, the host's (its socket), or one nested in the bench.
    script_engine: Literal["none", "socket", "nested"] = "none"
    gpus: int = Field(default=0, ge=0)


class WorkbenchHello(BaseModel):
    """The workbench's first message after dialing in: its identity plus the
    self-reported facts the control plane surfaces in its fleet view. Kept small
    and additive — new fields must default so an older workbench still parses,
    and unknown fields are *ignored* (unlike the frames) so an older control
    plane still accepts a newer workbench's hello.
    """

    model_config = ConfigDict(extra="ignore")

    workbench_id: str
    mode: Literal["managed", "external"] = "managed"
    allocation_id: str = ""
    enrollment_token: str = ""
    hostname: str = ""
    version: str = ""
    build: BuildInfo = Field(default_factory=BuildInfo)
    executor_build: BuildInfo = Field(default_factory=BuildInfo)
    location_id: str = ""
    # The base image this bench was provisioned from; blank for an externally
    # managed bench, which this control plane did not build.
    image: str = ""
    # The store this workbench serves: a directory of REEs, one per ree_id. Blank for a managed
    # bench, whose root is the one REE it was provisioned for.
    store_id: str = ""
    # Where it runs the author's scripts: on its own host, or in a container from the REE's image.
    backend: Literal["host", "container"] = "host"
    # The images a container backend offers an REE created in its store, the first the default.
    images: list[str] = Field(default_factory=list)
    # How many actions it runs at once; queries do not count.
    slots: int = Field(default=1, ge=1)
    capabilities: WorkbenchCapabilities = Field(default_factory=WorkbenchCapabilities)
    # Random per-process token: the same workbench_id arriving with a different
    # nonce is a distinct workbench *instance* (a duplicate or takeover), not a
    # reconnect of the one already known.
    nonce: str = ""


# ================================================
# Requests
# ================================================


class ExecSimpleRequest(BaseModel):
    """Run an executor subcommand in the bench, discarding output.

    ``argv`` is the ``repo2ree-exec`` subcommand argv (e.g. ``["init-ree", …]``)
    — *without* the executor binary. The resident workbench resolves its local
    executor entry point from configuration."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_simple"] = "exec_simple"
    # The REE this addresses in the workbench's store; None on a managed bench, whose root is its one REE.
    ree_id: str | None = None
    argv: list[str]
    timeout: int = 60


class ExecQueryRequest(BaseModel):
    """Run an executor subcommand in the bench, streaming its stdout back.

    ``argv`` is the executor subcommand argv, as in ``ExecSimpleRequest``."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_query"] = "exec_query"
    # The REE this addresses in the workbench's store; None on a managed bench, whose root is its one REE.
    ree_id: str | None = None
    argv: list[str]
    timeout: int = 30


class ExecUploadRequest(BaseModel):
    """Run an executor subcommand in the bench and upload its stdout as a file.

    For output too large for the control socket (an REE archive): the workbench
    writes the subcommand's stdout to a file in the bench, then sends that file
    over HTTP — ``PUT`` to ``transfer_path`` on the same address it dialed for
    this socket, so the workbench still only ever dials out — and answers
    ``done`` once the control plane has taken it. Bulk bytes never share the
    socket that carries keepalive pings and every other request.

    ``transfer_path`` is an absolute path naming a single-use transfer the
    control plane opened for this request; it is the transfer's only credential."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_upload"] = "exec_upload"
    # The REE this addresses in the workbench's store; None on a managed bench, whose root is its one REE.
    ree_id: str | None = None
    argv: list[str]
    transfer_path: str
    timeout: int = 600


class ExecActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_action"] = "exec_action"
    # The REE this addresses in the workbench's store; None on a managed bench, whose root is its one REE.
    ree_id: str | None = None
    cmd_json: str
    context: ExecutionContext | None = None
    run_id: str
    # Extra environment injected into the executor (trace propagation).
    env: dict[str, str] = {}


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel_run"] = "cancel_run"
    # The REE this addresses in the workbench's store; None on a managed bench, whose root is its one REE.
    ree_id: str | None = None
    run_id: str


class FetchFileRequest(BaseModel):
    """Fetch a file the control plane offers and land it in the bench at ``workbench_path``.

    The counterpart of ``ExecUploadRequest`` for bytes going into the bench (an
    uploaded source archive, a bundle to load): the workbench ``GET``s
    ``transfer_path`` on the address it dialed for this socket, lands the file,
    and answers ``done``. ``transfer_path`` names a single-use transfer the
    control plane opened for this request; it is the transfer's only credential."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["fetch_file"] = "fetch_file"
    # The REE this addresses in the workbench's store; None on a managed bench, whose root is its one REE.
    ree_id: str | None = None
    transfer_path: str
    workbench_path: str
    timeout: int = 600


class CancelRequest(BaseModel):
    """Stop the in-flight request ``request_id``: its caller is gone (abandoned
    stream, frame-gap timeout), so any work still running for it is wasted.
    Best-effort and idempotent — answered with ``done`` whether or not the
    target is still running; the cancelled request itself sends no further
    frames."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel"] = "cancel"
    request_id: str


class DeleteReeRequest(BaseModel):
    """Delete an REE and everything in its directory from this workbench's store.

    Refused while a run of that REE is active. Only a workbench serving a store has
    REEs to delete: a managed bench's one REE goes with the bench."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["delete_ree"] = "delete_ree"
    ree_id: str


class DrainWorkbenchRequest(BaseModel):
    """Finish in-flight work and terminate this single-use workbench."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["drain"] = "drain"


class AssignAllocationRequest(BaseModel):
    """Assign a validated allocation to this otherwise idle workbench."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["assign_allocation"] = "assign_allocation"
    allocation: AllocationRequest


# Tagged union discriminated on 'op': every execution call. The op literal
# lives on the request model itself, so both sides share one definition and a
# mistyped op cannot compile into a well-formed request.
WorkbenchRequest = Annotated[
    ExecSimpleRequest
    | ExecQueryRequest
    | ExecUploadRequest
    | ExecActionRequest
    | CancelRunRequest
    | FetchFileRequest
    | CancelRequest
    | DeleteReeRequest
    | DrainWorkbenchRequest
    | AssignAllocationRequest,
    Field(discriminator="op"),
]


class WorkbenchWsRequest(BaseModel):
    """A control-plane call on the execution-only workbench connection."""

    model_config = ConfigDict(extra="forbid")

    id: str
    request: WorkbenchRequest
    traceparent: str | None = None


class WorkbenchWsMessage(BaseModel):
    """A frame from the workbench, correlated to an execution request or not.

    ``id`` names the in-flight request this answers. It is None for a frame the
    workbench originated itself — self-telemetry, which answers no request and
    correlates to nothing the control plane asked for.
    """

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    frame: Frame


workbench_hello_adapter: TypeAdapter[WorkbenchHello] = TypeAdapter(WorkbenchHello)
workbench_ws_request_adapter: TypeAdapter[WorkbenchWsRequest] = TypeAdapter(WorkbenchWsRequest)
workbench_ws_message_adapter: TypeAdapter[WorkbenchWsMessage] = TypeAdapter(WorkbenchWsMessage)
