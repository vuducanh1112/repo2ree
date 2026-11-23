from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.result import ActionResult


class LogFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["log"] = "log"
    stream: str
    level: str
    message: str


LogSink = Callable[[str, str, str], None]


class SpanFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["span"] = "span"
    payload: str


class ResultFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["result"] = "result"
    result: ActionResult


class DoneFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["done"] = "done"


class AcceptedFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["accepted"] = "accepted"


class BusyFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["busy"] = "busy"
    detail: str


class UnknownFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["unknown"] = "unknown"
    detail: str


class UnavailableFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["unavailable"] = "unavailable"
    detail: str


class ErrorFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["error"] = "error"
    detail: str


COPY_CHUNK_BYTES = 256 * 1024


class BytesChunkFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["bytes_chunk"] = "bytes_chunk"
    data_b64: str


Frame = Annotated[
    LogFrame
    | SpanFrame
    | ResultFrame
    | DoneFrame
    | AcceptedFrame
    | BusyFrame
    | UnknownFrame
    | UnavailableFrame
    | ErrorFrame
    | BytesChunkFrame,
    Field(discriminator="type"),
]

frame_adapter: TypeAdapter[Frame] = TypeAdapter(Frame)

TERMINAL_FRAME_TYPES = frozenset({"result", "done", "accepted", "busy", "unknown", "unavailable", "error"})
