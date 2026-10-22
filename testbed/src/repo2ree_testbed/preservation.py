"""Preserve full REE directories before their owners destroy them."""

from __future__ import annotations

import fcntl
import shutil
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Literal

from repo2ree_testbed.artifacts import case_dir, case_key, execution_id
from repo2ree_testbed.records import Record, write

type Consistency = Literal["cooperating_writers_locked", "fixture_teardown_without_history_lock", "container_paused"]


class Preserved(Record):
    source: str
    path: str | None = None
    status: Literal["recorded", "unavailable", "error"]
    reason: str | None = None
    consistency: Consistency | None = None

    def recorded(self, consistency: Consistency) -> Preserved:
        return self.but(status="recorded", consistency=consistency)

    def failed(self, reason: str) -> Preserved:
        return self.but(status="error", reason=reason)

    def unavailable(self, reason: str) -> Preserved:
        return self.but(status="unavailable", reason=reason)


class PreservationManifest(Record):
    schema_version: Literal[1] = 1
    execution_id: str
    nodeid: str
    started: float
    finished: float
    outcome: str
    repositories: tuple[Preserved, ...]
    trace_attribution: str = "arrival_window; late background spans remain in service traces"


class TestRecorder:
    __test__ = False

    def __init__(self, nodeid: str, *, directory: Path | None = None):
        self.nodeid = nodeid
        self.directory = directory if directory is not None else case_dir(nodeid)
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.repositories: list[Preserved] = []
        self.recorded: set[str] = set()
        self.started = time.time()

    def destination(self, name: str) -> Path:
        candidate = self.directory / "rees" / case_key(name)
        used = {item.path for item in self.repositories if item.path}
        index = 2
        while str(candidate.relative_to(self.directory)) in used:
            candidate = self.directory / "rees" / f"{case_key(name)}-{index}"
            index += 1
        return candidate

    def unavailable(self, source: str, reason: str) -> None:
        self.repositories.append(Preserved(source=source, status="unavailable", reason=reason))

    def local(self, root: Path) -> None:
        source = str(root.absolute())
        if source in self.recorded:
            return
        self.recorded.add(source)
        destination = self.destination(root.name)
        path = str(destination.relative_to(self.directory))
        self.repositories.append(self._copy(root, destination, Preserved(source=source, path=path, status="error")))

    def _copy(self, root: Path, destination: Path, preserved: Preserved) -> Preserved:
        try:
            if not root.exists():
                return preserved.unavailable("source removed before recording")
            if root.is_symlink():
                raise ValueError("REE root is a symlink")
            with ExitStack() as stack:
                scopes = [root, *sorted((root / "reviews").glob("*"))]
                locked = False
                for scope in scopes:
                    lock = scope / ".git/repo2ree.lock"
                    if (
                        lock.is_file()
                        and not lock.is_symlink()
                        and not scope.is_symlink()
                        and not (scope / ".git").is_symlink()
                    ):
                        handle = stack.enter_context(lock.open("rb"))
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = True
                shutil.copytree(root, destination, symlinks=True)
        except (OSError, ValueError) as exc:
            return preserved.failed(str(exc))
        return preserved.recorded("cooperating_writers_locked" if locked else "fixture_teardown_without_history_lock")

    def workbench(self, container: str) -> None:
        destination = self.destination("workbench")
        path = str(destination.relative_to(self.directory))
        preserved = Preserved(source=container, path=path, status="error")
        paused = False
        try:
            state = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Paused}}", container],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if state != "true":
                subprocess.run(["docker", "pause", container], check=True, capture_output=True)
                paused = True
            destination.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["docker", "cp", f"{container}:/ree/.", str(destination)],
                check=True,
                capture_output=True,
            )
            preserved = preserved.recorded("container_paused")
        except (OSError, subprocess.CalledProcessError) as exc:
            preserved = preserved.failed(str(exc))
        finally:
            if paused:
                result = subprocess.run(["docker", "unpause", container], check=False, capture_output=True)
                if result.returncode:
                    preserved = preserved.failed("Failed to unpause workbench after recording")
            self.repositories.append(preserved)

    def discover(self, root: Path) -> None:
        for directory, dirs, files in root.walk(follow_symlinks=False):
            if ".git" in dirs and "ree.json" in files:
                self.local(directory)
                dirs.clear()  # Reviews are included in the author directory copy.
            else:
                dirs[:] = [name for name in dirs if name not in {".git", "workspace", "upstream", "node_modules"}]

    def finish(self, outcome: str) -> None:
        manifest = PreservationManifest(
            execution_id=execution_id(),
            nodeid=self.nodeid,
            started=self.started,
            finished=time.time(),
            outcome=outcome,
            repositories=tuple(self.repositories),
        )
        write(self.directory / "manifest.json", manifest)
