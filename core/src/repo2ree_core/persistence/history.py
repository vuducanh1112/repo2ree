"""Local Git snapshots of an REE, independent of its portable seal identity.

The layout selects state files; logs, staging and recorder storage stay outside
snapshots. Git plumbing records bytes without consulting ignores or filters.
Empty directories are recreated by ReeDirectory.ensure_dirs(), not Git.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.persistence.directory import UNREADABLE_DOCUMENT, ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.tooling import find_tool

INITIAL_REF = "refs/repo2ree/initial"
HISTORY_REF = "refs/heads/ree-history"
SELECTION_VERSION = 1


class HistoryCaptureError(RuntimeError):
    """Recording failed; existing REE files have not been rolled back."""


def _walk_failed(error: OSError) -> None:
    # Path.walk otherwise ignores unreadable directories, producing a snapshot
    # which appears successful while silently omitting part of the REE.
    raise HistoryCaptureError(f"Cannot enumerate REE files: {error}") from error


@dataclass(frozen=True)
class GitHistory:
    layout: ReeLayout
    executable: str

    def initialize(self) -> None:
        self._git("init", "--quiet", "--template=", "--initial-branch=ree-history")

    def _git(
        self, *args: str, data: bytes | None = None, index: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        # A caller's repository, index, identity or config must not redirect a
        # capture. The absolute git-dir also prevents parent-repository discovery.
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_ATTR_NOSYSTEM="1",
            GIT_AUTHOR_NAME="repo2ree",
            GIT_AUTHOR_EMAIL="repo2ree@localhost",
            GIT_COMMITTER_NAME="repo2ree",
            GIT_COMMITTER_EMAIL="repo2ree@localhost",
        )
        if index is not None:
            env["GIT_INDEX_FILE"] = str(index.resolve())
        result = subprocess.run(
            [
                self.executable,
                "--git-dir",
                str(self.layout.git_dir.resolve()),
                "--work-tree",
                str(self.layout.root.resolve()),
                "-c",
                f"core.hooksPath={os.devnull}",
                "-c",
                "commit.gpgSign=false",
                *args,
            ],
            cwd=self.layout.root,
            env=env,
            input=data,
            capture_output=True,
            check=False,
        )
        if check and result.returncode:
            raise HistoryCaptureError(result.stderr.decode(errors="replace").strip() or "Git capture failed")
        return result

    def head_snapshot(self) -> str | None:
        result = self._git("rev-parse", "--verify", "--quiet", f"{HISTORY_REF}^{{commit}}", check=False)
        if result.returncode == 1:
            return None
        if result.returncode:
            raise HistoryCaptureError("Cannot read REE history head")
        return result.stdout.decode().strip()

    def initial_snapshot(self) -> str | None:
        result = self._git("rev-parse", "--verify", "--quiet", f"{INITIAL_REF}^{{commit}}", check=False)
        if result.returncode == 1:
            return None
        if result.returncode:
            raise HistoryCaptureError("Cannot read the initial REE snapshot")
        return result.stdout.decode().strip()

    def _selected_files(self) -> list[Path]:
        paths: set[Path] = set()
        try:
            fixed = (*self.layout.history_files, *ReeDirectory(self.layout).history_artifacts())
        except UNREADABLE_DOCUMENT as exc:
            raise HistoryCaptureError(f"Cannot resolve declared history artifacts: {exc}") from exc
        for path in fixed:
            if path.exists() or path.is_symlink():
                paths.add(path)
        for root in self.layout.history_trees:
            if root.is_symlink():
                paths.add(root)
            elif root.exists():
                for directory, _directories, files in root.walk(on_error=_walk_failed):
                    paths.update(directory / name for name in files)
        if isinstance(self.layout, ReviewLayout) and self.layout.runs.exists():
            paths.update(self.layout.runs.glob("*.receipt.json"))
        # Never read a declared artifact through a directory symlink (including
        # one into recorder storage). Tree walks themselves do not follow links.
        for path in paths:
            relative = path.relative_to(self.layout.root)
            if relative.parts[0] == ".git" or any(
                parent.is_symlink()
                for parent in path.parents
                if parent != self.layout.root and self.layout.root in parent.parents
            ):
                raise HistoryCaptureError(f"Unsafe history artifact: {relative}")
        return sorted(path for path in paths if not self._internal_temporary(path))

    def _internal_temporary(self, path: Path) -> bool:
        """Recognize our staging names only for REE-owned persistence targets."""
        match = re.fullmatch(r"\.(.+)\.[0-9a-f]{32}\.tmp", path.name)
        if match is None:
            return False
        target = path.with_name(match[1])
        if target in (*self.layout.history_files, self.layout.sbom, self.layout.reproducibility_report):
            return True
        return isinstance(self.layout, ReviewLayout) and (
            target.is_relative_to(self.layout.receipts) or target.is_relative_to(self.layout.comparisons)
        )

    def _tree(self) -> str:
        with tempfile.TemporaryDirectory(dir=self.layout.git_dir, prefix="capture-") as temporary:
            index = Path(temporary) / "index"
            self._git("read-tree", "--empty", index=index)
            entries = bytearray()
            for path in self._selected_files():
                relative = path.relative_to(self.layout.root)
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    mode = "120000"
                    blob = self._git("hash-object", "-w", "--stdin", data=os.fsencode(path.readlink()))
                elif stat.S_ISREG(info.st_mode):
                    mode = "100755" if info.st_mode & 0o111 else "100644"
                    blob = self._git("hash-object", "-w", "--no-filters", "--", str(relative))
                else:
                    raise HistoryCaptureError(f"Cannot capture special file: {relative}")
                entries.extend(f"{mode} {blob.stdout.decode().strip()}\t".encode())
                entries.extend(os.fsencode(relative.as_posix()) + b"\0")
            self._git("update-index", "-z", "--index-info", data=bytes(entries), index=index)
            return self._git("write-tree", index=index).stdout.decode().strip()

    def _commit(
        self,
        tree: str,
        parent: str | None,
        *,
        operation: str,
        run_id: str | None = None,
        outcome: str | None = None,
        attempt_id: str | None = None,
    ) -> str:
        metadata = {
            "schema_version": 1,
            "selection_version": SELECTION_VERSION,
            "run_id": run_id,
            "outcome": outcome,
            "attempt_id": attempt_id,
        }
        message = f"{operation}\n\n{json.dumps(metadata)}\n"
        parents = ("-p", parent) if parent is not None else ()
        commit = self._git("commit-tree", tree, *parents, data=message.encode()).stdout.decode().strip()
        # Compare-and-swap also detects a non-cooperating writer moving the ref.
        self._git("update-ref", HISTORY_REF, commit, parent or "")
        self._git("read-tree", commit)
        return commit

    def capture(
        self,
        *,
        operation: str,
        run_id: str | None = None,
        outcome: str | None = None,
        attempt_id: str | None = None,
        reuse_unchanged: bool = False,
    ) -> str:
        """Capture selected state while the caller holds the operation lock."""
        parent = self._git("rev-parse", "--verify", "--quiet", f"{HISTORY_REF}^{{commit}}", check=False)
        if parent.returncode not in {0, 1}:
            raise HistoryCaptureError("Cannot read the REE history head")
        parent_id = parent.stdout.decode().strip() if parent.returncode == 0 else None
        tree = self._tree()
        if parent_id is not None:
            body = self._git("show", "-s", "--format=%b", parent_id).stdout.decode()
            try:
                metadata = json.loads(body)
            except ValueError:
                metadata = {}
            version = metadata.get("selection_version") if isinstance(metadata, dict) else None
            if version != SELECTION_VERSION:
                parent_id = self._commit(tree, parent_id, operation="migrate_history_selection")
            if reuse_unchanged:
                previous_tree = self._git("rev-parse", f"{parent_id}^{{tree}}").stdout.decode().strip()
                if tree == previous_tree:
                    return parent_id
        return self._commit(tree, parent_id, operation=operation, run_id=run_id, outcome=outcome, attempt_id=attempt_id)

    def capture_initial(self, *, existing: bool) -> str:
        if snapshot := self.initial_snapshot():
            return snapshot
        snapshot = self.capture(operation="baseline_existing_ree" if existing else "initialize_ree")
        self._git("update-ref", INITIAL_REF, snapshot)
        return snapshot


@contextmanager
def open_history(layout: ReeLayout) -> Iterator[GitHistory]:
    """Serialize cooperating processes before initializing or capturing this REE."""
    executable = find_tool("git")
    if executable is None:
        raise HistoryCaptureError("Git is required to initialize and capture an REE")
    if layout.git_dir.is_symlink() or (layout.git_dir.exists() and not layout.git_dir.is_dir()):
        raise HistoryCaptureError("REE history requires a local .git directory")
    try:
        layout.git_dir.mkdir(parents=True, exist_ok=True)
        with (layout.git_dir / "repo2ree.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            history = GitHistory(layout, executable)
            history.initialize()
            yield history
    except OSError as exc:
        raise HistoryCaptureError(f"REE history storage failed: {exc}") from exc
