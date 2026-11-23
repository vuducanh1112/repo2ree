from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.execution import ExecutionContext
from repo2ree_protocol.frames import Frame
from repo2ree_protocol.machine import MachineFacts
from repo2ree_protocol.queries import BundleQuery, InitRee, Query


class WorkbenchHello(BaseModel):
    model_config = ConfigDict(extra="ignore")

    workbench_id: str
    enrollment_token: str = ""
    hostname: str = ""
    version: str = ""
    build: BuildInfo = Field(default_factory=BuildInfo)
    executor_build: BuildInfo = Field(default_factory=BuildInfo)
    store_id: str
    slots: int = Field(default=1, ge=1)
    machine: MachineFacts = Field(default_factory=MachineFacts)
    nonce: str = ""


class InitReeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["init_ree"] = "init_ree"
    ree_id: str
    init: InitRee
    timeout: int = 60


class ExecQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_query"] = "exec_query"
    ree_id: str
    query: Query
    timeout: int = 30


class ExecUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["exec_upload"] = "exec_upload"
    ree_id: str
    query: BundleQuery = Field(default_factory=BundleQuery)
    transfer_path: str
    timeout: int = 600


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["start_run"] = "start_run"
    ree_id: str
    cmd_json: str
    context: ExecutionContext
    run_id: str
    env: dict[str, str] = {}
    wait: float = Field(default=0.0, ge=0)


class FollowRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["follow_run"] = "follow_run"
    ree_id: str
    attempt_id: str
    after: int = Field(default=0, ge=0)


class CancelRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel_run"] = "cancel_run"
    ree_id: str
    run_id: str
    record: str | None = None


class FetchFileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["fetch_file"] = "fetch_file"
    ree_id: str
    transfer_path: str
    workbench_path: str
    timeout: int = 600


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["cancel"] = "cancel"
    request_id: str


class DeleteReeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["delete_ree"] = "delete_ree"
    ree_id: str


class ListJournalsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["list_journals"] = "list_journals"


class ReadJournalRequest(BaseModel):
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
    model_config = ConfigDict(extra="forbid")

    id: str
    request: WorkbenchRequest
    traceparent: str | None = None


class WorkbenchWsMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    frame: Frame


workbench_hello_adapter: TypeAdapter[WorkbenchHello] = TypeAdapter(WorkbenchHello)
workbench_ws_request_adapter: TypeAdapter[WorkbenchWsRequest] = TypeAdapter(WorkbenchWsRequest)
workbench_ws_message_adapter: TypeAdapter[WorkbenchWsMessage] = TypeAdapter(WorkbenchWsMessage)
