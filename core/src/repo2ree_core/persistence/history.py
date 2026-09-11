"""Local Git snapshots of an REE, independent of its portable seal identity.

The REE is the working tree; only its root .git directory is excluded. Git
plumbing records bytes without consulting ignore rules, filters or hooks.
Empty directories are recreated by ReeDirectory.ensure_dirs(), not Git.
"""

from __future__ import annotations

import fcntl
import os
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.tooling import find_tool

INITIAL_REF = "refs/repo2ree/initial"
HISTORY_REF = "refs/heads/ree-history"


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

    def initial_snapshot(self) -> str | None:
        result = self._git("rev-parse", "--verify", "--quiet", f"{INITIAL_REF}^{{commit}}", check=False)
        if result.returncode == 1:
            return None
        if result.returncode:
            raise HistoryCaptureError("Cannot read the initial REE snapshot")
        return result.stdout.decode().strip()

    def capture(self, *, operation: str) -> str:
        """Capture current files and publish one commit, while the caller holds the lock."""
        parent = self._git("rev-parse", "--verify", "--quiet", f"{HISTORY_REF}^{{commit}}", check=False)
        if parent.returncode not in {0, 1}:
            raise HistoryCaptureError("Cannot read the REE history head")
        # A private index prevents a failed capture from leaving half-staged
        # files for the next one. No git add: it honors ignores and filters.
        with tempfile.TemporaryDirectory(dir=self.layout.git_dir, prefix="capture-") as temporary:
            index = Path(temporary) / "index"
            self._git("read-tree", "--empty", index=index)
            entries = bytearray()
            for directory, directories, files in self.layout.root.walk(on_error=_walk_failed):
                if directory == self.layout.root:
                    directories[:] = [name for name in directories if name != ".git"]
                for name in sorted(files):
                    path = directory / name
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
            tree = self._git("write-tree", index=index).stdout.decode().strip()
        parents = ("-p", parent.stdout.decode().strip()) if parent.returncode == 0 else ()
        commit = self._git("commit-tree", tree, *parents, data=f"{operation}\n".encode()).stdout.decode().strip()
        self._git("update-ref", HISTORY_REF, commit)
        # Keep the ordinary working-tree index in sync for useful git status.
        self._git("read-tree", commit)
        return commit

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
