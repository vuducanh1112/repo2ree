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
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from repo2ree_core.persistence.capture_policy import capture_plan
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.persistence.lfs import LfsPointer, store_payload
from repo2ree_protocol.history import SELECTION_VERSION
from repo2ree_protocol.tools import find_tool

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
        self.git("init", "--quiet", "--template=", "--initial-branch=ree-history")

    def git(
        self,
        *args: str,
        data: bytes | None = None,
        index: Path | None = None,
        check: bool = True,
        output: BinaryIO | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        # A caller's repository, index, identity or config must not redirect a
        # capture. The absolute git-dir also prevents parent-repository discovery.
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_ATTR_NOSYSTEM="1",
            GIT_NO_REPLACE_OBJECTS="1",
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
            stdout=output if output is not None else subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode:
            raise HistoryCaptureError(result.stderr.decode(errors="replace").strip() or "Git capture failed")
        return result

    def head_snapshot(self) -> str | None:
        result = self.git("rev-parse", "--verify", "--quiet", f"{HISTORY_REF}^{{commit}}", check=False)
        if result.returncode == 1:
            return None
        if result.returncode:
            raise HistoryCaptureError("Cannot read REE history head")
        return result.stdout.decode().strip()

    def initial_snapshot(self) -> str | None:
        result = self.git("rev-parse", "--verify", "--quiet", f"{INITIAL_REF}^{{commit}}", check=False)
        if result.returncode == 1:
            return None
        if result.returncode:
            raise HistoryCaptureError("Cannot read the initial REE snapshot")
        return result.stdout.decode().strip()

    def _selected_files(self) -> list[Path]:
        ree = ReeDirectory(self.layout).read_ree() if self.layout.manifest.is_file() else None
        return [
            self.layout.root / entry.path
            for entry in capture_plan(self.layout, ree).entries
            if not self._internal_temporary(self.layout.root / entry.path)
        ]

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
            self.git("read-tree", "--empty", index=index)
            entries = bytearray()
            ree = ReeDirectory(self.layout).read_ree() if self.layout.manifest.is_file() else None
            lfs_paths = set(ree.subject.capture.lfs_paths) if ree and ree.subject.capture else set()
            for path in self._selected_files():
                relative = path.relative_to(self.layout.root)
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    mode = "120000"
                    blob = self.git("hash-object", "-w", "--stdin", data=os.fsencode(path.readlink()))
                elif stat.S_ISREG(info.st_mode):
                    mode = "100755" if info.st_mode & 0o111 else "100644"
                    if relative.as_posix() in lfs_paths:
                        pointer = store_payload(path, self.layout.git_dir)
                        blob = self.git("hash-object", "-w", "--stdin", data=pointer.encode())
                    else:
                        blob = self.git("hash-object", "-w", "--no-filters", "--", str(relative))
                else:
                    raise HistoryCaptureError(f"Cannot capture special file: {relative}")
                entries.extend(f"{mode} {blob.stdout.decode().strip()}\t".encode())
                entries.extend(os.fsencode(relative.as_posix()) + b"\0")
            self.git("update-index", "-z", "--index-info", data=bytes(entries), index=index)
            return self.git("write-tree", index=index).stdout.decode().strip()

    def restore(self, snapshot: str) -> None:
        """Put the selected REE files back as ``snapshot`` recorded them: a canceled attempt's rollback.

        Selected files the snapshot does not hold are removed. Files outside the selection (logs,
        upload staging, the recorder's own storage) are never captured, so they are left alone.
        The manifest is restored first: it says which paths the snapshot holds as LFS pointers.
        """
        recorded: dict[str, tuple[str, str]] = {}
        for entry in self.git("ls-tree", "-rz", snapshot).stdout.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            if kind != "blob":
                raise HistoryCaptureError(f"Cannot restore {os.fsdecode(raw_path)}: not a file")
            recorded[os.fsdecode(raw_path)] = (mode, oid)
        for path in self._selected_files():
            if path.relative_to(self.layout.root).as_posix() not in recorded:
                path.unlink()
        manifest = self.layout.manifest.relative_to(self.layout.root).as_posix()
        lfs_paths: set[str] = set()
        for relative in sorted(recorded, key=lambda name: name != manifest):
            mode, oid = recorded[relative]
            target = self.layout.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.is_file():
                target.unlink()
            if mode == "120000":
                target.symlink_to(os.fsdecode(self.git("cat-file", "blob", oid).stdout))
                continue
            pointer = LfsPointer.parse(self.git("cat-file", "blob", oid).stdout) if relative in lfs_paths else None
            if relative in lfs_paths and pointer is None:
                raise HistoryCaptureError(f"Cannot restore {relative}: expected an LFS pointer")
            if pointer is not None:
                shutil.copyfile(pointer.verify(self.layout.git_dir), target)
            else:
                with target.open("wb") as stream:
                    self.git("cat-file", "blob", oid, output=stream)
            target.chmod(0o755 if mode == "100755" else 0o644)
            if relative == manifest:
                ree = ReeDirectory(self.layout).read_ree()
                lfs_paths = set(ree.subject.capture.lfs_paths) if ree.subject.capture else set()

    def _commit(
        self,
        tree: str,
        parent: str | None,
        *,
        operation: str,
        run_id: str | None = None,
        outcome: str | None = None,
        attempt_id: str | None = None,
        record: dict[str, Any] | None = None,
    ) -> str:
        metadata: dict[str, Any] = {
            "schema_version": 1,
            "selection_version": SELECTION_VERSION,
            "run_id": run_id,
            "outcome": outcome,
            "attempt_id": attempt_id,
        }
        if record is not None:
            metadata.update(kind="operation.completed", schema_version=2, record=record)
        message = f"{operation}\n\n{json.dumps(metadata)}\n"
        parents = ("-p", parent) if parent is not None else ()
        commit = self.git("commit-tree", tree, *parents, data=message.encode()).stdout.decode().strip()
        # Compare-and-swap also detects a non-cooperating writer moving the ref.
        self.git("update-ref", HISTORY_REF, commit, parent or "")
        # update-ref publishes the journal entry. The index is only a cache:
        # failing to refresh it must not turn a published outcome into failure.
        with suppress(HistoryCaptureError, OSError):
            self.git("read-tree", commit)
        return commit

    def commit_operation(self, *, operation: str, record: dict[str, Any]) -> tuple[str, bool]:
        """Publish a completed attempt even when its state tree is unchanged."""
        before = record["before_snapshot_id"]
        if self.head_snapshot() != before:
            raise HistoryCaptureError("History head changed before operation publication")
        tree = self._tree()
        previous_tree = self.git("rev-parse", f"{before}^{{tree}}").stdout.decode().strip()
        changed = tree != previous_tree
        commit = self._commit(
            tree,
            before,
            operation=operation,
            run_id=record["run_id"],
            outcome=record["operation_status"],
            attempt_id=record["attempt_id"],
            record={**record, "changed": changed},
        )
        return commit, changed

    def completed_operations(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """Read published journal entries without initializing or locking storage."""
        head = self.head_snapshot()
        imported = (
            self.git("for-each-ref", "--format=%(refname)", "refs/repo2ree/imports/").stdout.decode().splitlines()
        )
        heads = ([head] if head else []) + imported
        if not heads:
            return
        entries = self.git("log", "--format=%H%x00%B%x00", *heads).stdout.decode().split("\0")
        for index in range(0, len(entries) - 1, 2):
            commit, body = entries[index].strip(), entries[index + 1]
            _subject, separator, metadata = body.partition("\n\n")
            if not separator or not metadata.lstrip().startswith("{"):
                continue
            try:
                document = json.loads(metadata)
            except ValueError as exc:
                raise HistoryCaptureError(f"Unreadable history metadata at {commit}") from exc
            if isinstance(document, dict) and document.get("kind") == "operation.completed":
                if document.get("schema_version") != 2:
                    raise HistoryCaptureError(f"Unsupported operation history at {commit}")
                yield commit, document["record"]

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
        parent = self.git("rev-parse", "--verify", "--quiet", f"{HISTORY_REF}^{{commit}}", check=False)
        if parent.returncode not in {0, 1}:
            raise HistoryCaptureError("Cannot read the REE history head")
        parent_id = parent.stdout.decode().strip() if parent.returncode == 0 else None
        tree = self._tree()
        if parent_id is not None:
            body = self.git("show", "-s", "--format=%b", parent_id).stdout.decode()
            try:
                metadata = json.loads(body)
            except ValueError:
                metadata = {}
            version = metadata.get("selection_version") if isinstance(metadata, dict) else None
            if version != SELECTION_VERSION:
                parent_id = self._commit(tree, parent_id, operation="migrate_history_selection")
            if reuse_unchanged:
                previous_tree = self.git("rev-parse", f"{parent_id}^{{tree}}").stdout.decode().strip()
                if tree == previous_tree:
                    return parent_id
        return self._commit(tree, parent_id, operation=operation, run_id=run_id, outcome=outcome, attempt_id=attempt_id)

    def capture_initial(self, *, existing: bool) -> str:
        if snapshot := self.initial_snapshot():
            return snapshot
        snapshot = self.capture(operation="baseline_existing_ree" if existing else "initialize_ree")
        self.git("update-ref", INITIAL_REF, snapshot)
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
