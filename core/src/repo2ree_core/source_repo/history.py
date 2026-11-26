from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.lfs import LfsPointer, store_payload
from repo2ree_protocol.tools import find_tool
from repo2ree_ree.digest import Digest
from repo2ree_ree.primitives import GitRevision, SourceHistory, Swhid, WorkspacePath
from repo2ree_ree.receipt import LfsFile

SOURCE_REF = "refs/ree/source"
_TAGS = "refs/tags/"
_SWHID_DIRECTORY = "swh:1:dir:"
_NO_HOOKS = "ree-no-hooks"
_POINTER_LIMIT = 1024
_SYMLINK_MODE = "120000"


class SourceHistoryError(Exception):
    pass


@dataclass(frozen=True)
class PackedSourceHistory:
    revision: GitRevision
    history: SourceHistory
    digest: Digest


def _git_executable() -> str:
    executable = find_tool("git")
    if executable is None:
        raise SourceHistoryError("git is required for a git source's history")
    return executable


def _environment() -> dict[str, str]:
    kept = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    return {**kept, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}


def _git(repository: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        [_git_executable(), "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=False,
        env=_environment(),
    )
    if check and done.returncode != 0:
        raise SourceHistoryError(f"git {' '.join(args)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done


def _out(repository: Path, *args: str) -> str:
    return _git(repository, *args).stdout.strip()


def _git_bytes(repository: Path, *args: str, stdin: bytes) -> bytes:
    done = subprocess.run(
        [_git_executable(), "-C", str(repository), *args],
        input=stdin,
        capture_output=True,
        check=False,
        env=_environment(),
    )
    if done.returncode != 0:
        raise SourceHistoryError(f"git {' '.join(args)} failed: {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def lfs_manifest(repository: Path, revision: str) -> dict[str, LfsPointer]:
    small: dict[str, str] = {}
    for record in _git_bytes(repository, "ls-tree", "-r", "-z", "-l", "--full-tree", revision, stdin=b"").split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, kind, blob, size = meta.decode().split()
        if kind == "blob" and mode != _SYMLINK_MODE and int(size) < _POINTER_LIMIT:
            small[path.decode()] = blob
    if not small:
        return {}
    contents = _blobs(repository, sorted(set(small.values())))
    pointers = {path: pointer for path, blob in small.items() if (pointer := LfsPointer.parse(contents[blob]))}
    if not pointers:
        return {}
    listed = _git_bytes(
        repository,
        "check-attr",
        "--stdin",
        "-z",
        "--source",
        revision,
        "filter",
        stdin=b"".join(path.encode() + b"\0" for path in pointers),
    ).split(b"\0")
    filtered = {
        listed[index].decode()
        for index in range(0, len(listed) - 2, 3)
        if listed[index + 1] == b"filter" and listed[index + 2] == b"lfs"
    }
    return {path: pointer for path, pointer in sorted(pointers.items()) if path in filtered}


def lfs_files(manifest: Mapping[str, LfsPointer]) -> tuple[LfsFile, ...]:
    return tuple(
        LfsFile(path=WorkspacePath(path), digest=Digest(f"sha256:{pointer.oid}"), size=pointer.size)
        for path, pointer in sorted(manifest.items())
    )


def lfs_pointers(files: tuple[LfsFile, ...]) -> dict[str, LfsPointer]:
    return {str(file.path): LfsPointer(oid=str(file.digest).removeprefix("sha256:"), size=file.size) for file in files}


def _blobs(repository: Path, blobs: list[str]) -> dict[str, bytes]:
    out = _git_bytes(repository, "cat-file", "--batch", stdin="".join(f"{blob}\n" for blob in blobs).encode())
    contents: dict[str, bytes] = {}
    at = 0
    for blob in blobs:
        header_end = out.index(b"\n", at)
        name, _kind, size = out[at:header_end].decode().split()
        if name != blob:
            raise SourceHistoryError(f"git cat-file answered {name} for {blob}")
        start = header_end + 1
        contents[blob] = out[start : start + int(size)]
        at = start + int(size) + 1
    return contents


def bundled_lfs_manifest(bundle: Path, *, revision: GitRevision, history: SourceHistory) -> dict[str, LfsPointer]:
    with tempfile.TemporaryDirectory(prefix="ree-source-lfs-") as scratch:
        repository = Path(scratch)
        _git(repository, "init", "--quiet")
        _fill(repository, bundle, revision, history)
        return lfs_manifest(repository, str(revision))


def _tree_of(swhid: Swhid) -> str:
    if not str(swhid).startswith(_SWHID_DIRECTORY):
        raise SourceHistoryError(f"a source's identity is a directory SWHID, not {swhid}")
    return str(swhid).removeprefix(_SWHID_DIRECTORY)


def _annotated_tags(repository: Path, revision: str, history: SourceHistory) -> list[str]:
    listed = _out(repository, "for-each-ref", "--format=%(objecttype) %(refname)", _TAGS)
    tags = [line.split(" ", 1)[1] for line in listed.splitlines() if line.startswith("tag ")]
    if history == "tip":
        return [tag for tag in tags if _out(repository, "rev-parse", f"{tag}^{{commit}}") == revision]
    return [
        tag
        for tag in tags
        if _git(repository, "merge-base", "--is-ancestor", f"{tag}^{{commit}}", revision, check=False).returncode == 0
    ]


def pack_source_history(clone: Path, destination: Path) -> PackedSourceHistory:
    revision = GitRevision(_out(clone, "rev-parse", "HEAD"))
    history: SourceHistory = "tip" if _out(clone, "rev-parse", "--is-shallow-repository") == "true" else "full"
    _git(clone, "update-ref", SOURCE_REF, str(revision))
    refs = [SOURCE_REF, *_annotated_tags(clone, str(revision), history)]
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.partial")
    partial.unlink(missing_ok=True)
    _git(clone, "bundle", "create", "--quiet", str(partial), *refs)
    partial.replace(destination)
    return PackedSourceHistory(revision=revision, history=history, digest=digest_file(destination))


def _fill(repository: Path, bundle: Path, revision: GitRevision, history: SourceHistory) -> None:
    if history == "tip":
        (repository / ".git" / "shallow").write_text(f"{revision}\n")
    _git(repository, "fetch", "--quiet", "--no-tags", "--no-write-fetch-head", str(bundle), "refs/*:refs/*")


def verify_source_history(bundle: Path, *, revision: GitRevision, swhid: Swhid, history: SourceHistory) -> None:
    with tempfile.TemporaryDirectory(prefix="ree-source-history-") as scratch:
        repository = Path(scratch)
        _git(repository, "init", "--quiet")
        _fill(repository, bundle, revision, history)
        held = _out(repository, "rev-parse", "--verify", f"{SOURCE_REF}^{{commit}}")
        if held != revision:
            raise SourceHistoryError(f"the source history holds commit {held}, not {revision}")
        tree = _out(repository, "rev-parse", f"{revision}^{{tree}}")
        if tree != _tree_of(swhid):
            raise SourceHistoryError(f"commit {revision} holds tree {tree}, not the source's {swhid}")
        shallow = _out(repository, "rev-parse", "--is-shallow-repository") == "true"
        if (history == "full") == shallow:
            raise SourceHistoryError(
                f"the source history is not {history}: it holds {'the commit alone' if shallow else 'its ancestry'}"
            )
        _git(repository, "fsck", "--strict", "--no-dangling")


def lay_source_repository(
    workspace: Path,
    bundle: Path,
    *,
    revision: GitRevision,
    history: SourceHistory,
    left_out: tuple[str, ...],
    lfs: Mapping[str, LfsPointer] | None = None,
) -> None:
    _git(workspace, "-c", "init.defaultBranch=ree", "init", "--quiet")
    _fill(workspace, bundle, revision, history)
    if lfs:
        _hold_lfs(workspace, lfs)
    _git(workspace, "update-ref", "--no-deref", "HEAD", str(revision))
    _git(workspace, "reset", "--quiet", "--mixed", str(revision))
    git_dir = workspace / ".git"
    no_hooks = git_dir / _NO_HOOKS
    no_hooks.mkdir(exist_ok=True)
    _git(workspace, "config", "core.hooksPath", str(no_hooks))
    exclude = git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    exclude.write_text("".join(f"{pattern}\n" for pattern in left_out))


def _hold_lfs(workspace: Path, lfs: Mapping[str, LfsPointer]) -> None:
    git_dir = workspace / ".git"
    for path, pointer in lfs.items():
        if store_payload(workspace / path, git_dir) != pointer:
            raise SourceHistoryError(f"{path} is not the content its LFS pointer names (sha256:{pointer.oid})")
    for key, value in (
        ("filter.lfs.clean", "git-lfs clean -- %f"),
        ("filter.lfs.smudge", "git-lfs smudge -- %f"),
        ("filter.lfs.process", "git-lfs filter-process"),
        ("filter.lfs.required", "true"),
    ):
        _git(workspace, "config", key, value)
