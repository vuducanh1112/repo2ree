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

from repo2ree_protocol.frames import Frame

# ================================================
# Identity
# ================================================


class WorkbenchCapabilities(BaseModel):
    """Facts observed inside the environment hosting the workbench."""

    model_config = ConfigDict(extra="ignore")

    root_writable: bool = False
    executor_available: bool = False
    docker_mode: Literal["nested", "host-socket", "unknown"] | None = None
    docker_version: str = ""


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
    substrate: str = ""
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
    argv: list[str]
    timeout: int = 60


class ExecQueryRequest(BaseModel):
    """Run an executor subcommand in the bench, streaming its stdout back.

    ``argv`` is the executor subcommand argv, as in ``ExecSimpleRequest``."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_query"] = "exec_query"
    argv: list[str]
    timeout: int = 30


class ExecActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_action"] = "exec_action"
    cmd_json: str
    run_id: str
    # Extra environment injected into the executor (trace propagation).
    env: dict[str, str] = {}


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel_run"] = "cancel_run"
    run_id: str


class CopyOpenRequest(BaseModel):
    """Begin a chunked copy into ``workbench_path``; the workbench replies with
    a ``transfer`` handle that later chunks reference."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["copy_open"] = "copy_open"
    workbench_path: str


class CopyChunkRequest(BaseModel):
    """Write one bounded, base64-encoded slice of the file to an open transfer.

    ``offset`` is the slice's byte position in the assembled file. The control
    plane pipelines chunks (several in flight before the first ack), and the
    workbench handles each request concurrently — so chunks may *apply* out of
    order; the offset makes the write position explicit rather than relying on
    arrival order."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["copy_chunk"] = "copy_chunk"
    transfer_id: str
    offset: int
    data_b64: str


class CopyCloseRequest(BaseModel):
    """Finish a transfer: the workbench lands the assembled file in the bench."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["copy_close"] = "copy_close"
    transfer_id: str


class CopyAbortRequest(BaseModel):
    """Drop a transfer without landing it (a mid-stream failure); the workbench
    discards the partial file."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["copy_abort"] = "copy_abort"
    transfer_id: str


class CancelRequest(BaseModel):
    """Stop the in-flight request ``request_id``: its caller is gone (abandoned
    stream, frame-gap timeout), so any work still running for it is wasted.
    Best-effort and idempotent — answered with ``done`` whether or not the
    target is still running; the cancelled request itself sends no further
    frames."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel"] = "cancel"
    request_id: str


class DrainWorkbenchRequest(BaseModel):
    """Finish in-flight work and terminate this single-use workbench."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["drain"] = "drain"


class BindAllocationRequest(BaseModel):
    """Bind one authenticated idle external workbench to one REE allocation."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["bind_allocation"] = "bind_allocation"
    allocation_id: str = Field(min_length=1)
    ree_id: str = Field(min_length=1)


# Tagged union discriminated on 'op': every execution call. The op literal
# lives on the request model itself, so both sides share one definition and a
# mistyped op cannot compile into a well-formed request.
WorkbenchRequest = Annotated[
    ExecSimpleRequest
    | ExecQueryRequest
    | ExecActionRequest
    | CancelRunRequest
    | CopyOpenRequest
    | CopyChunkRequest
    | CopyCloseRequest
    | CopyAbortRequest
    | CancelRequest
    | DrainWorkbenchRequest
    | BindAllocationRequest,
    Field(discriminator="op"),
]


class WorkbenchWsRequest(BaseModel):
    """A control-plane call on the execution-only workbench connection."""

    model_config = ConfigDict(extra="forbid")

    id: str
    request: WorkbenchRequest
    traceparent: str | None = None


class WorkbenchWsMessage(BaseModel):
    """A workbench response frame correlated to an execution request."""

    model_config = ConfigDict(extra="forbid")

    id: str
    frame: Frame


workbench_hello_adapter: TypeAdapter[WorkbenchHello] = TypeAdapter(WorkbenchHello)
workbench_ws_request_adapter: TypeAdapter[WorkbenchWsRequest] = TypeAdapter(WorkbenchWsRequest)
workbench_ws_message_adapter: TypeAdapter[WorkbenchWsMessage] = TypeAdapter(WorkbenchWsMessage)
