"""The REE a showcase's authoring test sealed, read from the copy the test preserved.

The preserved copy is the REE's Git repository (``dossier/rees/<name>/ree``). Every operation is a commit whose
message carries its record, so the REE itself says what inference proposed (``generate_script_candidates``) and what
was written (``write_file``). Each script under ``overlay/`` at the seal is matched against those proposals: the
bytes of a candidate as proposed, bytes chosen over what inference proposed, bytes written where inference was asked
and proposed nothing, or bytes written without inference being asked.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, JsonValue, ValidationError

from repo2ree_repoview.documents import Document

OVERLAY = "overlay/"
SCRIPTS = OVERLAY + "ree-scripts/"
# The scripts in the order an REE runs them: its environment built, then activated; its experiments after.
RUN_ORDER = (SCRIPTS + "build_experiment_environment.sh", SCRIPTS + "activate_experiment_environment.sh")
SEAL = "seal_ree"
INFER = "generate_script_candidates"
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"
# Text files up to this size are shown in full.
SHOWN_BYTES = 64_000

InferenceStatus = Literal["complete", "needs_input", "not_inferred"]
Application = Literal["automatic_allowed", "confirmation_required", "unavailable"]
Written = Literal["inferred", "chosen_over", "no_candidate", "not_asked"]
StrategyOutcome = Literal["complete", "candidate", "blocked", "not_applicable"]
NodeKind = Literal["check", "fork", "strategy_leaf", "resolve", "result"]
ContainerEngine = Literal["docker", "podman"]
EngineState = Literal["absent", "unreachable", "usable"]


class _Command(Document):
    operation: str
    args: JsonValue = None


class _Result(Document):
    status: str
    outputs: JsonValue = None


class _Record(Document):
    command: _Command
    result: _Result | None = None


class _Commit(Document):
    outcome: str
    record: _Record


class ScriptTarget(Document):
    kind: str
    experiment_name: str | None = None
    path: str


class CandidateWarning(Document):
    code: str
    severity: str


class Candidate(Document):
    candidate_id: str
    body: str
    inference_rule: str
    decision_leaf: str
    warnings: tuple[CandidateWarning, ...] = ()


class LogicalRootSeen(Document):
    kind: Literal["logical_root"]
    path: str
    wrapper_depth: int

    def summary(self) -> str:
        return f"project root {self.path or '.'}, {self.wrapper_depth} wrapper folder(s) deep"


class PathMatchesSeen(Document):
    kind: Literal["path_matches"]
    count: int
    paths: tuple[str, ...] = ()

    def summary(self) -> str:
        return f"{self.count} match(es)" + (f": {', '.join(self.paths)}" if self.paths else "")


class StrategyOutcomeSeen(Document):
    strategy: str
    outcome: StrategyOutcome
    leaf: str


class StrategyOutcomesSeen(Document):
    kind: Literal["strategy_outcomes"]
    outcomes: tuple[StrategyOutcomeSeen, ...]

    def summary(self) -> str:
        return ", ".join(f"{o.strategy} {o.outcome}" for o in self.outcomes)


class ContractSeen(Document):
    kind: Literal["experiment_environment_contract"]
    result: str
    experiment_environment_kind: str | None = None
    provenance: str | None = None
    detail: str = ""

    def summary(self) -> str:
        known = [part for part in (self.experiment_environment_kind, self.provenance, self.detail) if part]
        return self.result + (f" ({'; '.join(known)})" if known else "")


class CommandCandidatesSeen(Document):
    kind: Literal["command_candidates"]
    count: int
    sources: tuple[str, ...] = ()

    def summary(self) -> str:
        return f"{self.count} command(s)" + (f" from {', '.join(self.sources)}" if self.sources else "")


class ExperimentGateSeen(Document):
    kind: Literal["experiment_gate"]
    result: str
    requested: str = ""
    declared: bool = False

    def summary(self) -> str:
        return f"{self.requested or 'no experiment'} {'declared' if self.declared else 'not declared'}"


class EngineSeen(Document):
    engine: ContainerEngine
    state: EngineState
    server: str | None = None
    version: str | None = None
    detail: str | None = None

    def summary(self) -> str:
        served = f", served by {self.server}" if self.server and self.server != self.engine else ""
        known = f" {self.version}" if self.version else ""
        why = f" ({self.detail})" if self.detail else ""
        return f"{self.engine} {self.state}{known}{served}{why}"


class EngineProbeSeen(Document):
    status: Literal["probed", "failed", "not_probed"]
    runner: Literal["host", "container"] | None = None
    image: str | None = None
    engines: tuple[EngineSeen, ...] = ()
    detail: str = ""


class ContainerEnginesSeen(Document):
    kind: Literal["container_engines"]
    engine: ContainerEngine
    probe: EngineProbeSeen

    def summary(self) -> str:
        probe = self.probe
        if probe.status != "probed":
            return f"{self.engine}: probe {probe.status}" + (f" ({probe.detail})" if probe.detail else "")
        where = f"in {probe.image}" if probe.image else f"on the {probe.runner or 'host'}"
        return f"probed {where}: " + "; ".join(engine.summary() for engine in probe.engines)


class OtherSeen(Document):
    """An observation of a kind this view does not know yet: named, not described."""

    kind: str

    def summary(self) -> str:
        return self.kind


Observation = Annotated[
    LogicalRootSeen
    | PathMatchesSeen
    | StrategyOutcomesSeen
    | ContractSeen
    | CommandCandidatesSeen
    | ExperimentGateSeen
    | ContainerEnginesSeen
    | OtherSeen,
    Field(union_mode="left_to_right"),
]


class Step(Document):
    node_id: str
    kind: NodeKind
    check: str | None = None
    branch: str | None = None
    observed: Observation | None = None
    outcome: str | None = None

    def summary(self) -> str:
        return self.observed.summary() if self.observed else (self.outcome or "")


class Edge(Document):
    source: str
    branch: str
    target: str


class Trace(Document):
    dag: str
    version: int
    steps: tuple[Step, ...]
    edges: tuple[Edge, ...]
    result_node: str


class CheckNode(Document):
    id: str
    kind: Literal["check"]
    check: str
    branches: dict[str, str]

    def edges(self) -> list[tuple[str, str]]:
        return list(self.branches.items())


class ForkNode(Document):
    id: str
    kind: Literal["fork"]
    branches: dict[str, str]
    join: str

    def edges(self) -> list[tuple[str, str]]:
        return list(self.branches.items())


class LeafNode(Document):
    id: str
    kind: Literal["strategy_leaf"]
    strategy: str
    outcome: StrategyOutcome
    rule: str | None = None
    warnings: tuple[str, ...] = ()
    next: str

    def edges(self) -> list[tuple[str, str]]:
        return [("join", self.next)]


class ResolveNode(Document):
    id: str
    kind: Literal["resolve"]
    resolver: str
    branches: dict[str, str]

    def edges(self) -> list[tuple[str, str]]:
        return list(self.branches.items())


class ResultNode(Document):
    id: str
    kind: Literal["result"]
    status: InferenceStatus
    application: Application

    def edges(self) -> list[tuple[str, str]]:
        return []


Node = Annotated[CheckNode | ForkNode | LeafNode | ResolveNode | ResultNode, Field(discriminator="kind")]


class Dag(Document):
    key: str
    version: int
    root: str
    nodes: tuple[Node, ...]


class TargetResult(Document):
    target: ScriptTarget
    status: InferenceStatus
    application: Application
    candidates: tuple[Candidate, ...] = ()
    # Absent from records older than the trace.
    decision: Trace | None = None


class InferenceReport(Document):
    results: tuple[TargetResult, ...]


class _Dags(Document):
    dags: tuple[Dag, ...] = ()


class Sealed(Document):
    sealed_at: str
    ree_digest: str


@dataclass(frozen=True)
class Operation:
    commit: str
    operation: str
    outcome: str


@dataclass(frozen=True)
class Request:
    """One ``generate_script_candidates``: what inference answered for each target it was asked about."""

    commit: str
    results: tuple[TargetResult, ...]
    # The whole graphs its results walked, by key.
    dags: dict[str, Dag]


@dataclass(frozen=True)
class Decision:
    """How inference reached an answer: the whole graph, and the walk it took through it."""

    dag: Dag
    trace: Trace


@dataclass(frozen=True)
class Proposal:
    request: Request
    result: TargetResult
    candidate: Candidate


@dataclass(frozen=True)
class Script:
    path: str
    body: str
    written: Written
    # The candidate whose bytes it is.
    proposal: Proposal | None
    proposals: tuple[Proposal, ...]
    # What inference last answered for its path, whether or not it proposed anything.
    answer: TargetResult | None
    # How it reached that answer, where the record carries the walk and its graph.
    decision: Decision | None


@dataclass(frozen=True)
class LfsPayload:
    oid: str
    size: int


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    lfs: LfsPayload | None
    # Its text when it is small UTF-8 text; None otherwise.
    text: str | None


@dataclass(frozen=True)
class SealedRee:
    source: Path
    ree_id: str
    seal: str
    sealed: Sealed | None
    operations: tuple[Operation, ...]
    after_seal: int
    requests: tuple[Request, ...]
    scripts: tuple[Script, ...]
    files: tuple[Entry, ...]


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def _commits(repo: Path) -> list[tuple[str, str, _Commit | None]]:
    """Every commit oldest first: its hash, subject, and the operation record its message carries."""
    found = []
    for entry in _git(repo, "log", "--reverse", "--format=%H%x1f%s%x1f%b%x1e").decode().split("\x1e"):
        if not entry.strip():
            continue
        commit, subject, body = entry.strip("\n").split("\x1f", 2)
        try:
            record = _Commit.model_validate_json(body)
        except ValidationError:
            record = None
        found.append((commit, subject, record))
    return found


def _lfs(content: bytes) -> LfsPayload | None:
    if not content.startswith(LFS_POINTER):
        return None
    fields = dict(line.split(" ", 1) for line in content.decode().splitlines() if " " in line)
    return LfsPayload(oid=fields.get("oid", "").removeprefix("sha256:"), size=int(fields.get("size", "0")))


def _text(content: bytes) -> str | None:
    if len(content) > SHOWN_BYTES:
        return None
    try:
        return content.decode()
    except UnicodeDecodeError:
        return None


def _files(repo: Path, commit: str) -> tuple[Entry, ...]:
    entries = []
    for line in _git(repo, "ls-tree", "-r", "-l", "-z", "--full-tree", commit).decode().split("\0"):
        if not line:
            continue
        meta, path = line.split("\t", 1)
        _mode, kind, blob, size = meta.split()
        if kind != "blob":
            continue
        content = _git(repo, "cat-file", "blob", blob)
        lfs = _lfs(content)
        entries.append(Entry(path=path, size=int(size), lfs=lfs, text=None if lfs else _text(content)))
    return tuple(entries)


def _decision(request: Request, result: TargetResult) -> Decision | None:
    trace = result.decision
    if trace is None or trace.dag not in request.dags:
        return None
    return Decision(request.dags[trace.dag], trace)


def _script(entry: Entry, requests: tuple[Request, ...]) -> Script:
    target = entry.path.removeprefix(OVERLAY)
    body = entry.text or ""
    answers = [(request, result) for request in requests for result in request.results if result.target.path == target]
    answer = answers[-1][1] if answers else None
    decision = _decision(*answers[-1]) if answers else None
    proposals = tuple(
        Proposal(request, result, candidate) for request, result in answers for candidate in result.candidates
    )
    same = [proposal for proposal in proposals if proposal.candidate.body == body]
    if same:
        return Script(entry.path, body, "inferred", same[-1], proposals, answer, decision)
    if proposals:
        return Script(entry.path, body, "chosen_over", None, proposals, answer, decision)
    return Script(entry.path, body, "no_candidate" if answers else "not_asked", None, (), answer, decision)


def read_sealed(repo: Path, ree_id: str) -> SealedRee | None:
    """The REE in ``repo`` as of its last seal; None when it was never sealed."""
    commits = _commits(repo)
    sealed_at = max((index for index, (_, subject, _) in enumerate(commits) if subject == SEAL), default=None)
    if sealed_at is None:
        return None
    upto = commits[: sealed_at + 1]
    operations = tuple(Operation(commit, subject, record.outcome if record else "") for commit, subject, record in upto)
    requests = []
    for commit, subject, record in upto:
        if subject != INFER or record is None or record.record.result is None:
            continue
        try:
            report = InferenceReport.model_validate(record.record.result.outputs)
        except ValidationError:
            continue
        try:
            dags = _Dags.model_validate(record.record.result.outputs).dags
        except ValidationError:
            dags = ()
        requests.append(Request(commit, report.results, {dag.key: dag for dag in dags}))
    seal_commit, _, seal_record = commits[sealed_at]
    try:
        sealed = (
            Sealed.model_validate(seal_record.record.result.outputs)
            if seal_record and seal_record.record.result
            else None
        )
    except ValidationError:
        sealed = None
    files = _files(repo, seal_commit)
    scripts = tuple(
        _script(entry, tuple(requests))
        for entry in sorted(
            (entry for entry in files if entry.path.startswith(SCRIPTS)),
            key=lambda entry: (RUN_ORDER.index(entry.path) if entry.path in RUN_ORDER else len(RUN_ORDER), entry.path),
        )
    )
    return SealedRee(
        source=repo,
        ree_id=ree_id,
        seal=seal_commit,
        sealed=sealed,
        operations=operations,
        after_seal=len(commits) - len(upto),
        requests=tuple(requests),
        scripts=scripts,
        files=files,
    )


def preserved_ree(test_directory: Path, rees: tuple[str, ...]) -> SealedRee | None:
    """The first REE a test preserved that was sealed."""
    for name in rees:
        repo = test_directory / "dossier/rees" / name / "ree"
        if not (repo / ".git").is_dir():
            continue
        try:
            found = read_sealed(repo, name)
        except subprocess.CalledProcessError:
            continue
        if found is not None:
            return found
    return None
