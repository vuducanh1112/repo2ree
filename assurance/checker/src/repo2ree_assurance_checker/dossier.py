from __future__ import annotations

from pathlib import Path

from repo2ree_assurance_checker.evidence import Evidence
from repo2ree_assurance_checker.sources import (
    combine,
    git_repositories,
    history_head,
    read_git_history,
    read_journals,
    read_stores,
)
from repo2ree_assurance_dossier import read_dossier

__all__ = ["history_head", "load_dossier", "one_per_history"]


def load_dossier(directory: Path, git_executable: str = "git") -> Evidence:
    dossier = read_dossier(directory)
    parts: list[Evidence] = []
    snapshots: list[Evidence] = []
    problems: list[str] = []
    for recorded in dossier.sources:
        if recorded.kind == "spans":
            continue
        label = f"{recorded.kind} {recorded.name or recorded.path} from {recorded.origin}"
        path = directory / recorded.path
        if recorded.status != "recorded":
            problems.append(f"{label}: {recorded.status}{f' ({recorded.problem})' if recorded.problem else ''}")
            continue
        if not path.exists():
            problems.append(f"{label}: listed in the manifest but not in the dossier")
            continue
        update = {"origin": recorded.origin, "cut": recorded.cut}
        if recorded.kind == "journal":
            sources, events = read_journals(path)
            parts.append(Evidence(sources=tuple(s.model_copy(update=update) for s in sources), events=tuple(events)))
        elif recorded.kind == "git":
            if not (path / ".git").is_dir():
                problems.append(f"{label}: not an REE repository")
                continue
            for repository, name, scope in git_repositories(path, recorded.name):
                history = read_git_history(
                    repository, name, git_executable, author=not scope, scope=scope, ree=recorded.name or path.name
                )
                (source,) = history.sources
                snapshots.append(history.model_copy(update={"sources": (source.model_copy(update=update),)}))
        else:
            source, events = read_stores(path)
            parts.append(Evidence(sources=(source.model_copy(update=update),), events=tuple(events)))
    histories, diverged = one_per_history(snapshots)
    return combine(*parts, *histories, Evidence(sources=(), events=(), problems=(*problems, *diverged)))


def one_per_history(snapshots: list[Evidence]) -> tuple[list[Evidence], list[str]]:
    groups: dict[tuple[frozenset[str], str], list[Evidence]] = {}
    for snapshot in snapshots:
        (source,) = snapshot.sources
        scope = source.id.partition("/reviews/")[2]
        key = (source.partitions or frozenset({source.id}), scope)
        groups.setdefault(key, []).append(snapshot)
    kept: list[Evidence] = []
    problems: list[str] = []
    for group in groups.values():
        latest = max(group, key=lambda snapshot: len(_captured(snapshot)))
        kept.append(latest)
        held = _captured(latest)
        problems.extend(
            f"{other.sources[0].id} is not a prefix of {latest.sources[0].id}: the snapshots diverge"
            for other in group
            if other is not latest and not _captured(other).items() <= held.items()
        )
    return kept, problems


def _captured(snapshot: Evidence) -> dict[str, str]:
    attempts: dict[str, str] = {}
    for event in snapshot.events:
        if event.subject == "Attempt":
            attempts[event.key] = str(event.facts.get("commit", attempts.get(event.key, "")))
    return attempts
