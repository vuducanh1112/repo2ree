from __future__ import annotations

import contextlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from repo2ree_core.persistence.history import GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.workspace.integrity import reviews_of
from repo2ree_protocol.tools import find_tool

_HISTORY = ".git"
type _Identity = tuple[int, int]


def _git() -> str:
    executable = find_tool("git")
    if executable is None:
        raise HistoryCaptureError("git is required to stage an attempt")
    return executable


def _link_or_copy(source: Path, target: Path) -> None:
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _scope_layout(root: Path, relative: str) -> ReeLayout:
    return ReeLayout(root=root) if relative == "." else ReviewLayout(root=root / relative)


@dataclass(frozen=True)
class Stage:
    live: ReeLayout
    root: Path
    heads: dict[str, str | None]
    held: frozenset[str]
    linked: dict[str, _Identity]
    links: dict[str, str]
    directories: frozenset[str]

    @property
    def layout(self) -> ReeLayout:
        return ReeLayout(root=self.root)

    def scope(self, relative: str) -> ReeLayout:
        return _scope_layout(self.root, relative)

    def history(self, relative: str) -> GitHistory:
        return GitHistory(self.scope(relative), _git())


def lay_out(live: ReeLayout, attempt_id: str) -> Stage:
    root = live.stages / attempt_id
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    executable = _git()
    scopes = {".": live, **{review.root.relative_to(live.root).as_posix(): review for review in reviews_of(live)}}
    heads: dict[str, str | None] = {}
    held: set[str] = set()
    for relative, scope in scopes.items():
        staged = root if relative == "." else root / relative
        staged.mkdir(parents=True, exist_ok=True)
        (staged / _HISTORY).symlink_to(scope.git_dir.resolve())
        history = GitHistory(scope, executable)
        head = history.head_snapshot()
        heads[relative] = head
        if head is None:
            continue
        prefix = "" if relative == "." else f"{relative}/"
        held.update(f"{prefix}{path}" for path in history.check_out(head, staged, payloads=scope.root))
    linked: dict[str, _Identity] = {}
    links: dict[str, str] = {}
    directories: set[str] = set()
    for directory, dirnames, filenames in live.root.walk():
        here = directory.relative_to(live.root)
        dirnames[:] = [name for name in dirnames if name != _HISTORY and directory / name != live.stages]
        for name in [*dirnames, *filenames]:
            path = directory / name
            relative = (here / name).as_posix()
            if relative in held or name == _HISTORY:
                continue
            target = root / relative
            if path.is_symlink():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(path.readlink())
                links[relative] = str(path.readlink())
            elif path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                directories.add(relative)
            elif path.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                _link_or_copy(path, target)
                info = path.stat()
                linked[relative] = (info.st_dev, info.st_ino)
        dirnames[:] = [name for name in dirnames if not (directory / name).is_symlink()]
    return Stage(
        live=live,
        root=root,
        heads=heads,
        held=frozenset(held),
        linked=linked,
        links=links,
        directories=frozenset(directories),
    )


def changed_beyond(stage: Stage, recorded_in: str) -> list[str]:
    changed = []
    for relative, head in stage.heads.items():
        if relative == recorded_in or head is None:
            continue
        history = stage.history(relative)
        tree = history.git("rev-parse", f"{head}^{{tree}}").stdout.decode().strip()
        if history._tree(store=False) != tree:  # noqa: SLF001
            changed.append(relative)
    return changed


def put_back(stage: Stage, recorded_in: str, before: str, after: str) -> None:
    live = _scope_layout(stage.live.root, recorded_in)
    history = GitHistory(live, _git())
    was, now = history.entries(before), history.entries(after)
    lfs_was, lfs_now = history.lfs_paths_at(before), history.lfs_paths_at(after)
    staged = stage.scope(recorded_in).root
    manifest = live.manifest.relative_to(live.root).as_posix()
    for relative in sorted(set(was) | set(now), key=lambda name: name == manifest):
        if was.get(relative) == now.get(relative):
            continue
        target = live.root / relative
        if history.holds_as(target, now.get(relative), lfs=relative in lfs_now):
            continue
        if not history.holds_as(target, was.get(relative), lfs=relative in lfs_was):
            continue
        if relative not in now:
            target.unlink()
            continue
        _replace(staged / relative, target)
    prefix = "" if recorded_in == "." else f"{recorded_in}/"
    held = set(stage.held) | {f"{prefix}{relative}" for relative in now}
    _put_back_unheld(stage, held)


def _replace(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_dir() and not target.is_symlink():
        shutil.rmtree(target)
    swap = target.with_name(f".{target.name}.staged")
    swap.unlink(missing_ok=True)
    if source.is_symlink():
        swap.symlink_to(source.readlink())
    else:
        _link_or_copy(source, swap)
    swap.replace(target)


def _same(path: Path, identity: _Identity) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return (info.st_dev, info.st_ino) == identity


def _put_back_unheld(stage: Stage, held: set[str]) -> None:
    live = stage.live.root
    present: set[str] = set()
    for directory, dirnames, filenames in stage.root.walk():
        here = directory.relative_to(stage.root)
        dirnames[:] = [name for name in dirnames if name != _HISTORY and not (directory / name).is_symlink()]
        for name in dirnames:
            relative = (here / name).as_posix()
            present.add(relative)
            if relative not in held:
                (live / relative).mkdir(parents=True, exist_ok=True)
        for name in [*filenames, *(entry.name for entry in directory.iterdir() if entry.is_symlink())]:
            relative = (here / name).as_posix()
            if name == _HISTORY or relative in held or relative in present:
                continue
            present.add(relative)
            path = directory / name
            if path.is_symlink():
                if stage.links.get(relative) == str(path.readlink()):
                    continue
                if relative not in stage.links or (live / relative).is_symlink():
                    _replace(path, live / relative)
                continue
            identity = stage.linked.get(relative)
            if identity is not None and _same(path, identity):
                continue
            if identity is None or _same(live / relative, identity) or not (live / relative).exists():
                _replace(path, live / relative)

    def removed(relative: str) -> bool:
        staged = stage.root / relative
        return relative not in held and not staged.exists() and not staged.is_symlink()

    for relative, identity in stage.linked.items():
        if removed(relative) and _same(live / relative, identity):
            (live / relative).unlink()
    for relative in stage.links:
        if removed(relative) and (live / relative).is_symlink():
            (live / relative).unlink()
    for relative in sorted(
        (name for name in stage.directories if removed(name)), key=lambda name: name.count("/"), reverse=True
    ):
        try:
            (live / relative).rmdir()
        except OSError:
            continue


def discard(stage: Stage) -> None:
    shutil.rmtree(stage.root, ignore_errors=True)
    with_stages = stage.root.parent
    with contextlib.suppress(OSError):
        with_stages.rmdir()


def discard_left(live: ReeLayout, attempt_id: str) -> None:
    root = live.stages / attempt_id
    shutil.rmtree(root, ignore_errors=True)
    with contextlib.suppress(OSError):
        root.parent.rmdir()
