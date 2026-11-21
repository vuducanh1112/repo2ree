"""Whether an REE's history is as its last attempt left it.

Nothing is kept for it beside what the REE records already. The files its history holds are compared with where ree
left the history, by git. Where ree left the history's ref is in its reflog, under ree's mark
(``GitHistory.left_by_ree``); when the reflog was lost, the head must still be a commit ree made. The REE's
``workspace/`` and ``upstream/`` are views for people: every step runs in a workspace laid out fresh from what the REE
records (``workspace.attempt``), so nothing changed in them can drift. Each review is checked the same, in its own
history. What drifted is found, never absorbed; this guards against mistakes, not against someone rewriting the
records too.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from repo2ree_core.persistence.history import HISTORY_REF, GitHistory, HistoryCaptureError
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.history import DriftedFile, ReePart
from repo2ree_protocol.tools import find_tool
from repo2ree_ree.layout import OVERLAY, WORKSPACE
from repo2ree_ree.reserved_paths import is_overlay_path

# Where a ref is named among an REE's files: in its version storage, which no file view shows.
HISTORY = ".git"


def _history(layout: ReeLayout) -> GitHistory:
    """The history at ``layout``, read without its lock: nothing here writes to it."""
    executable = find_tool("git")
    if executable is None:
        raise HistoryCaptureError("git is not available to read the REE's history")
    return GitHistory(layout, executable)


def _part(relative: str) -> ReePart:
    top = PurePosixPath(relative).parts[0]
    if top == HISTORY:
        return "history"
    return "overlay" if top == OVERLAY else "workspace" if top == WORKSPACE else "records"


def reviews_of(layout: ReeLayout) -> list[ReeLayout]:
    """Every review of the REE that has a history of its own."""
    if not layout.reviews.is_dir():
        return []
    return [layout.review(path.name) for path in sorted(layout.reviews.iterdir()) if (path / HISTORY).is_dir()]


def _moved(history: GitHistory, head: str) -> bool:
    """Whether the history's ref is not where ree left it: by ree's reflog, or, when that was lost, because its head
    is no commit ree made."""
    left = history.left_by_ree()
    if left is not None:
        return left != head
    return history.unrecorded(head) is not None


def _drift_in(scope: ReeLayout, ree: Path) -> list[DriftedFile]:
    if not (scope.git_dir / "HEAD").is_file():
        return []
    history = _history(scope)
    head = history.head_snapshot()
    if head is None:
        return []
    within = scope.root.relative_to(ree).as_posix()
    prefix = "" if within == "." else f"{within}/"
    moved = _moved(history, head)
    # Files are compared with where ree left the history: a moved head may hold an edit committed beside ree.
    base = _left(scope) if moved else None
    paths = [relative for relative, _ in history.drifted_paths(base)]
    drifted = [DriftedFile(path=f"{prefix}{relative}", part=_part(relative)) for relative in paths]
    if moved:
        drifted.append(DriftedFile(path=f"{prefix}{HISTORY}/{HISTORY_REF}", part="history"))
    return drifted


def find_drift(layout: ReeLayout) -> list[DriftedFile]:
    """Everything of the REE and its reviews not as the last attempt left it, by its path from the REE. Nothing is
    written to the REE."""
    drifted = _drift_in(layout, layout.root)
    for review in reviews_of(layout):
        drifted += _drift_in(review, layout.root)
    return drifted


def _left(scope: ReeLayout) -> str | None:
    """The commit ree left the history's ref at: by its reflog, else the newest commit of the history ree made."""
    history = _history(scope)
    if (left := history.left_by_ree()) is not None:
        return left
    head = history.head_snapshot()
    if head is None:
        return None
    return next(
        (commit for commit in history.git("rev-list", head).stdout.decode().split() if not history.unrecorded(commit)),
        None,
    )


def history_hints(layout: ReeLayout, drift: list[DriftedFile]) -> list[str]:
    """For each history whose ref moved, the git command that puts it back where ree left it."""
    hints = []
    for item in drift:
        if item.part != "history":
            continue
        within, _, ref = item.path.partition(f"{HISTORY}/")
        review = PurePosixPath(within).name if within else None
        left = _left(layout.review(review) if review else layout)
        where = f" -C {within.rstrip('/')}" if within else ""
        hints.append(f"git{where} update-ref {ref} {left}" if left else f"git{where} update-ref -d {ref}")
    return hints


def drift_refusal(layout: ReeLayout, drift: list[DriftedFile]) -> str:
    """What ree says of an REE that changed outside it: what drifted, and how each part of it is put right."""
    named = ", ".join(item.path for item in drift[:10]) + (f" and {len(drift) - 10} more" if len(drift) > 10 else "")
    ways = [
        "write a script with `ree write-script`, or edit it in overlay/ alone so the next command records it",
        "`git restore <file>` puts a record back, and the ree command that changes it makes the change",
        *(f"`{hint}` puts the history back where ree left it" for hint in history_hints(layout, drift)),
    ]
    return f"the REE changed outside ree: {named}. " + "; ".join(ways)


def recordable_edits(layout: ReeLayout, drift: list[DriftedFile]) -> list[str]:
    """The scripts edited in ``overlay/`` that attempts can record as written, by their path from the overlay.

    Only when every drifted file is such a script: one of the REE's scripts, edited, never added or removed. Any
    other drift is recorded by nothing, so then none of them is.
    """
    history = _history(layout)
    edits = []
    for item in drift:
        relative = PurePosixPath(item.path)
        script = PurePosixPath(*relative.parts[1:]).as_posix()
        recordable = (
            item.part == "overlay"
            and is_overlay_path(script)
            and (layout.root / relative).is_file()
            and history.holds(item.path)
        )
        if not recordable:
            return []
        edits.append(script)
    return edits


def lay_out_scripts(layout: ReeLayout) -> None:
    """Make each script in the workspace what the REE records once its files were put back: the overlay's, else the
    source's, else none. A restore puts back only what the history holds, and a script's workspace copy is not."""
    scripts = {
        path.relative_to(base).as_posix()
        for base in (layout.overlay, layout.workspace)
        if base.is_dir()
        for path in base.rglob("*")
        if path.is_file() and is_overlay_path(path.relative_to(base).as_posix())
    }
    for script in sorted(scripts):
        copy = layout.workspace / script
        recorded = next(
            (base / script for base in (layout.overlay, layout.upstream) if (base / script).is_file()), None
        )
        if recorded is None:
            copy.unlink(missing_ok=True)
        elif not copy.is_file() or copy.read_bytes() != recorded.read_bytes():
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(recorded.read_bytes())
