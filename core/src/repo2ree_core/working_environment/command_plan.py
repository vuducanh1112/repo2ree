"""Canonical shell-command builders and the lifecycle projection for substrates.

This module is the single source of truth for the exact commands a substrate
runs. The :class:`WorkingEnvironment` implementations build their argv through
the ``*_argv`` helpers here, and :func:`describe_plan` projects those same
helpers — with placeholder tokens standing in for run-scoped values — into a
:class:`CommandPlan` for display. Because execution and display call the same
builders, the shown commands cannot drift from what actually runs.

The plan is a pure function of an :class:`EnvEntry` (the substrate kind plus its
declared params) and the runnable command convention; it needs no running
workbench and no real run id.
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from repo2ree_core.container.run_script import (
    CONTAINER_WORKSPACE,
    build_exec_command,
    container_name,
    docker_cp_in_argv,
    docker_cp_out_argv,
    docker_create_argv,
    docker_exec_argv,
    docker_load_argv,
    docker_rm_argv,
    docker_rmi_argv,
    docker_start_argv,
    docker_tag_argv,
    env_export_segments,
    experiment_script_rel,
    format_argv,
    runtime_image_tag,
)

# Deferred to runtime (see manager.py): importing domain.env_entry at module
# load would pull domain → experiment → run → working_environment, a cycle when
# this package is imported first. describe_plan needs the classes at call time.
if TYPE_CHECKING:
    from repo2ree_core.domain.env_entry import (
        ContainerEntry,
        EnvEntry,
        LocalEntry,
        PhaseOverrides,
    )


# ================================================
# Canonical argv builders — Native
# ================================================


def native_shell_command(
    *,
    activate: str,
    working_dir: str,
    script_abs: str,
    echo_label: str | None = None,
    script_rel: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    """The ``set -e; …`` snippet a native run feeds to ``bash -c``."""
    segments = ["set -e", *env_export_segments(env)]
    activate = activate.strip()
    if activate:
        segments.append(activate)
    segments.append(f"cd {shlex.quote(working_dir)}")
    if echo_label is not None and script_rel is not None:
        segments.append(f"echo '--- {echo_label} ({shlex.quote(script_rel)}) ---'")
    segments.append(f"source {shlex.quote(script_abs)}")
    return "; ".join(segments)


def native_exec_argv(shell_command: str, *, login_shell: bool) -> list[str]:
    return ["bash", "--login", "-c", shell_command] if login_shell else ["bash", "-c", shell_command]


# ================================================
# Plan model
# ================================================


class PlannedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display: str  # the exact shell line, with placeholder tokens for run-scoped values
    note: str = ""  # optional condition or explanation


class CommandPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["pre", "exec", "post"]
    label: str
    commands: list[PlannedCommand] = Field(default_factory=list)


class CommandPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    placeholders: dict[str, str] = Field(default_factory=dict)
    phases: list[CommandPhase] = Field(default_factory=list)
    note: str = ""  # set when a substrate has no command projection yet


# ================================================
# Projection
# ================================================

# Quote-safe placeholder tokens for the run-scoped values that only exist at
# run time. Kept identifier-like so they render without shell quoting.
_RUN_ID = "RUN_ID"
_WORKSPACE = "WORKSPACE"
_ARTIFACT = "ARTIFACT"
_LOADED_REF = "LOADED_REF"

_PLACEHOLDERS = {
    _RUN_ID: "unique id of this run",
    _WORKSPACE: "host path of the materialized workspace",
    _ARTIFACT: "the built runtime image tarball",
    _LOADED_REF: "image ref Docker reports after loading the tarball",
}


def _cmd(argv: list[str], note: str = "") -> PlannedCommand:
    return PlannedCommand(display=format_argv(argv), note=note)


# A substrate is a *preset*: it generates the default phase commands, and the
# author may layer overrides onto them. The plan is where the two meet — defaults
# synthesized below, overrides spliced in by _apply_overrides — so both the UI
# preview and the executor read one projection.
#
# The override semantics mirror run.run_runnable exactly:
#   provision  — runs in-substrate after the preset's setup    → appended to "pre"
#   exec       — dispatches the per-run command in its place    → replaces "exec"
#   teardown   — runs in-substrate before the preset's teardown → prepended to "post"
# Author scripts are rendered by path (like the custom driver), not expanded to
# the exact in-substrate argv.


def _exec_override_command(script: str) -> PlannedCommand:
    return PlannedCommand(
        display=f"sh {shlex.quote(script)}",
        note="exec override: dispatches the per-run command (R2R_COMMAND / R2R_RUN_ID in env)",
    )


def _hook_command(script: str, phase_label: str) -> PlannedCommand:
    return PlannedCommand(
        display=f"sh {shlex.quote(script)}",
        note=f"{phase_label} override: runs inside the substrate",
    )


def _apply_overrides(plan: CommandPlan, overrides: PhaseOverrides) -> CommandPlan:
    """Layer the author's phase overrides onto a preset's default plan.

    Empty overrides leave the plan untouched, so a substrate with no overrides
    renders exactly the preset default.
    """
    if not overrides.any_set():
        return plan
    provision, exec_, teardown = (
        overrides.provision.strip(),
        overrides.exec.strip(),
        overrides.teardown.strip(),
    )
    new_phases = []
    for phase in plan.phases:
        if phase.id == "exec" and exec_:
            commands = [_exec_override_command(exec_)]
        elif phase.id == "pre" and provision:
            commands = [*phase.commands, _hook_command(provision, "provision")]
        elif phase.id == "post" and teardown:
            commands = [_hook_command(teardown, "teardown"), *phase.commands]
        else:
            commands = phase.commands
        new_phases.append(CommandPhase(id=phase.id, label=phase.label, commands=commands))
    return plan.model_copy(update={"phases": new_phases})


def _container_plan(entry: ContainerEntry) -> CommandPlan:
    engine = entry.engine
    # The plan renders Docker-compatible verbs (load/create/start/cp/exec/rm).
    # Docker and Podman honour them; Apptainer does not — showing them would be
    # confidently wrong, so flag it as unimplemented instead (matches machine.py).
    if engine == "apptainer":
        return CommandPlan(
            kind=f"container({engine})",
            note="The Apptainer container engine is not implemented yet.",
        )
    container = container_name(_RUN_ID)
    image = runtime_image_tag(_RUN_ID)
    script_rel = experiment_script_rel(_RUN_ID)
    script_in_container = CONTAINER_WORKSPACE / script_rel
    exec_command = build_exec_command(
        script_in_container,
        script_rel,
        echo_label=None,
        working_dir=CONTAINER_WORKSPACE,
    )
    return CommandPlan(
        kind=f"container({engine})",
        placeholders={k: _PLACEHOLDERS[k] for k in (_ARTIFACT, _LOADED_REF, _WORKSPACE, _RUN_ID)},
        phases=[
            CommandPhase(
                id="pre",
                label="Setup",
                commands=[
                    _cmd(docker_load_argv(engine, _ARTIFACT)),
                    _cmd(docker_tag_argv(engine, _LOADED_REF, image)),
                    _cmd(
                        docker_create_argv(
                            engine,
                            container=container,
                            image=image,
                            sock_mount=engine == "docker",
                            extra_args=entry.create_args or None,
                        )
                    ),
                    _cmd(docker_cp_in_argv(engine, workspace=_WORKSPACE, container=container)),
                    _cmd(docker_start_argv(engine, container)),
                ],
            ),
            CommandPhase(
                id="exec",
                label="Run",
                commands=[
                    _cmd(
                        docker_exec_argv(engine, container=container, exec_command=exec_command, login_shell=False),
                        note=f"{script_rel} holds the activation/experiment command",
                    ),
                ],
            ),
            CommandPhase(
                id="post",
                label="Teardown",
                commands=[
                    _cmd(
                        docker_cp_out_argv(engine, container=container, workspace=_WORKSPACE),
                        note="only when the runnable declares file outputs",
                    ),
                    _cmd(docker_rm_argv(engine, container)),
                    _cmd(docker_rmi_argv(engine, image=image, loaded_ref=_LOADED_REF)),
                ],
            ),
        ],
    )


def _local_plan(entry: LocalEntry) -> CommandPlan:
    script_abs = f"{_WORKSPACE}/{experiment_script_rel(_RUN_ID)}"
    shell_command = native_shell_command(
        activate=entry.activate,
        working_dir=_WORKSPACE,
        script_abs=script_abs,
    )
    return CommandPlan(
        kind="local",
        placeholders={k: _PLACEHOLDERS[k] for k in (_WORKSPACE, _RUN_ID)},
        phases=[
            CommandPhase(id="pre", label="Setup", commands=[]),
            CommandPhase(
                id="exec",
                label="Run",
                commands=[
                    _cmd(
                        native_exec_argv(shell_command, login_shell=False),
                        note=f"{experiment_script_rel(_RUN_ID)} holds the activation/experiment command",
                    ),
                ],
            ),
            CommandPhase(id="post", label="Teardown", commands=[]),
        ],
    )


def _custom_plan(enter_script: str) -> CommandPlan:
    return CommandPlan(
        kind="custom",
        placeholders={k: _PLACEHOLDERS[k] for k in (_WORKSPACE, _RUN_ID)},
        phases=[
            CommandPhase(
                id="pre",
                label="Setup (optional)",
                commands=[PlannedCommand(display=f"{enter_script}/pre (if present)", note="provision substrate")],
            ),
            CommandPhase(
                id="exec",
                label="Run",
                commands=[
                    PlannedCommand(
                        display=f"{enter_script}/exec  # or {enter_script} if single-file",
                        note="runs $R2R_COMMAND inside the substrate",
                    )
                ],
            ),
            CommandPhase(
                id="post",
                label="Teardown (optional)",
                commands=[
                    PlannedCommand(display=f"{enter_script}/post (if present)", note="collect outputs, teardown")
                ],
            ),
        ],
        note=f"Custom driver: {enter_script}",
    )


def describe_plan(entry: EnvEntry) -> CommandPlan:
    """Project *entry* into the exact command lifecycle, for display.

    The argv shown is built by the very helpers the executors use, so it stays
    in lockstep with what runs. Run-scoped values appear as placeholder tokens
    (see :attr:`CommandPlan.placeholders`).
    """
    from repo2ree_core.domain.env_entry import ContainerEntry, CustomEntry, LocalEntry

    if isinstance(entry, ContainerEntry):
        return _apply_overrides(_container_plan(entry), entry.overrides)
    if isinstance(entry, LocalEntry):
        return _apply_overrides(_local_plan(entry), entry.overrides)
    if isinstance(entry, CustomEntry):
        # custom is already the all-overridden case; its driver *is* the phases.
        return _custom_plan(entry.enter_script)
    # VM substrate is not implemented yet.
    return CommandPlan(kind=entry.kind, note="This substrate is not implemented yet.")


__all__ = [
    "CommandPhase",
    "CommandPlan",
    "PlannedCommand",
    "describe_plan",
    "native_exec_argv",
    "native_shell_command",
]
