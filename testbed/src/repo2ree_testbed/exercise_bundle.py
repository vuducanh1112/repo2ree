from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Final

from repo2ree_testbed.exercise import BundleCorruption

_TREE: Final = "ree/"
_GIT: Final = "ree/.git/"
_EXPORT: Final = "export.json"
_DAMAGED: Final = b"damaged on its way\n"
_IDENTITY: Final = ("-c", "user.name=environment", "-c", "user.email=environment@repo2ree.invalid")


def corrupted(archive: bytes, corruption: BundleCorruption, number: int) -> bytes:
    if corruption == "intact":
        return archive
    if corruption == "truncated":
        return archive[: len(archive) // 2]
    try:
        entries = _entries(archive)
    except zipfile.BadZipFile:
        return archive
    damage: dict[BundleCorruption, Callable[[dict[str, tuple[zipfile.ZipInfo, bytes]], int], bool]] = {
        "unknown_head": _unknown_head,
        "objects_removed": _objects_removed,
        "file_changed": _file_changed,
        "foreign_commit": _foreign_commit,
    }
    return _archive(entries) if damage[corruption](entries, number) else archive


def _entries(archive: bytes) -> dict[str, tuple[zipfile.ZipInfo, bytes]]:
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        return {info.filename: (info, bundle.read(info)) for info in bundle.infolist()}


def _archive(entries: dict[str, tuple[zipfile.ZipInfo, bytes]]) -> bytes:
    written = io.BytesIO()
    with zipfile.ZipFile(written, "w", zipfile.ZIP_DEFLATED) as bundle:
        for info, content in entries.values():
            bundle.writestr(info, content)
    return written.getvalue()


def _export(entries: dict[str, tuple[zipfile.ZipInfo, bytes]]) -> dict[str, object] | None:
    if _EXPORT not in entries:
        return None
    try:
        export = json.loads(entries[_EXPORT][1])
    except ValueError:
        return None
    return export if isinstance(export, dict) else None


def _ree_scope(export: dict[str, object]) -> dict[str, object] | None:
    scopes = export.get("scopes")
    if not isinstance(scopes, list):
        return None
    return next((scope for scope in scopes if isinstance(scope, dict) and scope.get("scope") == "."), None)


def _name_head(entries: dict[str, tuple[zipfile.ZipInfo, bytes]], head: str) -> bool:
    export = _export(entries)
    scope = _ree_scope(export) if export is not None else None
    if export is None or scope is None:
        return False
    scope["head"] = head
    info, _ = entries[_EXPORT]
    entries[_EXPORT] = (info, json.dumps(export, indent=2).encode())
    return True


def _unknown_head(entries: dict[str, tuple[zipfile.ZipInfo, bytes]], number: int) -> bool:
    return _name_head(entries, hashlib.sha1(f"no commit {number}".encode(), usedforsecurity=False).hexdigest())


def _objects_removed(entries: dict[str, tuple[zipfile.ZipInfo, bytes]], _number: int) -> bool:
    objects = [name for name in entries if name.startswith(f"{_GIT}objects/") and not name.endswith("/")]
    for name in objects:
        del entries[name]
    return bool(objects)


def _file_changed(entries: dict[str, tuple[zipfile.ZipInfo, bytes]], _number: int) -> bool:
    beside = sorted(
        name
        for name in entries
        if name.startswith(_TREE)
        and not name.startswith(_GIT)
        and not name.startswith(f"{_TREE}reviews/")
        and not name.endswith("/")
    )
    if not beside:
        return False
    name = f"{_TREE}ree.json" if f"{_TREE}ree.json" in beside else beside[0]
    info, content = entries[name]
    entries[name] = (info, content + _DAMAGED)
    return True


def _git(git_dir: Path, *words: str, stdin: bytes | None = None) -> str | None:
    ran = subprocess.run(
        ["git", "--git-dir", str(git_dir), *_IDENTITY, *words], input=stdin, capture_output=True, check=False
    )
    return ran.stdout.decode().strip() if ran.returncode == 0 else None


def _foreign_commit(entries: dict[str, tuple[zipfile.ZipInfo, bytes]], number: int) -> bool:
    export = _export(entries)
    scope = _ree_scope(export) if export is not None else None
    head = scope.get("head") if scope is not None else None
    if not isinstance(head, str):
        return False
    with tempfile.TemporaryDirectory() as temporary:
        git_dir = Path(temporary) / ".git"
        for name, (info, content) in entries.items():
            if name.startswith(_GIT) and not info.is_dir():
                target = git_dir / name.removeprefix(_GIT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        before = {path for path in (git_dir / "objects").rglob("*") if path.is_file()}
        blob = _git(git_dir, "hash-object", "-w", "--stdin", stdin=_DAMAGED)
        listed = _git(git_dir, "ls-tree", head)
        if blob is None or listed is None:
            return False
        lines = [*listed.splitlines(), f"100644 blob {blob}\tdamaged-{number}.txt"]
        tree = _git(git_dir, "mktree", stdin=("\n".join(lines) + "\n").encode())
        commit = _git(git_dir, "commit-tree", tree, "-p", head, "-m", "changed outside ree") if tree else None
        if commit is None:
            return False
        for path in sorted(path for path in (git_dir / "objects").rglob("*") if path.is_file() and path not in before):
            name = f"{_GIT}{path.relative_to(git_dir).as_posix()}"
            entries[name] = (zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), path.read_bytes())
    return _name_head(entries, commit)
