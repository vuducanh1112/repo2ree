from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import threading
import time
import warnings
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Final

from repo2ree_testbed.cli_cast import Printed, Stream
from repo2ree_testbed.stack.environments import (
    ENVIRONMENTS,
    MACHINE_CONTAINERS_VARIABLE,
    MACHINE_VARIABLE,
    MACHINE_WORKDIRS_VARIABLE,
    EnvironmentName,
    machine_exec,
)

STEP_SECONDS: Final = 3600


@dataclass(frozen=True)
class Done:
    status: int
    stdout: bytes
    stderr: str
    printed: tuple[Printed, ...] = ()


@dataclass
class Machine:
    environment: EnvironmentName
    container: str
    workdir: Path

    @classmethod
    def of_this_test(cls) -> Machine | None:
        machines = cls.all_of_this_test()
        return machines[0] if machines else None

    @classmethod
    def all_of_this_test(cls) -> tuple[Machine, ...]:
        if not os.environ.get(MACHINE_VARIABLE):
            return ()
        environment = EnvironmentName(os.environ[MACHINE_VARIABLE])
        containers = os.environ[MACHINE_CONTAINERS_VARIABLE].split(os.pathsep)
        workdirs = os.environ[MACHINE_WORKDIRS_VARIABLE].split(os.pathsep)
        if len(containers) != len(workdirs):
            raise ValueError(f"{len(containers)} machine containers but {len(workdirs)} workdirs")
        return tuple(
            cls(environment, container, Path(workdir)) for container, workdir in zip(containers, workdirs, strict=True)
        )

    def ree(
        self,
        root: Path,
        *words: str,
        stdin: bytes | None = None,
        variables: dict[str, str] | None = None,
        inside: bool = True,
        program: str = "ree",
    ) -> Done:
        if inside:
            command = machine_exec(ENVIRONMENTS[self.environment], self.container, [program, *words], variables, root)
        else:
            command = machine_exec(
                ENVIRONMENTS[self.environment], self.container, [program, "-C", str(root), *words], variables
            )
        printed: list[Printed] = []
        arrived = threading.Lock()

        def read(stream: Stream, source: IO[bytes]) -> None:
            while chunk := os.read(source.fileno(), 1 << 16):
                with arrived:
                    printed.append(Printed(time.time(), stream, chunk))

        def feed(sink: IO[bytes]) -> None:
            try:
                sink.write(stdin or b"")
            except BrokenPipeError:
                pass
            finally:
                sink.close()

        with subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as process:
            if process.stdin is None or process.stdout is None or process.stderr is None:
                raise RuntimeError("ree was started without its pipes")
            threads = [
                threading.Thread(target=feed, args=(process.stdin,), daemon=True),
                threading.Thread(target=read, args=("stdout", process.stdout), daemon=True),
                threading.Thread(target=read, args=("stderr", process.stderr), daemon=True),
            ]
            for thread in threads:
                thread.start()
            try:
                process.wait(timeout=STEP_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                raise
            finally:
                for thread in threads:
                    thread.join()
        stdout = b"".join(chunk.data for chunk in printed if chunk.stream == "stdout")
        stderr = b"".join(chunk.data for chunk in printed if chunk.stream == "stderr")
        return Done(process.returncode, stdout, stderr.decode(errors="replace"), tuple(printed))


def keep_histories(root: Path, kept: Path) -> None:
    kept.mkdir(parents=True, exist_ok=True)
    scopes = [root, *sorted(path for path in (root / "reviews").glob("*") if (path / ".git").is_dir())]
    try:
        with ExitStack() as locks:
            for scope in scopes:
                if (lock := scope / ".git/repo2ree.lock").is_file():
                    fcntl.flock(locks.enter_context(lock.open("rb")), fcntl.LOCK_EX)
            for scope in scopes:
                target = kept / scope.relative_to(root) / ".git"
                shutil.copytree(scope / ".git", target, symlinks=True, ignore=_without_lfs, dirs_exist_ok=True)
    except OSError as exc:
        shutil.rmtree(kept, ignore_errors=True)
        kept.mkdir(parents=True, exist_ok=True)
        warnings.warn(f"the history of {root.name} was not kept: {exc}", stacklevel=2)


def _without_lfs(directory: str, names: list[str]) -> list[str]:
    return ["lfs"] if Path(directory).name == ".git" and "lfs" in names else []
