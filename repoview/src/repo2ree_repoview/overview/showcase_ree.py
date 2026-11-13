"""The REE a showcase's authoring test sealed, read from the copy the test preserved.

The preserved copy is the REE's Git repository (``dossier/rees/<name>/ree``). Every operation is a commit whose
message carries its record, so the REE itself says what inference proposed (``generate_script_candidates``) and what
was written (``write_file``). Each script under ``overlay/`` at the seal is matched against those proposals: the
bytes of a candidate as proposed, bytes chosen over what inference proposed, bytes written where inference was asked
and proposed nothing, or bytes written without inference being asked.
"""

from __future__ import annotations

import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import JsonValue, ValidationError

from repo2ree_repoview.documents import Document

OVERLAY = "overlay/"
SCRIPTS = OVERLAY + "ree-scripts/"
SEAL = "seal_ree"
INFER = "generate_script_candidates"
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"
# Text files up to this size are shown in full.
SHOWN_BYTES = 64_000

InferenceStatus = Literal["complete", "needs_input", "not_inferred"]
Application = Literal["automatic_allowed", "confirmation_required", "unavailable"]
Written = Literal["inferred", "chosen_over", "no_candidate", "not_asked"]


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


class TargetResult(Document):
    target: ScriptTarget
    status: InferenceStatus
    application: Application
    candidates: tuple[Candidate, ...] = ()


class InferenceReport(Document):
    results: tuple[TargetResult, ...]


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
    # The candidate whose bytes it is, or, when chosen over, the one nearest to them.
    proposal: Proposal | None
    proposals: tuple[Proposal, ...]
    # What inference last answered for its path, whether or not it proposed anything.
    answer: TargetResult | None

    def diff(self) -> str:
        """How its bytes differ from the nearest proposal, as a unified diff; empty when they do not."""
        if self.proposal is None or self.written != "chosen_over":
            return ""
        return "".join(
            difflib.unified_diff(
                self.proposal.candidate.body.splitlines(keepends=True),
                self.body.splitlines(keepends=True),
                fromfile=f"proposed by {self.proposal.candidate.inference_rule}",
                tofile="written",
            )
        )


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


def _nearest(body: str, proposals: list[Proposal]) -> Proposal:
    return max(proposals, key=lambda p: difflib.SequenceMatcher(None, p.candidate.body, body).ratio())


def _script(entry: Entry, requests: tuple[Request, ...]) -> Script:
    target = entry.path.removeprefix(OVERLAY)
    body = entry.text or ""
    answers = [(request, result) for request in requests for result in request.results if result.target.path == target]
    answer = answers[-1][1] if answers else None
    proposals = tuple(
        Proposal(request, result, candidate) for request, result in answers for candidate in result.candidates
    )
    same = [proposal for proposal in proposals if proposal.candidate.body == body]
    if same:
        return Script(entry.path, body, "inferred", same[-1], proposals, answer)
    if proposals:
        return Script(entry.path, body, "chosen_over", _nearest(body, list(proposals)), proposals, answer)
    return Script(entry.path, body, "no_candidate" if answers else "not_asked", None, (), answer)


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
        requests.append(Request(commit, report.results))
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
    scripts = tuple(_script(entry, tuple(requests)) for entry in files if entry.path.startswith(SCRIPTS))
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
