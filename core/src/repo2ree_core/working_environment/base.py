"""Protocol definitions for Working Environments.

A WorkingEnvironment is the execution context for workflow steps that run
against a REE workspace (build-runtime, activation-test, experiments, etc.).
It is a context manager: ``__enter__`` provisions the environment,
``__exit__`` tears it down unconditionally.

Implementations live in sibling modules (``docker_env``, future ``vm_env``).
Callers obtain instances through :func:`working_environment.manager.acquire`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from repo2ree_core.container.run_script import LogSink

# ================================================
# Types
# ================================================

# LogSink (the (stream, level, message) sink) is owned by container.run_script,
# the lower-level layer this package builds on; re-exported here for callers.
CancelCheck = Callable[[], bool]  # True once a cancel has been requested


# ================================================
# Spec
# ================================================


@dataclass(frozen=True)
class WorkingEnvironmentSpec:
    """Parameters for provisioning a WorkingEnvironment on a Machine."""

    workspace_path: Path
    run_id: str
    log: LogSink
    is_canceled: CancelCheck | None = None
    image: str | None = None  # docker base image; None → implementation default
    activate: str = ""  # native substrate: command sourced before each run


@dataclass(frozen=True)
class ScriptStep:
    """A single script execution within a WorkingEnvironment.

    ``script_rel_path`` is relative to the workspace root.
    ``working_dir_rel`` is also relative to the workspace root inside the
    environment (e.g. ``""`` = workspace root, ``None`` = script's directory).
    """

    script_rel_path: str
    echo_label: str | None = None
    working_dir_rel: str | None = None
    stdin_text: str | None = None
    login_shell: bool = True


@dataclass(frozen=True)
class StepOutcome:
    """Result of one ``exec_script`` call."""

    status: str  # "succeeded" | "failed" | "canceled"
    exit_code: int | None = None
    captured_stdout: str = ""
    captured_stderr: str = ""


class ProvisioningCanceledError(RuntimeError):
    """Raised when environment provisioning is canceled before exec begins."""


# ================================================
# Protocol
# ================================================


class WorkingEnvironment(Protocol):
    """Execution context for workflow steps against a REE workspace.

    Implementations are context managers: provisioning on ``__enter__``,
    unconditional teardown on ``__exit__``.  Callers invoke ``exec_script``
    any number of times between enter and exit; ``put_file`` injects content
    directly into the running environment without a full re-sync; ``sync_out``
    must be called explicitly when mutations should be written back to the
    host workspace.
    """

    def exec_script(
        self,
        step: ScriptStep,
        *,
        log: LogSink,
        is_canceled: CancelCheck,
    ) -> StepOutcome: ...

    def put_file(self, rel_path: str, content: str) -> None: ...

    def sync_out(self, *, log: LogSink) -> bool: ...

    def __enter__(self) -> WorkingEnvironment: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None: ...
