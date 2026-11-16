"""Running `ree` against the REEs of the store this workbench serves, each in a process of its own.

A workbench serves a store: it keeps one directory per REE beneath its root and runs each command
against the directory of the REE the request names.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from repo2ree_protocol.build import BuildInfo
from repo2ree_protocol.machine import MachineFacts
from repo2ree_telemetry.spans import current_traceparent

# An REE id names a directory in the store: one path segment, nothing a shell or a path could misread.
_REE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


def ree_directory(store: Path, ree_id: str) -> Path:
    """The directory of ``ree_id`` in ``store``; refuses an id that is not one plain path segment."""
    if not _REE_ID.fullmatch(ree_id) or ree_id in {".", ".."}:
        raise ValueError(f"not an REE id: {ree_id!r}")
    return store / ree_id


class LocalCli:
    """Run executor processes locally, each against one REE of the store."""

    def __init__(
        self,
        root: Path,
        cli_path: str = "ree",
        *,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.cli_path = cli_path
        # What every executor is started with besides this process's own environment (the tools).
        self.tools = environment or {}

    def ree_root(self, ree_id: str) -> Path:
        """The root an REE's commands run against: its directory in the store."""
        return ree_directory(self.root, ree_id)

    def delete_ree(self, ree_id: str) -> None:
        root = self.ree_root(ree_id)
        if root.exists():
            shutil.rmtree(root)

    def environment(self, root: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
        environment = {**os.environ, **self.tools}
        environment.update(extra or {})
        if traceparent := current_traceparent():
            environment["TRACEPARENT"] = traceparent
        return environment

    def build_info(self) -> BuildInfo:
        """Ask the configured executor to identify itself, tolerating older binaries."""
        try:
            result = subprocess.run(
                [self.cli_path, "build-info"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
                env=self.environment(self.root),
            )
            if result.returncode == 0:
                return BuildInfo.model_validate(json.loads(result.stdout))
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return BuildInfo()

    def machine(self) -> MachineFacts:
        """The machine the REEs' scripts run on, as the executor reports it; nothing known when it cannot say."""
        try:
            result = subprocess.run(
                [self.cli_path, "machine"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=self.environment(self.root),
            )
            if result.returncode == 0:
                return MachineFacts.model_validate_json(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return MachineFacts()

    def at(self, root: Path, argv: list[str]) -> list[str]:
        """The command line that runs ``argv`` against the REE at ``root``."""
        return [self.cli_path, "-C", str(root), *argv]

    def run(self, root: Path, argv: list[str], timeout: int) -> str:
        """Run an executor subcommand against ``root``; its stdout."""
        result = subprocess.run(
            self.at(root, argv),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self.environment(root),
        )
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "(no output)"
            raise RuntimeError(f"executor {argv[0]!r} failed (exit {result.returncode}): {detail}")
        return result.stdout

    def exec_query_stream(
        self, argv: list[str], timeout: int = 30, *, ree_id: str, stdin: bytes | None = None
    ) -> Iterator[bytes]:
        root = self.ree_root(ree_id)
        result = subprocess.run(
            self.at(root, argv),
            check=False,
            input=stdin,
            capture_output=True,
            timeout=timeout,
            env=self.environment(root),
        )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")
        view = memoryview(result.stdout)
        for offset in range(0, len(view), 256 * 1024):
            yield bytes(view[offset : offset + 256 * 1024])

    def exec_query_to_file(self, argv: list[str], target: Path, timeout: int = 600, *, ree_id: str) -> None:
        """Run an executor query with its stdout written straight to ``target``, never held in memory."""
        root = self.ree_root(ree_id)
        with target.open("wb") as output:
            result = subprocess.run(
                self.at(root, argv),
                check=False,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=timeout,
                env=self.environment(root),
            )
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip() or "(no stderr)"
            raise RuntimeError(f"executor query {argv!r} failed (exit {result.returncode}): {detail}")

    def copy_in(self, source_path: str, workbench_path: str, *, ree_id: str) -> None:
        destination = self._resolve_destination(self.ree_root(ree_id), workbench_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copyfile(source_path, temporary)
            Path(temporary).replace(destination)
        finally:
            Path(temporary).unlink(missing_ok=True)

    @staticmethod
    def _resolve_destination(root: Path, requested: str) -> Path:
        path = PurePosixPath(requested)
        if ".." in path.parts:
            raise ValueError("workbench path must not contain '..'")
        if path.is_absolute():
            try:
                relative = path.relative_to("/ree")
            except ValueError as exc:
                raise ValueError("absolute workbench paths must be below /ree") from exc
        else:
            relative = path
        destination = root.joinpath(*relative.parts)
        resolved_parent = destination.parent.resolve()
        if not resolved_parent.is_relative_to(root):
            raise ValueError("workbench path escapes the configured root")
        return resolved_parent / destination.name
