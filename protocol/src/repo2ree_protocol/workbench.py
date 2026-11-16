"""The execution wire vocabulary: driving REE commands in an existing workbench.

These are the requests the control plane sends to the *workbench service* — the
process that serves a store of REEs and executes their commands through
short-lived executors. Every request names the REE it addresses in the store.

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

from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame
from repo2ree_protocol.machine import MachineFacts
from repo2ree_protocol.queries import BundleQuery, InitRee, Query

# ================================================
# Identity
# ================================================


class WorkbenchHello(BaseModel):
    """The workbench's first message after dialing in: its identity plus the
    self-reported facts the control plane surfaces in its fleet view. Kept small
    and additive — new fields must default so an older workbench still parses,
    and unknown fields are *ignored* (unlike the frames) so an older control
    plane still accepts a newer workbench's hello.
    """

    model_config = ConfigDict(extra="ignore")

    workbench_id: str
    # The store's token, presented once: the control plane admits the workbench for that store alone.
    enrollment_token: str = ""
    hostname: str = ""
    version: str = ""
    build: BuildInfo = Field(default_factory=BuildInfo)
    executor_build: BuildInfo = Field(default_factory=BuildInfo)
    # The store this workbench serves: a directory of REEs, one per ree_id.
    store_id: str
    # How many actions it runs at once; queries do not count.
    slots: int = Field(default=1, ge=1)
    # How its machine runs the store's REEs' scripts, as ``ree machine`` reports it.
    machine: MachineFacts = Field(default_factory=MachineFacts)
    # Random per-process token: the same workbench_id arriving with a different
    # nonce is a distinct workbench *instance* (a duplicate or takeover), not a
    # reconnect of the one already known.
    nonce: str = ""


# ================================================
# Requests
# ================================================


class InitReeRequest(BaseModel):
    """Create the REE in the workbench's store, which runs ``ree init`` for it; refused where one is already."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["init_ree"] = "init_ree"
    # The REE this addresses in the workbench's store.
    ree_id: str
    init: InitRee
    timeout: int = 60


class ExecQueryRequest(BaseModel):
    """Read the REE: the workbench runs the ``ree`` read that answers ``query`` and streams its stdout back."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_query"] = "exec_query"
    # The REE this addresses in the workbench's store.
    ree_id: str
    query: Query
    timeout: int = 30


class ExecUploadRequest(BaseModel):
    """Bundle the REE and upload the bundle as a file.

    For output too large for the control socket: the workbench writes ``ree bundle``'s
    stdout to a file in the bench, then sends that file over HTTP — ``PUT`` to
    ``transfer_path`` on the same address it dialed for this socket, so the workbench
    still only ever dials out — and answers ``done`` once the control plane has taken
    it. Bulk bytes never share the socket that carries keepalive pings and every other
    request.

    ``transfer_path`` is an absolute path naming a single-use transfer the
    control plane opened for this request; it is the transfer's only credential."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_upload"] = "exec_upload"
    # The REE this addresses in the workbench's store.
    ree_id: str
    query: BundleQuery = Field(default_factory=BundleQuery)
    transfer_path: str
    timeout: int = 600


class StartRunRequest(BaseModel):
    """Start a command in an executor of its own; answered once it started, never when it ends."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["start_run"] = "start_run"
    # The REE this addresses in the workbench's store.
    ree_id: str
    cmd_json: str
    context: ExecutionContext
    run_id: str
    # Extra environment injected into the executor (trace propagation).
    env: dict[str, str] = {}
    # How long it waits for another command in the REE to end before it is refused as busy.
    wait: float = Field(default=0.0, ge=0)


class FollowRunRequest(BaseModel):
    """Stream a started command's log from its ``after``-th line, and how it ended once it has."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["follow_run"] = "follow_run"
    ree_id: str
    attempt_id: str
    after: int = Field(default=0, ge=0)


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel_run"] = "cancel_run"
    # The REE this addresses in the workbench's store.
    ree_id: str
    run_id: str
    # Where the sender journaled asking for it (``<journal>#<seq>``): the stop it causes names it.
    record: str | None = None


class FetchFileRequest(BaseModel):
    """Fetch a file the control plane offers and land it in the bench at ``workbench_path``.

    The counterpart of ``ExecUploadRequest`` for bytes going into the bench (an
    uploaded source archive, a bundle to load): the workbench ``GET``s
    ``transfer_path`` on the address it dialed for this socket, lands the file,
    and answers ``done``. ``transfer_path`` names a single-use transfer the
    control plane opened for this request; it is the transfer's only credential."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["fetch_file"] = "fetch_file"
    # The REE this addresses in the workbench's store.
    ree_id: str
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

    Refused while a run of that REE is active."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["delete_ree"] = "delete_ree"
    ree_id: str


class ListJournalsRequest(BaseModel):
    """List the behaviour journals the workbench keeps for its store, streamed back as one JSON document."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["list_journals"] = "list_journals"


class ReadJournalRequest(BaseModel):
    """Stream one of the store's behaviour journals as written: its complete records above ``after``."""

    model_config = ConfigDict(extra="forbid")

    op: Literal["read_journal"] = "read_journal"
    journal_id: str
    after: int = Field(default=0, ge=0)


class WorkbenchJournal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    process: str
    epoch: int
    last_seq: int


class WorkbenchJournalList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    journals: list[WorkbenchJournal]


# Tagged union discriminated on 'op': every execution call. The op literal
# lives on the request model itself, so both sides share one definition and a
# mistyped op cannot compile into a well-formed request.
WorkbenchRequest = Annotated[
    InitReeRequest
    | ExecQueryRequest
    | ExecUploadRequest
    | StartRunRequest
    | FollowRunRequest
    | CancelRunRequest
    | FetchFileRequest
    | CancelRequest
    | DeleteReeRequest
    | ListJournalsRequest
    | ReadJournalRequest,
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
