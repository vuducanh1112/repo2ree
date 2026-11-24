from __future__ import annotations

import multiprocessing
import shutil
import subprocess
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo2ree_testbed.artifacts import execution_id, run_dir
from repo2ree_testbed.cli_machine import Machine
from repo2ree_testbed.exercise import Exercise
from repo2ree_testbed.exercise_case import ExerciseCase, measure
from repo2ree_testbed.exercise_cli import covered_machine_ree, machine_ree
from repo2ree_testbed.exercise_verdict import Trace, judge
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName, machine_command
from repo2ree_testbed.stack.process import wait_until
from repo2ree_testbed.stack.services import workbench_host

type Stage = Literal["coverage", "baseline"]
MEASURED = ENVIRONMENTS[EnvironmentName.BARE_MEASURED]


@dataclass(frozen=True)
class Measured:
    case: ExerciseCase
    arcs: int
    files: int
    differences: tuple[str, ...]


@contextmanager
def machine_for(name: str, mounted: Path) -> Iterator[Machine]:
    state = mounted / ".machines" / name
    state.mkdir(parents=True, exist_ok=True)
    ready = state / "ready"
    container = f"{execution_id()[:12]}-{name}"
    command = machine_command(
        MEASURED,
        {},
        ["sh", "-c", 'touch "$0" && exec sleep infinity', str(ready)],
        container=container,
        owner=execution_id(),
        network=workbench_host()[1],
        mounts=(mounted,),
    )
    with (state / "machine.log").open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

        def started() -> bool:
            if process.poll() is not None:
                raise RuntimeError(f"the machine {container} exited before it was ready (log: {log.name})")
            return ready.exists()

        try:
            wait_until(f"the machine {container}", started)
            yield Machine(MEASURED.name, container, mounted)
        finally:
            subprocess.run(["docker", "rm", "--force", container], capture_output=True, check=False)
            process.wait()


def on_machine(machine: Machine) -> Callable[[Exercise, Path, bool], Trace]:
    def judged(exercise: Exercise, workdir: Path, measured: bool) -> Trace:
        return judge(
            exercise, workdir, measured=measured, run=machine_ree(machine), measuring=covered_machine_ree(machine)
        )

    return judged


def _measure(case: ExerciseCase, workdir: Path, directory: Path) -> Measured:
    shutil.rmtree(workdir, ignore_errors=True)
    with machine_for(f"measure-{case.digest}", workdir) as machine:
        measured, differences = measure(case, workdir, directory, covered_machine_ree(machine))
    files = measured.coverage.files if measured.coverage else {}
    return Measured(
        case=measured,
        arcs=sum(len(file.arcs) for file in files.values()),
        files=len(files),
        differences=tuple(differences),
    )


def measure_all(found: Sequence[ExerciseCase], directory: Path, stage: Stage, jobs: int) -> Iterator[Measured]:
    root = run_dir() / "exercises" / execution_id() / stage
    if jobs <= 1:
        yield from (_measure(case, root / case.digest, directory) for case in found)
        return
    with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context("forkserver")) as pool:
        running = [pool.submit(_measure, case, root / case.digest, directory) for case in found]
        yield from (done.result() for done in as_completed(running))
