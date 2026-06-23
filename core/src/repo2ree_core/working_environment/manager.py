"""Convenience factory: resolve a (machine, kind) selector to a WorkingEnvironment.

Callers import :func:`acquire` and use it as a context manager::

    with acquire(workspace, run_id, log=log) as we:
        outcome = we.exec_script(step, log=log, is_canceled=is_canceled)
        we.sync_out(log=log)

``machine`` defaults to ``"local"`` (the local Docker daemon).
``kind`` defaults to ``"container"`` (the only supported kind today).
Both parameters are intentional hooks for future machine/kind selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from repo2ree_core.working_environment.base import (
    CancelCheck,
    LogSink,
    ProvisioningCanceledError,
    ScriptStep,
    StepOutcome,
    WorkingEnvironment,
    WorkingEnvironmentSpec,
)
from repo2ree_core.working_environment.machine import LocalMachine

# Deferred to runtime: importing domain.env_entry at module load pulls in
# domain → experiment → run → working_environment, a cycle when this package is
# imported first. Only ``acquire`` needs the concrete class, at call time.
if TYPE_CHECKING:
    from repo2ree_core.domain.env_entry import EnvEntry

# ================================================
# Public API
# ================================================


# Maps an EnvEntry discriminator to the WorkingEnvironment kind a Machine
# knows how to provision. Adding a substrate is: a new EnvEntry, an entry
# here, and a Machine branch.
_ENTRY_KIND_TO_ENV_KIND = {
    "container": "container",
    "local": "native",
    "custom": "custom",
    "vm": "vm",
    # legacy v1 kinds kept for any stale in-memory objects
    "docker": "container",
    "native": "native",
    "singularity": "singularity",
}


def acquire(
    workspace_path: Path,
    run_id: str,
    *,
    log: LogSink,
    is_canceled: CancelCheck | None = None,
    image: str | None = None,
    entry: EnvEntry | None = None,
    machine: str = "local",
    kind: str | None = None,
) -> WorkingEnvironment:
    """Return a WorkingEnvironment for *workspace_path* / *run_id*.

    The returned object is a context manager.  ``__enter__`` provisions the
    environment (creates the container and copies the workspace in).
    ``__exit__`` tears it down unconditionally.  Call ``sync_out()``
    explicitly before exit when mutations need to be written back to the
    host workspace.

    Args:
        workspace_path: Absolute path to the materialized workspace directory.
        run_id:         Unique identifier for this run; used in container names.
        log:            Log sink for provisioning steps (create, cp, start, rm).
        image:          Override the base image; ``None`` → implementation default.
        entry:          Runtime entry recipe; selects the substrate (kind).
                        ``None`` → Docker container (the historical default).
        machine:        Placement selector (``"local"`` only for now).
        kind:           Explicit environment kind override; normally derived
                        from *entry*.
    """
    if machine != "local":
        raise ValueError(f"Machine {machine!r} is not supported yet; only 'local' is available")
    from repo2ree_core.domain.env_entry import ContainerEntry

    if kind is None:
        kind = _ENTRY_KIND_TO_ENV_KIND.get(entry.kind, "container") if entry is not None else "container"
    activate = entry.activate if entry is not None and hasattr(entry, "activate") else ""
    engine = entry.engine if isinstance(entry, ContainerEntry) else "docker"
    enter_script = getattr(entry, "enter_script", "")
    spec = WorkingEnvironmentSpec(
        workspace_path=workspace_path,
        run_id=run_id,
        log=log,
        is_canceled=is_canceled,
        image=image,
        activate=activate,
        engine=engine,
        enter_script=enter_script,
    )
    we = LocalMachine().create_working_environment(spec, kind=kind)
    return we


def run_workspace_script(
    *,
    workspace: Path,
    script_rel_path: str,
    run_id: str,
    log: LogSink,
    is_canceled: CancelCheck,
    echo_label: str | None = None,
    sync_out_on_success: bool = False,
) -> StepOutcome:
    """Run a single script in the workspace environment and return its outcome.

    Provisions a fresh WorkingEnvironment, executes *script_rel_path* with a
    login shell, optionally syncs file mutations back to the host on success,
    then tears the environment down unconditionally.
    """
    try:
        with acquire(workspace, run_id, log=log, is_canceled=is_canceled) as we:
            step = ScriptStep(
                script_rel_path=script_rel_path,
                echo_label=echo_label,
                login_shell=True,
            )
            outcome = we.exec_script(step, log=log, is_canceled=is_canceled)
            if sync_out_on_success and outcome.status == "succeeded":
                if not we.sync_out(log=log):
                    return StepOutcome(
                        "failed",
                        outcome.exit_code,
                        outcome.captured_stdout,
                        outcome.captured_stderr,
                    )
        return outcome
    except ProvisioningCanceledError:
        return StepOutcome("canceled")
