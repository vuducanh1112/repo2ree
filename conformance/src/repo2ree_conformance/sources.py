"""Read owner journals, REE Git histories, and persisted stores into normalized evidence."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from repo2ree_conformance.evidence import Event, Evidence, Source

JOURNAL_NAME = re.compile(r"^(?P<process>[a-z][a-z0-9-]*)-(?P<epoch>[0-9]{6})\.ndjson$")
HISTORY_REF = "refs/heads/ree-history"
MESSAGE_KINDS = {"send", "receive", "abandon"}
TERMINAL_OUTCOMES = {"succeeded", "failed", "canceled"}


# ================================================
# Owner journals
# ================================================


def read_journal(path: Path, epoch_gap: bool = False) -> tuple[Source, list[Event]]:
    """One process epoch. Gaps, torn lines, and unknown records make it incomplete, not unreadable."""
    match = JOURNAL_NAME.match(path.name)
    if match is None:
        raise ValueError(f"{path.name}: not a journal file name")
    journal_id = path.stem
    problems: list[str] = []
    events: list[Event] = []
    header: dict[str, Any] = {}
    closed = False
    expected = 1
    lines = path.read_bytes().splitlines()
    for number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
            if not isinstance(record, dict):
                raise ValueError("expected an object")
        except ValueError as exc:
            torn = number == len(lines)
            problems.append(f"line {number}: {'torn final record' if torn else 'unreadable record'} ({exc})")
            continue
        seq = record.get("seq")
        if not isinstance(seq, int):
            problems.append(f"line {number}: record has no sequence number")
            continue
        if seq != expected:
            problems.append(f"sequence jumps from {expected - 1} to {seq}")
        expected = seq + 1
        if closed:
            problems.append(f"seq {seq}: recorded after the journal closed")
        kind = record.get("kind")
        if kind == "journal.opened":
            if seq != 1:
                problems.append(f"seq {seq}: reopened mid-journal")
            header = record
        elif kind == "journal.closed":
            closed = True
        elif kind == "transition" or kind in MESSAGE_KINDS:
            # Trace context is for views only: a malformed one is dropped, never a reason to distrust the record.
            context = record.get("trace")
            trace = {k: v for k, v in context.items() if isinstance(v, str)} if isinstance(context, dict) else {}
            try:
                events.append(
                    Event(
                        source=journal_id,
                        position=seq,
                        kind=kind,
                        owner=record["owner"],
                        subject=record["subject"],
                        key=record["key"],
                        partition=record.get("partition"),
                        source_state=record.get("from"),
                        target_state=record.get("to"),
                        message=record.get("message"),
                        facts=record.get("facts") or {},
                        at=record.get("at"),
                        trace_id=trace.get("trace_id"),
                        span_id=trace.get("span_id"),
                    )
                )
            except (KeyError, ValueError) as exc:
                problems.append(f"seq {seq}: malformed {kind} record ({exc})")
        else:
            problems.append(f"seq {seq}: unknown record kind {kind!r}")
    if not header:
        problems.append("missing journal.opened header")
    elif header.get("process") != match["process"] or header.get("epoch") != int(match["epoch"]):
        problems.append("header disagrees with the file name")
    if epoch_gap:
        problems.append("an earlier epoch of this process is missing")
    source = Source(
        id=journal_id,
        kind="journal",
        process=match["process"],
        rank=int(match["epoch"]),
        hosts=frozenset(header.get("hosts") or [match["process"]]),
        complete=not problems,
        closed=closed,
        spec_digest=header.get("spec_digest"),
        problems=tuple(problems),
    )
    return source, events


def read_journals(directory: Path) -> tuple[list[Source], list[Event]]:
    """Every epoch in a journal directory; a missing earlier epoch taints the later ones."""
    files: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for path in sorted(directory.glob("*.ndjson")):
        if match := JOURNAL_NAME.match(path.name):
            files[match["process"]].append((int(match["epoch"]), path))
    sources: list[Source] = []
    events: list[Event] = []
    for epochs in files.values():
        for index, (epoch, path) in enumerate(sorted(epochs)):
            source, found = read_journal(path, epoch_gap=epoch != index + 1)
            sources.append(source)
            events.extend(found)
    return sources, events


# ================================================
# REE Git histories
# ================================================


def git(executable: str, repository: Path, *args: str) -> str:
    return subprocess.run(
        [executable, "--no-pager", "--git-dir", str(repository / ".git"), *args],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1", "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout


@dataclass(frozen=True)
class Commit:
    id: str
    tree: str
    parent_tree: str | None
    subject: str
    metadata: dict[str, Any] | None


def history_commits(executable: str, repository: Path) -> tuple[list[Commit], list[str]]:
    """The REE's own capture history, oldest first.

    Imported histories (refs/repo2ree/imports/) describe another workbench
    lifetime; they are not this deployment's behaviour.
    """
    if not git(executable, repository, "for-each-ref", "--format=%(refname)", HISTORY_REF).split():
        return [], []
    raw = git(executable, repository, "log", "--reverse", "--format=%H%x00%T%x00%P%x00%B%x1e", HISTORY_REF, "--")
    trees: dict[str, str] = {}
    commits: list[Commit] = []
    problems: list[str] = []
    for entry in raw.split("\x1e"):
        if not entry.strip():
            continue
        commit, tree, parents, message = entry.strip("\n").split("\0", 3)
        trees[commit] = tree
        parent = parents.split()[0] if parents.split() else None
        # Every capture commit is "<operation>\n\n<json metadata>".
        subject, _, body = message.strip().partition("\n\n")
        try:
            metadata = json.loads(body)
            if not isinstance(metadata, dict):
                raise ValueError("metadata is not an object")
        except ValueError:
            problems.append(f"{commit[:12]}: commit without readable capture metadata")
            metadata = None
        commits.append(Commit(commit, tree, trees.get(parent) if parent else None, subject.strip(), metadata))
    return commits, problems


def sealed_at(executable: str, repository: Path, commit: str) -> bool | None:
    """Whether the ree.json committed in ``commit`` carries a seal; None when it cannot be read."""
    try:
        document = json.loads(git(executable, repository, "show", f"{commit}:ree.json"))
    except (subprocess.CalledProcessError, ValueError):
        return None
    return isinstance(document, dict) and document.get("seal") is not None


def pending_records(repository: Path, published: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    problems: list[str] = []
    for path in sorted((repository / ".git" / "repo2ree" / "operations").glob("*.json")):
        try:
            record = json.loads(path.read_text())
            if not isinstance(record, dict) or not isinstance(record.get("attempt_id"), str):
                raise ValueError("no attempt_id")
        except ValueError as exc:
            problems.append(f"{path.name}: unreadable pending record ({exc})")
            continue
        if record["attempt_id"] not in published:
            records.append(record)
    return records, problems


def attempt_events(
    source_id: str, base: int, record: dict[str, Any], commit: Commit | None, locator: str | None = None
) -> list[Event]:
    """The transitions an attempt record proves, in the order capture_command writes them.

    ``changed`` is witnessed from the commit's tree, not taken from the record.
    """
    context = record.get("context") or {}
    common: dict[str, Any] = {
        "source": source_id,
        "owner": "core",
        "subject": "Attempt",
        "key": record["attempt_id"],
        "partition": context.get("ree_id"),
        "locator": locator,
    }
    command = record.get("command") or {}
    steps: list[tuple[str | None, str, dict[str, Any]]] = [
        (
            None,
            "pending",
            {"operation": command.get("operation"), "run_id": record.get("run_id"), "scope": record.get("scope")},
        )
    ]
    status = record.get("operation_status")
    state = "pending"
    if status != "not_started":
        steps.append((state, "executing", {}))
        state = "executing"
    if status in TERMINAL_OUTCOMES:
        steps.append((state, "completed", {"outcome": status}))
        state = "completed"
    if commit is not None:
        steps.append((state, "captured", {"commit": commit.id, "changed": commit.tree != commit.parent_tree}))
    elif record.get("capture_status") == "failed":
        steps.append((state, "capture_failed", {"error": record.get("capture_error") or ""}))
    return [
        Event(
            **common,
            position=base + offset,
            kind="transition",
            source_state=source_state,
            target_state=target,
            facts={name: value for name, value in facts.items() if value is not None},
        )
        for offset, (source_state, target, facts) in enumerate(steps)
    ]


def step_kind(step: str) -> str:
    return "experiment" if step.startswith("experiment:") else step


@dataclass
class StepTracker:
    """Turns successive audits into Step transitions for one REE."""

    source_id: str
    ree_id: str
    states: dict[str, str] = field(default_factory=dict)

    def observe(
        self, standing: dict[str, str], base: int, locator: str, cause: str, record: dict[str, Any] | None
    ) -> list[Event]:
        operation = ((record or {}).get("command") or {}).get("operation")
        attempt_id = (record or {}).get("attempt_id")
        events: list[Event] = []
        names = sorted(set(standing) | set(self.states))
        for offset, step in enumerate(names):
            target = standing.get(step, "not_applicable")
            current = self.states.get(step)
            if target == current:
                continue
            facts: dict[str, JsonValue] = {
                "step": step,
                "kind": step_kind(step),
                "operation": operation,
                "attempt_id": attempt_id,
                "cause": cause,
            }
            events.append(
                Event(
                    source=self.source_id,
                    position=base + offset,
                    kind="transition",
                    owner="core",
                    subject="Step",
                    key=f"{self.ree_id}/{step}",
                    partition=self.ree_id,
                    source_state=current,
                    target_state=target,
                    facts=facts,
                    locator=locator,
                )
            )
            self.states[step] = target
        return events


def ree_events(
    executable: str, repository: Path, source_id: str, label: str, ree_id: str, commits: list[Commit]
) -> tuple[list[Event], list[str], StepTracker]:
    """Witnessed Ree transitions and recorded Step transitions, commit by commit."""
    events: list[Event] = []
    problems: list[str] = []
    steps = StepTracker(source_id, ree_id)
    state: str | None = None
    for index, commit in enumerate(commits):
        base = (index + 1) * 1000
        locator = f"git:{label}@{commit.id[:12]}"
        metadata = commit.metadata or {}
        record = metadata.get("record") if metadata.get("kind") == "operation.completed" else None
        if isinstance(record, dict):
            before, after = record.get("step_evidence_before"), record.get("step_evidence_after")
            if isinstance(before, dict):
                cause = "external" if steps.states else "baseline"
                events.extend(steps.observe(before, base + 100, locator, cause, None))
            if isinstance(after, dict):
                events.extend(steps.observe(after, base + 300, locator, "operation", record))
        changed = commit.tree != commit.parent_tree
        if state is not None and not changed:
            continue
        sealed = sealed_at(executable, repository, commit.id)
        if sealed is None:
            problems.append(f"{commit.id[:12]}: committed ree.json is unreadable")
            continue
        target = "sealed" if sealed else "draft"
        facts: dict[str, JsonValue] = {
            "commit": commit.id,
            "operation": commit.subject,
            "attempt_id": record.get("attempt_id") if isinstance(record, dict) else None,
            "cause": "operation" if isinstance(record, dict) else "created" if state is None else "external",
        }
        events.append(
            Event(
                source=source_id,
                position=base + 900,
                kind="transition",
                owner="core",
                subject="Ree",
                key=ree_id,
                partition=ree_id,
                source_state=state,
                target_state=target,
                facts=facts,
                locator=locator,
            )
        )
        state = target
    return events, problems, steps


def read_git_history(
    repository: Path, label: str, executable: str = "git", *, author: bool = True
) -> tuple[Source, list[Event]]:
    source_id = f"git:{label}"
    problems: list[str] = []
    events: list[Event] = []
    try:
        commits, found = history_commits(executable, repository)
        problems.extend(found)
    except (OSError, subprocess.CalledProcessError) as exc:
        commits = []
        problems.append(f"cannot read history: {exc}")
    published: list[tuple[int, Commit, dict[str, Any]]] = []
    for index, commit in enumerate(commits):
        metadata = commit.metadata or {}
        if metadata.get("kind") != "operation.completed":
            continue  # Baselines and drift snapshots are not attempts.
        record = metadata.get("record")
        if metadata.get("schema_version") != 2 or not isinstance(record, dict) or "attempt_id" not in record:
            problems.append(f"{commit.id[:12]}: unreadable operation record")
            continue
        published.append((index, commit, record))
    pending, found = pending_records(repository, {record["attempt_id"] for _, _, record in published})
    problems.extend(found)
    for index, commit, record in published:
        events.extend(attempt_events(source_id, (index + 1) * 1000, record, commit, f"git:{label}@{commit.id[:12]}"))
    for offset, record in enumerate(pending):
        locator = f"git:{label}/operations/{record['attempt_id']}.json"
        events.extend(attempt_events(source_id, (len(commits) + 1 + offset) * 1000, record, None, locator))
    ree_ids = {event.partition for event in events if event.partition is not None}
    if author and len(ree_ids) == 1:
        found_events, found, _ = ree_events(executable, repository, source_id, label, next(iter(ree_ids)), commits)
        events.extend(found_events)
        problems.extend(found)
    elif len(ree_ids) > 1:
        problems.append(f"attempts name several REEs: {sorted(ree_ids)}")
    source = Source(
        id=source_id,
        kind="git",
        process="core",
        rank=0,
        hosts=frozenset({"core"}),
        complete=not problems,
        closed=False,
        partitions=frozenset(ree_ids),
        problems=tuple(problems),
    )
    return source, events


def git_repositories(root: Path) -> Iterable[tuple[Path, str, bool]]:
    """An REE root and its review attempts; each scope keeps its own history."""
    yield root, root.name, True
    reviews = root / "reviews"
    if reviews.is_dir():
        for path in sorted(reviews.iterdir()):
            if (path / ".git").is_dir():
                yield path, f"{root.name}/reviews/{path.name}", False


# ================================================
# Persisted stores
# ================================================


def read_stores(directory: Path) -> tuple[Source, list[Event]]:
    """Final persisted owner state, observed after the owners stopped.

    Each record becomes an ``observed`` event the checker reconciles with the
    state its journal replays to; disagreement means a change went unjournaled.
    """
    events: list[Event] = []
    problems: list[str] = []
    position = 0

    def observe(owner: str, subject: str, key: str, partition: str | None, state: str, locator: str) -> None:
        nonlocal position
        position += 1
        events.append(
            Event(
                source="stores",
                position=position,
                kind="observed",
                owner=owner,
                subject=subject,
                key=key,
                partition=partition,
                target_state=state,
                locator=locator,
            )
        )

    for path in sorted((directory / "runs").glob("*/state.json")):
        try:
            run = json.loads(path.read_text())
            observe("api", "Run", run["run_id"], run["ree_id"], run["status"], f"stores/runs/{path.parent.name}")
        except (ValueError, KeyError, TypeError) as exc:
            problems.append(f"{path.parent.name}: unreadable run state ({exc})")
    allocations = directory / "allocations.json"
    if allocations.exists():
        try:
            for key, record in json.loads(allocations.read_text())["allocations"].items():
                observe(
                    "supervisor",
                    "Allocation",
                    key,
                    record["request"]["ree_id"],
                    record["state"],
                    f"stores/allocations.json#{key}",
                )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            problems.append(f"allocations.json: unreadable ({exc})")
    source = Source(
        id="stores",
        kind="store",
        process="stores",
        rank=0,
        hosts=frozenset({"api", "supervisor"}),
        complete=not problems,
        closed=True,
        problems=tuple(problems),
    )
    return source, events


# ================================================
# Loading
# ================================================


def load_evidence(
    journals: Iterable[Path] = (),
    repositories: Iterable[Path] = (),
    git_executable: str = "git",
    stores: Iterable[Path] = (),
) -> Evidence:
    sources: list[Source] = []
    events: list[Event] = []
    problems: list[str] = []
    for directory in journals:
        if not directory.is_dir():
            problems.append(f"journal directory {directory} does not exist")
            continue
        found_sources, found_events = read_journals(directory)
        sources.extend(found_sources)
        events.extend(found_events)
    for root in repositories:
        if not (root / ".git").is_dir():
            problems.append(f"{root} is not an REE repository")
            continue
        for repository, label, author in git_repositories(root):
            source, found = read_git_history(repository, label, git_executable, author=author)
            sources.append(source)
            events.extend(found)
    for directory in stores:
        source, found = read_stores(directory)
        sources.append(source)
        events.extend(found)
    if len({source.id for source in sources}) != len(sources):
        raise ValueError("two evidence sources share an identity")
    return Evidence(sources=tuple(sources), events=tuple(events), problems=tuple(problems))


def recording_inputs(recording: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Journals, preserved REE repositories, and store snapshots inside an E2E recording."""
    journals = [recording / "journal"] if (recording / "journal").is_dir() else []
    capture = recording / "capture" / "rees"
    repositories = sorted(path for path in capture.iterdir() if (path / ".git").is_dir()) if capture.is_dir() else []
    stores = [recording / "stores"] if (recording / "stores").is_dir() else []
    return journals, repositories, stores
