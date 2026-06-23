"""Machine abstraction — where a WorkingEnvironment is hosted.

A Machine represents a placement target: the local Docker daemon today,
a remote host or cloud node in the future.  It acts as a factory for
WorkingEnvironments of a requested *kind* (``"container"`` now, ``"vm"``
later).

The two axes are orthogonal: a machine of any kind can produce environments
of any kind it supports.  Adding a new machine type (``RemoteMachine``) or
a new environment kind (``VmWorkingEnvironment``) is independent work.
"""

from __future__ import annotations

from typing import Protocol

from repo2ree_core.working_environment.base import (
    WorkingEnvironment,
    WorkingEnvironmentSpec,
)

# ================================================
# Protocol
# ================================================


class Machine(Protocol):
    """Factory for WorkingEnvironments.

    A Machine knows how to provision a WorkingEnvironment of a requested
    *kind* on its target (local daemon, remote host, etc.).  It should
    raise ``ValueError`` for unsupported kinds.
    """

    def create_working_environment(
        self,
        spec: WorkingEnvironmentSpec,
        kind: str = "container",
    ) -> WorkingEnvironment: ...


# ================================================
# Implementations
# ================================================


class LocalMachine:
    """Hosts WorkingEnvironments locally.

    Supports ``kind="container"`` (Docker/Podman) and ``kind="native"`` (the
    workbench itself) and ``kind="custom"`` (author-supplied phased scripts).
    The Apptainer container engine and ``"vm"`` are recognized but not yet
    implemented.
    """

    def create_working_environment(
        self,
        spec: WorkingEnvironmentSpec,
        kind: str = "container",
    ) -> WorkingEnvironment:
        if kind == "container":
            # DockerWorkingEnvironment drives the engine through Docker-compatible
            # verbs (create/start/cp/exec/rm). Docker and Podman support these;
            # Apptainer does not — it needs its own driver, not yet written.
            if spec.engine == "apptainer":
                raise NotImplementedError(
                    "Apptainer container engine is declared but not yet implemented; "
                    "only 'docker' and 'podman' run today"
                )
            from repo2ree_core.working_environment.docker_env import (
                DockerWorkingEnvironment,
            )

            return DockerWorkingEnvironment(spec)
        if kind == "native":
            from repo2ree_core.working_environment.native_env import (
                NativeWorkingEnvironment,
            )

            return NativeWorkingEnvironment(spec)
        if kind == "custom":
            from repo2ree_core.working_environment.scripted_env import (
                ScriptedWorkingEnvironment,
            )

            return ScriptedWorkingEnvironment(spec)
        if kind in ("singularity", "vm"):
            raise NotImplementedError(
                f"Substrate {kind!r} is declared but not yet implemented; "
                "only 'container', 'native', and 'custom' run today"
            )
        raise ValueError(f"LocalMachine does not support kind={kind!r}")
