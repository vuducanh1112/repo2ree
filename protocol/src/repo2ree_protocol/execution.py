"""Invocation identity, independent of runs, transport requests, and tracing."""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    ree_id: str | None = None
    # Where the sender journaled dispatching this attempt (``<journal>#<seq>``). The
    # attempt's record keeps it, which proves the attempt ran after the dispatch.
    dispatch_record: str | None = None

    @classmethod
    def new(cls, *, ree_id: str | None = None, operation_id: str | None = None) -> "ExecutionContext":
        """Retries may retain a logical operation ID, but always get a new attempt."""
        return cls(operation_id=operation_id or uuid4().hex, attempt_id=uuid4().hex, ree_id=ree_id)
