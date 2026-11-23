from __future__ import annotations

import fcntl
import hashlib
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
from repo2ree_core.persistence.ree_manifest import parse_ree_manifest
from repo2ree_protocol.history import SELECTION_VERSION
from repo2ree_protocol.tools import find_tool

INITIAL_REF = "refs/repo2ree/initial"
HISTORY_REF = "refs/heads/ree-history"
REFLOG_MARK = "repo2ree"
ATTEMPT = "operation.completed"
SNAPSHOT = "snapshot"
REPOSITORY_CONFIG = (
    ("core.logAllRefUpdates", "always"),
    ("gc.reflogExpire", "never"),
    ("gc.reflogExpireUnreachable", "never"),
)


class HistoryCaptureError(RuntimeError):
    pass


def _walk_failed(error: OSError) -> None:
    raise HistoryCaptureError(f"Cannot enumerate REE files: {error}") from error


def selected_files(layout: ReeLayout) -> list[Path]:
    ree = ReeDirectory(layout).read_ree() if layout.manifest.is_file() else None
    return [
        layout.root / entry.path
        for entry in capture_plan(layout, ree).entries
        if not _internal_temporary(layout, layout.root / entry.path)
    ]


def _internal_temporary(layout: ReeLayout, path: Path) -> bool:
    match = re.fullmatch(r"\.(.+)\.[0-9a-f]{32}\.tmp", path.name)
    if match is None:
        return False
    target = path.with_name(match[1])
    if target in (*layout.history_files, layout.sbom, layout.reproducibility_report):
        return True
    return isinstance(layout, ReviewLayout) and (
        target.is_relative_to(layout.receipts) or target.is_relative_to(layout.comparisons)
    )


def _metadata(commit: str, body: str) -> dict[str, Any] | None:
    _subject, separator, metadata = body.partition("\n\n")
    if not separator or not metadata.lstrip().startswith("{"):
        return None
    try:
        document = json.loads(metadata)
    except ValueError as exc:
        raise HistoryCaptureError(f"Unreadable history metadata at {commit}") from exc
    return document if isinstance(document, dict) else None


def _operation_record(commit: str, body: str) -> dict[str, Any] | None:
    document = _metadata(commit, body)
    if document is None or document.get("kind") != ATTEMPT:
        return None
    record = document.get("record")
    if document.get("schema_version") != 2 or not isinstance(record, dict):
        raise HistoryCaptureError(f"Unsupported operation history at {commit}")
    return record


def _file_mode(info: os.stat_result) -> str:
    return "100755" if info.st_mode & 0o111 else "100644"


def _pointer_of(path: Path) -> LfsPointer:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return LfsPointer(oid=digest, size=path.stat().st_size)


