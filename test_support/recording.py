"""Preserve full REE directories before their owners destroy them."""

from __future__ import annotations

import fcntl
import json
import shutil
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from test_support.artifacts import case_dir, case_key, execution_id


class TestRecorder:
    __test__ = False

    def __init__(self, nodeid: str, *, directory: Path | None = None):
        self.nodeid = nodeid
        self.directory = directory if directory is not None else case_dir(nodeid)
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.repositories: list[dict[str, Any]] = []
        self.recorded: set[str] = set()
        self.started = time.time()

    def destination(self, name: str) -> Path:
        candidate = self.directory / "rees" / case_key(name)
        used = {item["path"] for item in self.repositories if "path" in item}
        index = 2
        while str(candidate.relative_to(self.directory)) in used:
            candidate = self.directory / "rees" / f"{case_key(name)}-{index}"
            index += 1
        return candidate

    def local(self, root: Path) -> None:
        source = str(root.absolute())
        if source in self.recorded:
            return
        self.recorded.add(source)
        destination = self.destination(root.name)
        record: dict[str, Any] = {"source": source, "path": str(destination.relative_to(self.directory))}
        self.repositories.append(record)
        try:
            if not root.exists():
                record.update(status="unavailable", reason="source removed before recording")
                return
            if root.is_symlink():
                raise ValueError("REE root is a symlink")
            with ExitStack() as stack:
                # Match operation ordering: author lock, then review locks.
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
            record.update(
                status="recorded",
                consistency="cooperating_writers_locked" if locked else "fixture_teardown_without_history_lock",
            )
        except (OSError, ValueError) as exc:
            record.update(status="error", reason=str(exc))

    def workbench(self, container: str) -> None:
        """Freeze writers while docker copies /ree, including hidden Git storage.

        This can retain a failed operation's intermediate state; it does not
        claim the directory represents a completed operation boundary.
        """
        destination = self.destination("workbench")
        record: dict[str, Any] = {"source": container, "path": str(destination.relative_to(self.directory))}
        self.repositories.append(record)
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
            record.update(status="recorded", consistency="container_paused")
        except (OSError, subprocess.CalledProcessError) as exc:
            record.update(status="error", reason=str(exc))
        finally:
            if paused:
                result = subprocess.run(["docker", "unpause", container], check=False, capture_output=True)
                if result.returncode:
                    record.update(status="error", reason="Failed to unpause workbench after recording")

    def discover(self, root: Path) -> None:
        """Fallback for local tests constructing REEs directly under tmp_path."""
        for directory, dirs, files in root.walk(follow_symlinks=False):
            if ".git" in dirs and "ree.json" in files:
                self.local(directory)
                dirs.clear()  # Reviews are included in the author directory copy.
            else:
                dirs[:] = [name for name in dirs if name not in {".git", "workspace", "upstream", "node_modules"}]

    def finish(self, outcome: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "execution_id": execution_id(),
                    "nodeid": self.nodeid,
                    "started": self.started,
                    "finished": time.time(),
                    "outcome": outcome,
                    "repositories": self.repositories,
                    "trace_attribution": "arrival_window; late background spans remain in service traces",
                },
                indent=2,
            )
            + "\n"
        )
