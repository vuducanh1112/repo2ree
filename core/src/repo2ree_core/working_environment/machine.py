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
    """Uses the local Docker daemon. Supports kind=``"container"``."""

    def create_working_environment(
        self,
        spec: WorkingEnvironmentSpec,
        kind: str = "container",
    ) -> WorkingEnvironment:
        if kind != "container":
            raise ValueError(
                f"LocalMachine does not support kind={kind!r}; "
                "only 'container' is available"
            )
        from repo2ree_core.working_environment.docker_env import (
            DockerWorkingEnvironment,
        )

        return DockerWorkingEnvironment(spec)
