"""Wire contract between the control plane and a workbench agent.

The control plane (supervisor/api) never touches a container runtime directly.
It speaks these messages to an *agent* — a separate deployable that owns the
runtime on its host. The agent dials the control plane and holds one outbound
WebSocket; every call is multiplexed over it via the ``WsRequest``/``WsMessage``
envelope below. The schema lives here alongside ``Command``/``ActionResult``
rather than in the supervisor because both sides of the wire share it.

Each call returns a stream of ``AgentFrame`` records tagged with the request id.
Lifecycle/exec calls that produce incremental output (image pulls, live command
logs) emit ``log``/``span`` frames and end with a terminal frame (``location`` /
``result`` / ``done``, or ``unavailable`` / ``error``). Request/response calls
(remove, is-running) emit a single terminal frame (``running`` / ``done``, or
``unavailable`` / ``error``).

Byte payloads never ride one frame — they are too big for the transport's
receive caps — so both directions chunk. Reading out (exec_query: a sealed
archive, a workspace file) streams ``bytes_chunk`` frames ending in ``done``.
Copying a file in is a *chunked transfer*: ``copy_open`` mints a ``transfer``
handle, each ``copy_chunk`` appends bounded bytes and acks with ``done``, and
``copy_close`` (or ``copy_abort`` to drop a half-written one) ends it. Either
way, no frame approaches the transport's size cap.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.result import ActionResult

# ================================================
# Addressing
# ================================================


class WorkbenchLocation(BaseModel):
    """Where a provisioned workbench lives, as minted by the agent.

    The control plane treats this as an opaque address token it records in its
    registry and hands back on later calls — like an ECS task ARN or a pod name.
    """

    model_config = ConfigDict(extra="forbid")

    container_name: str
    volume_name: str


# ================================================
# Requests
# ================================================


class ProvisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ree_id: str
    # Always a fully-resolved concrete image reference; the agent never applies
    # image defaults (that is control-plane policy).
    image: str


class ReprovisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ree_id: str
    location: WorkbenchLocation
    image: str


class RemoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ree_id: str
    location: WorkbenchLocation


class IsRunningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container_name: str


class ExecSimpleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container_name: str
    argv: list[str]
    timeout: int = 60


class ExecQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container_name: str
    argv: list[str]
    timeout: int = 30


class ExecActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    container_name: str
    cmd_json: str
    run_id: str
    # Extra environment injected into the executor (trace propagation).
    env: dict[str, str] = {}


# Raw bytes per copy chunk. Base64 inflates the payload ~4/3, so a chunk frame
# stays well under the transport's default receive cap (websockets: 1 MiB) while
# the agent holds at most one chunk in memory at a time.
COPY_CHUNK_BYTES = 256 * 1024


class CopyOpenRequest(BaseModel):
    """Begin a chunked copy into ``container_path``; the agent replies with a
    ``transfer`` handle that later chunks reference."""

    model_config = ConfigDict(extra="forbid")

    container_name: str
    container_path: str


class CopyChunkRequest(BaseModel):
    """Append one bounded, base64-encoded slice of the file to an open transfer."""

    model_config = ConfigDict(extra="forbid")

    transfer_id: str
    data_b64: str


class CopyCloseRequest(BaseModel):
    """Finish a transfer: the agent lands the assembled file in the container."""

    model_config = ConfigDict(extra="forbid")

    transfer_id: str


class CopyAbortRequest(BaseModel):
    """Drop a transfer without landing it (a mid-stream failure); the agent
    discards the partial file."""

    model_config = ConfigDict(extra="forbid")

    transfer_id: str


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


class LocationFrame(BaseModel):
    """Terminal frame of a successful provision."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["location"] = "location"
    location: WorkbenchLocation


class ResultFrame(BaseModel):
    """Terminal frame of a completed action."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["result"] = "result"
    result: ActionResult


class DoneFrame(BaseModel):
    """Terminal frame of a streaming call with no payload (reprovision)."""

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


class BytesChunkFrame(BaseModel):
    """One bounded slice of a byte-returning query's result (exec_query).

    Incremental, like ``log``: the agent slices the payload into
    ``COPY_CHUNK_BYTES``-sized chunks so no frame nears the transport's receive
    cap (a sealed archive can be far larger than uvicorn's 16 MiB limit), and a
    terminal ``done`` ends the stream. The read twin of the chunked copy-in."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bytes_chunk"] = "bytes_chunk"
    data_b64: str


class TransferFrame(BaseModel):
    """Terminal frame of ``copy_open``: the agent's handle for a byte transfer."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["transfer"] = "transfer"
    transfer_id: str


# Tagged union discriminated on 'type'.
AgentFrame = Annotated[
    LogFrame
    | SpanFrame
    | LocationFrame
    | ResultFrame
    | DoneFrame
    | UnavailableFrame
    | ErrorFrame
    | RunningFrame
    | BytesChunkFrame
    | TransferFrame,
    Field(discriminator="type"),
]

agent_frame_adapter: TypeAdapter[AgentFrame] = TypeAdapter(AgentFrame)

# Frame types that terminate a request's response stream. Everything else
# (log, span, bytes_chunk) is incremental and more frames follow.
TERMINAL_FRAME_TYPES = frozenset({"location", "result", "done", "unavailable", "error", "running", "transfer"})


# ================================================
# WebSocket multiplexing envelope
# ================================================
#
# When the agent dials the control plane and holds one connection, a single
# socket multiplexes every call. Each request carries a correlation id; each
# response frame echoes it so the control plane can route frames back to the
# blocked caller. The op names map 1:1 to AgentClient verbs; the agent's request
# dispatcher is the single source of truth for which ops it serves.


class AgentHello(BaseModel):
    """The agent's first message after dialing in: its identity plus the
    self-reported facts the control plane surfaces in its fleet view. Kept small
    and additive — new fields must default so an older agent still parses, and
    unknown fields are *ignored* (unlike the frames) so an older control plane
    still accepts a newer agent's hello.
    """

    model_config = ConfigDict(extra="ignore")

    agent_id: str
    hostname: str = ""
    version: str = ""
    docker_mode: str = ""
    # Random per-process token: the same agent_id arriving with a different
    # nonce is a distinct agent *instance* (a duplicate or takeover), not a
    # reconnect of the one already known.
    nonce: str = ""


class WsRequest(BaseModel):
    """A control-plane→agent call over the multiplexed socket."""

    model_config = ConfigDict(extra="forbid")

    id: str
    op: str
    args: dict[str, Any] = {}


class WsMessage(BaseModel):
    """An agent→control-plane response frame, tagged with its request id."""

    model_config = ConfigDict(extra="forbid")

    id: str
    frame: AgentFrame


ws_hello_adapter: TypeAdapter[AgentHello] = TypeAdapter(AgentHello)
ws_request_adapter: TypeAdapter[WsRequest] = TypeAdapter(WsRequest)
ws_message_adapter: TypeAdapter[WsMessage] = TypeAdapter(WsMessage)
