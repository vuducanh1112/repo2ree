"""Streaming response frames of the workbench wire.

Every call the control plane issues to a workbench (``repo2ree_protocol.workbench``)
answers with a stream of these frames tagged with the request id.

Calls that produce incremental output (live command logs) emit ``log``/``span``
frames and end with a terminal frame (``result`` / ``done``, or ``unavailable`` /
``error``). Request/response calls emit a single terminal frame (``done``, or
``unavailable`` / ``error``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.result import ActionResult

# ================================================
# Frames
# ================================================


class LogFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["log"] = "log"
    stream: str
    level: str
    message: str


# stream, level, message: a LogFrame before it is framed.
LogSink = Callable[[str, str, str], None]


class SpanFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["span"] = "span"
    # A single serialized span, relayed verbatim to the collector (SpanSink).
    payload: str


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


COPY_CHUNK_BYTES = 256 * 1024


class BytesChunkFrame(BaseModel):
    """One bounded slice of a byte-returning query's result (exec_query).

    Incremental, like ``log``; a terminal ``done`` ends the stream. For small
    results only: a file goes beside the socket (``exec_upload``)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bytes_chunk"] = "bytes_chunk"
    data_b64: str


# Tagged union discriminated on 'type'.
Frame = Annotated[
    LogFrame | SpanFrame | ResultFrame | DoneFrame | UnavailableFrame | ErrorFrame | BytesChunkFrame,
    Field(discriminator="type"),
]

frame_adapter: TypeAdapter[Frame] = TypeAdapter(Frame)

# Frame types that terminate a request's response stream. Everything else
# (log, span, bytes_chunk) is incremental and more frames follow.
TERMINAL_FRAME_TYPES = frozenset({"result", "done", "unavailable", "error"})
