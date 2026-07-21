from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

# The terminal status of any executed action, shared by every layer that
# produces or relays one (executor handlers, agent, manager, run registry).
ActionStatus = Literal["succeeded", "failed", "canceled"]

# Coarse machine-readable class of a failure, so a client can act on *why*
# something failed without parsing free-text logs. ``code`` carries the finer
# operation-specific reason within a category.
FailureCategory = Literal[
    "validation",  # the request itself is malformed or references invalid input
    "precondition",  # required state is missing (no metadata, no intent, ...)
    "conflict",  # optimistic-concurrency / idempotency clash
    "execution",  # the author's script or an underlying process failed
    "timeout",  # an operation exceeded its deadline
    "unavailable",  # a dependency (workbench, agent, collector) was unreachable
    "internal",  # an unexpected fault inside repo2ree itself
]

# The component that first observed the failure. Later layers relay the same
# Failure rather than re-minting one, so this stays the true origin.
FailureOrigin = Literal["api", "supervisor", "agent", "executor", "core"]


class Failure(BaseModel):
    """Machine-readable description of why an action did not succeed.

    A single shared object carried on every ``failed`` :class:`ActionResult`
    (and, over time, through error frames, run records, and HTTP envelopes). The
    contract is that a component *enriches* the same failure as it travels up
    the layers rather than collapsing it to ``str(exc)`` at each hop, so the
    ``category``/``origin`` a client sees are the ones the originating component
    chose.
    """

    model_config = ConfigDict(extra="forbid")

    category: FailureCategory
    message: str
    retryable: bool = False
    origin: FailureOrigin
    details: dict[str, Any] | None = None


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ActionStatus
    exit_code: int = 0
    outputs: dict[str, Any] = {}
    # Present iff ``status == "failed"`` (enforced below). Absent for a success
    # or a cancellation, whose terminal status is itself the whole outcome.
    failure: Failure | None = None

    @model_validator(mode="after")
    def _enforce_status_invariants(self) -> Self:
        """Keep status, exit code, and failure mutually consistent.

        * ``succeeded`` implies exit code 0 and no failure.
        * ``failed`` carries a nonzero exit code and a failure.
        * ``canceled`` is its own terminal outcome and carries no failure.
        """
        if self.status == "succeeded":
            if self.exit_code != 0:
                raise ValueError("a succeeded ActionResult must have exit_code 0")
            if self.failure is not None:
                raise ValueError("a succeeded ActionResult must not carry a failure")
        elif self.status == "failed":
            if self.exit_code == 0:
                raise ValueError("a failed ActionResult must have a nonzero exit_code")
            if self.failure is None:
                raise ValueError("a failed ActionResult must carry a failure")
        else:  # canceled
            if self.failure is not None:
                raise ValueError("a canceled ActionResult must not carry a failure")
        return self

    @classmethod
    def failed(
        cls,
        category: FailureCategory,
        message: str,
        *,
        origin: FailureOrigin = "core",
        exit_code: int = 1,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> ActionResult:
        """Build a ``failed`` result carrying a typed :class:`Failure`.

        ``exit_code`` falls back to a nonzero sentinel (1) for failures with no
        underlying process exit code — validation, precondition, conflict — so
        the invariant that a failure has a nonzero exit code always holds.
        """
        return cls(
            status="failed",
            exit_code=exit_code or 1,
            outputs=outputs or {},
            failure=Failure(
                category=category,
                message=message,
                retryable=retryable,
                origin=origin,
                details=details,
            ),
        )