@dataclass(frozen=True)
class GitHistory:
    layout: ReeLayout
    executable: str

    def initialize(self) -> None:
        self.git("init", "--quiet", "--template=", "--initial-branch=ree-history")
        for key, value in REPOSITORY_CONFIG:
            if self.git("config", "--get", key, check=False).stdout.decode().strip() != value:
                self.git("config", key, value)

    def git(
        self,
        *args: str,
        data: bytes | None = None,
        index: Path | None = None,
        check: bool = True,
        output: BinaryIO | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
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
        return selected_files(self.layout)

    def _tree(self, *, store: bool = True) -> str:
        with tempfile.TemporaryDirectory(dir=self.layout.git_dir, prefix="capture-") as temporary:
            index = Path(temporary) / "index"
            self.git("read-tree", "--empty", index=index)
            ree = ReeDirectory(self.layout).read_ree() if self.layout.manifest.is_file() else None
            lfs_paths = set(ree.subject.capture.lfs_paths) if ree else set()
            written = ("-w",) if store else ()
            entries: list[tuple[str, str, str]] = []
            plain: list[tuple[str, str]] = []
            for path in self._selected_files():
                relative = path.relative_to(self.layout.root).as_posix()
                info = path.lstat()
                if stat.S_ISLNK(info.st_mode):
                    link = self.git("hash-object", *written, "--stdin", data=os.fsencode(path.readlink()))
                    entries.append(("120000", link.stdout.decode().strip(), relative))
                elif not stat.S_ISREG(info.st_mode):
                    raise HistoryCaptureError(f"Cannot capture special file: {relative}")
                elif relative in lfs_paths:
                    pointer = store_payload(path, self.layout.git_dir) if store else _pointer_of(path)
                    hashed_pointer = self.git("hash-object", *written, "--stdin", data=pointer.encode())
                    entries.append((_file_mode(info), hashed_pointer.stdout.decode().strip(), relative))
                else:
                    plain.append((_file_mode(info), relative))
            if any("\n" in relative for _mode, relative in plain):
                raise HistoryCaptureError("Cannot capture a file whose name holds a line break")
            if plain:
                listed = "\n".join(relative for _mode, relative in plain) + "\n"
                hashed = self.git("hash-object", *written, "--no-filters", "--stdin-paths", data=listed.encode())
                blobs = hashed.stdout.decode().split()
                if len(blobs) != len(plain):
                    raise HistoryCaptureError("Git hashed another number of files than it was given")
                entries += [(mode, blob, relative) for (mode, relative), blob in zip(plain, blobs, strict=True)]
            info_lines = bytearray()
            for mode, blob, relative in entries:
                info_lines.extend(f"{mode} {blob}\t".encode() + os.fsencode(relative) + b"\0")
            self.git("update-index", "-z", "--index-info", data=bytes(info_lines), index=index)
            return self.git("write-tree", *(() if store else ("--missing-ok",)), index=index).stdout.decode().strip()

    def drifted_paths(self, base: str | None = None) -> list[tuple[str, str]]:
        base = base or self.head_snapshot()
        if base is None:
            return []
        tree = self._tree(store=False)
        listed = self.git("diff-tree", "-r", "-z", "--no-renames", "--name-status", f"{base}^{{tree}}", tree)
        fields = listed.stdout.decode().split("\0")
        return [(fields[index + 1], fields[index][0]) for index in range(0, len(fields) - 1, 2)]

    def holds(self, relative: str) -> bool:
        head = self.head_snapshot()
        return head is not None and self.git("cat-file", "-e", f"{head}:{relative}", check=False).returncode == 0

    def left_by_ree(self) -> str | None:
        listed = self.git("reflog", "show", "--format=%H%x00%gs", HISTORY_REF, "--", check=False)
        for line in listed.stdout.decode().splitlines():
            commit, _, subject = line.partition("\0")
            if subject == REFLOG_MARK or subject.startswith(f"{REFLOG_MARK} "):
                return commit
        return None

    def unrecorded(self, commit: str) -> str | None:
        body = self.git("log", "-1", "--format=%B", commit).stdout.decode()
        metadata = _metadata(commit, body)
        if metadata is None or metadata.get("kind") not in {ATTEMPT, SNAPSHOT}:
            return "it says nothing of an attempt of ree's"
        parents = self.git("rev-parse", f"{commit}^@").stdout.decode().split()
        if parents != ([metadata["parent"]] if metadata.get("parent") else []):
            return "it names another parent than its own, as a commit copied by git does"
        if metadata.get("tree") != self.git("rev-parse", f"{commit}^{{tree}}").stdout.decode().strip():
            return "it names another tree than its own, as a commit amended by git does"
        if metadata.get("kind") == ATTEMPT and (_operation_record(commit, body) or {}).get("before_snapshot_id") != (
            parents[0] if parents else None
        ):
            return "its attempt began on another commit than its parent"
        return None

    def first_unrecorded(self, head: str) -> tuple[str, str] | None:
        for commit in self.git("rev-list", head).stdout.decode().split():
            if (reason := self.unrecorded(commit)) is not None:
                return commit, reason
        return None

    def restore(self, snapshot: str) -> None:
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
                lfs_paths = set(ree.subject.capture.lfs_paths)

    def entries(self, snapshot: str) -> dict[str, tuple[str, str]]:
        recorded: dict[str, tuple[str, str]] = {}
        for entry in self.git("ls-tree", "-rz", snapshot).stdout.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            if kind != "blob":
                raise HistoryCaptureError(f"Cannot read {os.fsdecode(raw_path)}: not a file")
            recorded[os.fsdecode(raw_path)] = (mode, oid)
        return recorded

    def lfs_paths_at(self, snapshot: str) -> set[str]:
        manifest = self.layout.manifest.relative_to(self.layout.root).as_posix()
        shown = self.git("show", f"{snapshot}:{manifest}", check=False)
        if shown.returncode != 0:
            return set()
        return {str(path) for path in parse_ree_manifest(json.loads(shown.stdout)).subject.capture.lfs_paths}

    def check_out(self, snapshot: str, root: Path, *, payloads: Path) -> list[str]:
        recorded = self.entries(snapshot)
        lfs_paths = self.lfs_paths_at(snapshot)
        for relative, (mode, oid) in recorded.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if mode == "120000":
                target.symlink_to(os.fsdecode(self.git("cat-file", "blob", oid).stdout))
                continue
            if relative in lfs_paths:
                kept = payloads / relative
                if kept.is_file() and not kept.is_symlink():
                    _link_or_copy(kept, target)
                    continue
                pointer = LfsPointer.parse(self.git("cat-file", "blob", oid).stdout)
                if pointer is None:
                    raise HistoryCaptureError(f"Cannot check out {relative}: expected an LFS pointer")
                shutil.copyfile(pointer.verify(self.layout.git_dir), target)
            else:
                with target.open("wb") as stream:
                    self.git("cat-file", "blob", oid, output=stream)
            target.chmod(0o755 if mode == "100755" else 0o644)
        return sorted(recorded)

    def holds_as(self, path: Path, entry: tuple[str, str] | None, *, lfs: bool) -> bool:
        if entry is None:
            return not path.exists() and not path.is_symlink()
        mode, oid = entry
        if mode == "120000":
            if not path.is_symlink():
                return False
            found = self.git("hash-object", "--stdin", data=os.fsencode(path.readlink())).stdout.decode().strip()
            return found == oid
        if path.is_symlink() or not path.is_file() or _file_mode(path.lstat()) != mode:
            return False
        if lfs:
            pointer = LfsPointer.parse(self.git("cat-file", "blob", oid).stdout)
            return pointer is not None and _pointer_of(path) == pointer
        return self.git("hash-object", "--no-filters", str(path)).stdout.decode().strip() == oid

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
            "schema_version": 2,
            "kind": SNAPSHOT,
            "selection_version": SELECTION_VERSION,
            "parent": parent,
            "tree": tree,
            "run_id": run_id,
            "outcome": outcome,
            "attempt_id": attempt_id,
        }
        if record is not None:
            metadata.update(kind=ATTEMPT, record=record)
        message = f"{operation}\n\n{json.dumps(metadata)}\n"
        parents = ("-p", parent) if parent is not None else ()
        commit = self.git("commit-tree", tree, *parents, data=message.encode()).stdout.decode().strip()
        self.git("update-ref", "-m", f"{REFLOG_MARK} {operation}", HISTORY_REF, commit, parent or "")
        with suppress(HistoryCaptureError, OSError):
            self.git("read-tree", commit)
        return commit

    def commit_operation(self, *, operation: str, record: dict[str, Any], unchanged: bool = False) -> tuple[str, bool]:
        before = record["before_snapshot_id"]
        if self.head_snapshot() != before:
            raise HistoryCaptureError("History head changed before operation publication")
        previous_tree = self.git("rev-parse", f"{before}^{{tree}}").stdout.decode().strip()
        tree = previous_tree if unchanged else self._tree()
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
        head = self.head_snapshot()
        imported = (
            self.git("for-each-ref", "--format=%(refname)", "refs/repo2ree/imports/").stdout.decode().splitlines()
        )
        heads = ([head] if head else []) + imported
        if not heads:
            return
        entries = self.git("log", "--format=%H%x00%B%x00", *heads).stdout.decode().split("\0")
        for index in range(0, len(entries) - 1, 2):
            commit = entries[index].strip()
            record = _operation_record(commit, entries[index + 1])
            if record is not None:
                yield commit, record

    def records_operation(self, commit: str) -> bool:
        body = self.git("log", "-1", "--format=%B", commit).stdout.decode()
        return _operation_record(commit, body) is not None and self.unrecorded(commit) is None

    def capture(
        self,
        *,
        operation: str,
        run_id: str | None = None,
        outcome: str | None = None,
        attempt_id: str | None = None,
        reuse_unchanged: bool = False,
    ) -> str:
        parent = self.git("rev-parse", "--verify", "--quiet", f"{HISTORY_REF}^{{commit}}", check=False)
        if parent.returncode not in {0, 1}:
            raise HistoryCaptureError("Cannot read the REE history head")
        parent_id = parent.stdout.decode().strip() if parent.returncode == 0 else None
        tree = self._tree()
        if parent_id is not None and reuse_unchanged:
            previous_tree = self.git("rev-parse", f"{parent_id}^{{tree}}").stdout.decode().strip()
            if tree == previous_tree:
                return parent_id
        return self._commit(tree, parent_id, operation=operation, run_id=run_id, outcome=outcome, attempt_id=attempt_id)

    def capture_initial(self, *, existing: bool) -> str:
        if snapshot := self.initial_snapshot():
            return snapshot
        snapshot = self.capture(operation="baseline_existing_ree" if existing else "initialize_ree")
        self.git("update-ref", "-m", f"{REFLOG_MARK} {INITIAL_REF}", INITIAL_REF, snapshot)
        return snapshot


@contextmanager
def open_history(layout: ReeLayout) -> Iterator[GitHistory]:
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


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)
