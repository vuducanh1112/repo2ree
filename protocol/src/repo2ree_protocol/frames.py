"""Streaming response frames and workbench addressing, shared by both wires.

Every call the control plane issues — capacity (``repo2ree_protocol.provider``)
or execution (``repo2ree_protocol.workbench``) — answers with a stream of these
frames tagged with the request id. The vocabulary is shared rather than split
per wire because both sides stream the same shapes: a provision emits ``log``
frames exactly like a build does, and both end in a terminal frame.

Lifecycle/exec calls that produce incremental output (image pulls, live command
logs) emit ``log``/``span`` frames and end with a terminal frame
(``workbench_ref`` for provision, ``result`` / ``done``, or
``unavailable`` / ``error``). Request/response calls (remove, is-running) emit a
single terminal frame (``running`` / ``done``, or ``unavailable`` / ``error``).

``WorkbenchRef`` lives here for the same reason: it is minted by the terminal
frame of a provision and then addresses every execution call, so it is the one
piece of addressing both vocabularies speak.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.allocation import AllocationState
from repo2ree_protocol.result import ActionResult

# ================================================
# Addressing
# ================================================


class WorkbenchRef(BaseModel):
    """Opaque backend-minted reference to a provisioned workbench.

    The control plane records and returns the token but never interprets it.
    ``runtime`` lets the serving process route the reference to the backend that
    minted it; the backend alone owns the token's representation.
    """

    model_config = ConfigDict(extra="forbid")

    runtime: str = Field(min_length=1)
    token: str = Field(min_length=1)


# ================================================
# Streaming frames
# ================================================


class LogFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["log"] = "log"
    stream: str
    level: str
    message: str


class SpanFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["span"] = "span"
    # A single serialized span, relayed verbatim to the collector (SpanSink).
    payload: str


class WorkbenchRefFrame(BaseModel):
    """Terminal frame of a successful provision."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["workbench_ref"] = "workbench_ref"
    ref: WorkbenchRef


class ResultFrame(BaseModel):
    """Terminal frame of a completed action."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["result"] = "result"
    result: ActionResult


class DoneFrame(BaseModel):
    """Terminal frame of a call with no payload (exec_simple, remove, …)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["done"] = "done"


class UnavailableFrame(BaseModel):
    """Terminal frame: the backend was gone or stopping mid-stream."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["unavailable"] = "unavailable"
    detail: str


class ErrorFrame(BaseModel):
    """Terminal frame: the operation failed for a non-gone reason."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    detail: str


class RunningFrame(BaseModel):
    """Terminal frame of an is-running query."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["running"] = "running"
    running: bool


class AllocationStatusFrame(BaseModel):
    """Terminal provider report for ensure/inspect operations."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["allocation_status"] = "allocation_status"
    allocation_id: str = Field(min_length=1)
    state: AllocationState
    workbench_id: str | None = None
    # What the provider actually ran, pinned by digest where the runtime could
    # resolve one. The request names the image that was asked for; this names
    # the one that arrived, and the two differ whenever a tag has moved.
    resolved_image: str = ""
    detail: str = ""


# Raw bytes per streamed chunk, in both directions (bytes_chunk frames out,
# copy_chunk requests in). Base64 inflates the payload ~4/3, so a chunk frame
# stays well under the transport's default receive cap (websockets: 1 MiB)
# while the receiver holds at most one chunk in memory at a time.
COPY_CHUNK_BYTES = 256 * 1024


class BytesChunkFrame(BaseModel):
    """One bounded slice of a byte-returning query's result (exec_query).

    Incremental, like ``log``; a terminal ``done`` ends the stream. The read
    twin of the chunked copy-in (see ``repo2ree_protocol.workbench``)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bytes_chunk"] = "bytes_chunk"
    data_b64: str


class TransferFrame(BaseModel):
    """Terminal frame of ``copy_open``: the handle for a byte transfer."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["transfer"] = "transfer"
    transfer_id: str


# Tagged union discriminated on 'type'.
Frame = Annotated[
    LogFrame
    | SpanFrame
    | WorkbenchRefFrame
    | ResultFrame
    | DoneFrame
    | UnavailableFrame
    | ErrorFrame
    | RunningFrame
    | AllocationStatusFrame
    | BytesChunkFrame
    | TransferFrame,
    Field(discriminator="type"),
]

frame_adapter: TypeAdapter[Frame] = TypeAdapter(Frame)

# Frame types that terminate a request's response stream. Everything else
# (log, span, bytes_chunk) is incremental and more frames follow.
TERMINAL_FRAME_TYPES = frozenset(
    {"workbench_ref", "result", "done", "unavailable", "error", "running", "allocation_status", "transfer"}
)
