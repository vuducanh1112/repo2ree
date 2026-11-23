from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.transitions import ReePreconditionError
from repo2ree_ree.model import LaunchDefinition
from repo2ree_ree.primitives import LaunchOption
from repo2ree_ree.receipt import Launched

OPTIONS_VARIABLE = "REE_LAUNCH_OPTIONS"
RECORD_PREFIX = ".workspace-launched-"
_RECORDER = 'printf "%s\\n%s\\n%s\\n" "$(uname -n)" "${SLURM_JOB_ID:-}" "${SLURM_STEP_ID:-}" > "$0"; exec "$@"'


@dataclass(frozen=True)
class Launch:
    script: str
    options: tuple[LaunchOption, ...] = ()


def declared_launch(definition: LaunchDefinition, workspace: Path, options: tuple[LaunchOption, ...] = ()) -> Launch:
    path = workspace / str(definition.launch_script_path)
    if not path.is_file():
        raise ReePreconditionError(f"the launch script is missing: {definition.launch_script_path}")
    if digest_file(path) != definition.launch_script_digest or path.stat().st_size != definition.launch_script_size:
        raise ReePreconditionError("the launch script does not match its definition")
    return Launch(script=str(definition.launch_script_path), options=options)


def launched_command(workspace: Path, launch: Launch, command: list[str]) -> tuple[list[str], Path]:
    record = f"{RECORD_PREFIX}{uuid.uuid4().hex}"
    options = ["env", f"{OPTIONS_VARIABLE}={' '.join(launch.options)}"] if launch.options else []
    return [*options, "sh", launch.script, "sh", "-c", _RECORDER, record, *command], workspace / record


def read_launched(record: Path) -> Launched | None:
    try:
        lines = record.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    finally:
        record.unlink(missing_ok=True)
    node, job, step = (*lines, "", "", "")[:3]
    if not node:
        return None
    return Launched(node=node, slurm_job_id=job or None, slurm_step_id=step or None)
