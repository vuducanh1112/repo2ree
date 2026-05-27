"""Working Environment abstraction for REE workflow execution.

The central export is :func:`acquire`, which returns a :class:`WorkingEnvironment`
context manager.  All other names are re-exported for callers that need the
types (e.g. to annotate callbacks or write tests against the protocol).

Machine and kind implementations live in sibling modules:
  docker_env  — DockerWorkingEnvironment  (kind="container")
  machine     — LocalMachine              (machine="local")
"""

from repo2ree_core.working_environment.base import (
    CancelCheck,
    LogSink,
    ProvisioningCanceledError,
    ScriptStep,
    StepOutcome,
    WorkingEnvironment,
)
from repo2ree_core.working_environment.manager import acquire, run_workspace_script

__all__ = [
    "CancelCheck",
    "LogSink",
    "ProvisioningCanceledError",
    "ScriptStep",
    "StepOutcome",
    "WorkingEnvironment",
    "acquire",
    "run_workspace_script",
]
