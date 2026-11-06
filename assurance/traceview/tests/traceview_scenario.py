"""A recorded scenario the real checker passes: provisioning, operations with authoring between them, a seal."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import JsonValue

from repo2ree_assurance_checker import Event, Evidence, Source, Verification, VerifiedModel, load_spec, verify
from repo2ree_assurance_traceview.model import BehaviourTrace, DossierInfo
from repo2ree_assurance_traceview.operations import build_dossier, build_trace
from repo2ree_assurance_traceview.spans import Span, SpanEvent, SpanIndex

SPEC = load_spec()
REE = "ree-1"
RECEIPT = "Receipt"
START = datetime(2026, 10, 18, 10, 0, tzinfo=UTC)
REQUEST, WORKER, PROVISION = "a" * 32, "b" * 32, "c" * 32
# The journal of the workbench serving the scenario's store.
BENCH = "lab-1/workbench-000001"


def at(seconds: float) -> str:
    return (START + timedelta(seconds=seconds)).isoformat()


def clock(seconds: float) -> float:
    return (START + timedelta(seconds=seconds)).timestamp()


class Scenario:
    """Journal and Git evidence numbered the way the readers number them."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.seq = 0
        # What the next records are about; switch them to interleave several REEs in one journal.
        self.ree, self.git = REE, "git:ree"
        # Each dispatched attempt's request, which its record cites, as the supervisor's context carries it.
        self.requests: dict[str, str] = {}
        # The API journal being written, and those that ended without closing: a crashed API's.
        self.source = "api-000001"
        self.crashed: set[str] = set()
        self.bench_seq = 0

    def journal(self, t: float, trace: str | None = None, partition: str | None = None, **fields: Any) -> None:
        self.seq += 1
        self.events.append(
            Event(
                source=self.source,
                position=self.seq,
                partition=partition or self.ree,
                at=at(t),
                trace_id=trace,
                **fields,
            )
        )

    def restart(self) -> None:
        """The API crashed: its journal ends without closing, and the restarted one begins a new journal."""
        self.crashed.add(self.source)
        epoch = int(self.source.rsplit("-", 1)[1]) + 1
        self.source, self.seq = f"api-{epoch:06d}", 0

    def session(
        self, t: float, key: str, current: str | None, target: str, *, store: str = "lab-1", **facts: Any
    ) -> None:
        """A workbench's connection to ``store`` moving on, as the supervisor journals it."""
        self.journal(
            t,
            partition=store,
            kind="transition",
            owner="supervisor",
            subject="WorkbenchSession",
            key=key,
            source_state=current,
            target_state=target,
            facts={"workbench_id": "wb-1", "nonce": "n-1", "store_id": store, **facts},
        )

    def run(self, key: str, path: list[tuple[float, str]], trace: str | None = None, *, action: str) -> None:
        """A long author action, watched as run ``key``, through ``path``."""
        previous: str | None = None
        for t, state in path:
            self.action(t, key, previous, state, trace, action=action)
            previous = state

    def action(
        self, t: float, run: str, previous: str | None, state: str, trace: str | None = None, **facts: Any
    ) -> None:
        self.journal(
            t,
            trace,
            kind="transition",
            owner="api",
            subject="AuthorApiAction",
            key=f"act-{run}",
            source_state=previous,
            target_state=state,
            facts={"run_id": run, **facts},
        )

    def dispatch(
        self, attempt: str, operation: str, run_id: str, sent: float, answered: float, trace: str | None = None
    ) -> None:
        """A command started, run by an executor the workbench journals, and followed to its end."""
        self.journal(
            sent,
            trace,
            kind="send",
            owner="supervisor",
            subject="start_run",
            key=attempt,
            message="start_run",
            facts={"operation": operation, "run_id": run_id, "session": "session-1"},
        )
        self.requests[attempt] = f"{self.source}#{self.seq}"
        self.journal(
            sent, trace, kind="receive", owner="supervisor", subject="start_run", key=attempt, message="accepted"
        )
        moves: list[tuple[str | None, str, dict[str, JsonValue]]] = [
            (None, "started", {"operation": operation, "run_id": run_id, "dispatched_by": self.requests[attempt]}),
            ("started", "exited", {"exit_code": 0, "status": "succeeded"}),
        ]
        for current, target, facts in moves:
            self.bench_seq += 1
            self.events.append(
                Event(
                    source=BENCH,
                    position=self.bench_seq,
                    partition=self.ree,
                    at=at(sent if current is None else answered),
                    kind="transition",
                    owner="workbench",
                    subject="Execution",
                    key=attempt,
                    source_state=current,
                    target_state=target,
                    facts=facts,
                )
            )
        self.journal(
            sent,
            trace,
            kind="send",
            owner="supervisor",
            subject="follow_run",
            key=attempt,
            message="follow_run",
            facts={"run_id": run_id, "session": "session-1"},
        )
        self.journal(
            answered,
            trace,
            kind="receive",
            owner="supervisor",
            subject="follow_run",
            key=attempt,
            message="settled",
            facts={"status": "succeeded"},
        )

    def operation(self, run: str, action: str, attempt: str, operation: str, t: float) -> None:
        """A long author action whose one dispatched attempt succeeds."""
        self.run(run, [(t, "requested"), (t + 0.1, "running")], action=action)
        self.dispatch(attempt, operation, run, t + 0.2, t + 1.0)
        self.action(t + 1.1, run, "running", "succeeded", action=action, attempt_id=attempt)

    def provision(self, run: str, t: float, trace: str | None = None) -> None:
        """An REE's creation in a store, as the API journals it."""
        self.run(run, [(t, "requested"), (t + 0.01, "running")], trace, action="create_ree")
        self.action(t + 5.3, run, "running", "succeeded", trace, action="create_ree", store_id="lab-1")

    def commit(
        self,
        index: int,
        attempt: str | None,
        operation: str,
        run_id: str,
        steps: Sequence[tuple[str, str | None, str, str]],
        ree: tuple[str | None, str] | None,
    ) -> None:
        base, locator, sha = index * 1000, f"{self.git}@c{index}", f"c{index}" + "0" * 38
        common: dict[str, Any] = {"source": self.git, "owner": "core", "partition": self.ree, "locator": locator}
        if attempt is not None:
            # The two sides cite each other: the attempt names its request, the result the capture commit.
            pending = {"operation": operation, "run_id": run_id, "dispatched_by": self.requests.get(attempt)}
            self.events = [
                event.model_copy(update={"facts": {**event.facts, "commit": sha}})
                if event.subject == "follow_run" and event.key == attempt and event.message == "settled"
                else event
                for event in self.events
            ]
            path: list[tuple[str | None, str, dict[str, Any]]] = [
                (None, "pending", {name: value for name, value in pending.items() if value is not None}),
                ("pending", "executing", {}),
                ("executing", "completed", {"outcome": "succeeded"}),
                ("completed", "captured", {"commit": sha, "changed": True}),
            ]
            for offset, (current, target, facts) in enumerate(path):
                self.events.append(
                    Event(
                        **common,
                        position=base + offset,
                        kind="transition",
                        subject="Attempt",
                        key=attempt,
                        source_state=current,
                        target_state=target,
                        facts=facts,
                    )
                )
        for offset, (step, current, target, cause) in enumerate(steps):
            facts = {
                "step": step,
                "kind": step,
                "operation": operation if cause == "operation" else None,
                "attempt_id": attempt if cause == "operation" else None,
                "cause": cause,
            }
            self.events.append(
                Event(
                    **common,
                    position=base + 100 + offset,
                    kind="transition",
                    subject=RECEIPT,
                    key=f"{self.ree}/{step}",
                    source_state=current,
                    target_state=target,
                    facts=facts,
                )
            )
        if ree is None:  # A review history witnesses no Ree.
            return
        cause = "operation" if attempt else "created"
        self.events.append(
            Event(
                **common,
                position=base + 900,
                kind="transition",
                subject="Ree",
                key=self.ree,
                source_state=ree[0],
                target_state=ree[1],
                facts={"commit": sha, "operation": operation, "attempt_id": attempt, "cause": cause},
            )
        )


def recorded(*, sealed: bool = False, scenario: Scenario | None = None) -> Scenario:
    s = scenario or Scenario()
    s.provision("run-provision", 0.0, PROVISION)
    # The author declares where the runtime goes, then builds it.
    s.dispatch("a-patch", "patch_ree_definition", "patch-definition", 8.0, 8.2)
    s.run("run-build", [(10.0, "requested")], REQUEST, action="build_runtime")
    s.action(10.1, "run-build", "requested", "running", WORKER, action="build_runtime")
    s.dispatch("a-build", "build_runtime", "run-build", 10.2, 12.0, WORKER)
    s.action(12.1, "run-build", "running", "succeeded", WORKER, action="build_runtime", attempt_id="a-build")
    s.run("run-sbom", [(20.0, "requested"), (20.1, "running")], action="generate_sbom")
    s.dispatch("a-sbom", "generate_sbom", "run-sbom", 20.2, 21.0)
    s.action(21.1, "run-sbom", "running", "succeeded", action="generate_sbom", attempt_id="a-sbom")
    if sealed:
        # An edit stales the runtime; rebuilding refreshes it and stales the SBOM; a rescan; then the seal.
        s.dispatch("a-edit", "patch_ree_definition", "patch-definition", 30.0, 30.2)
        s.operation("run-rebuild", "build_runtime", "a-rebuild", "build_runtime", 40.0)
        s.operation("run-rescan", "generate_sbom", "a-rescan", "generate_sbom", 45.0)
        s.operation("run-seal", "seal_ree", "a-seal", "seal_ree", 50.0)

    # A new REE declares its activation, and no runtime yet: as core's first audit finds it.
    created = [
        ("runtime", None, "not_applicable", "baseline"),
        ("sbom", None, "not_applicable", "baseline"),
        ("test_activation", None, "missing", "baseline"),
    ]
    s.commit(1, None, "initialize_ree", "", created, (None, "draft"))
    declared = [
        ("runtime", "not_applicable", "missing", "operation"),
        ("sbom", "not_applicable", "missing", "operation"),
    ]
    s.commit(2, "a-patch", "patch_ree_definition", "patch-definition", declared, ("draft", "draft"))
    s.commit(
        3, "a-build", "build_runtime", "run-build", [("runtime", "missing", "current", "operation")], ("draft", "draft")
    )
    s.commit(
        4, "a-sbom", "generate_sbom", "run-sbom", [("sbom", "missing", "current", "operation")], ("draft", "draft")
    )
    if sealed:
        edited = [("runtime", "current", "stale", "operation")]
        rebuilt = [("runtime", "stale", "current", "operation"), ("sbom", "current", "stale", "operation")]
        rescanned = [("sbom", "stale", "current", "operation")]
        s.commit(5, "a-edit", "patch_ree_definition", "patch-definition", edited, ("draft", "draft"))
        s.commit(6, "a-rebuild", "build_runtime", "run-rebuild", rebuilt, ("draft", "draft"))
        s.commit(7, "a-rescan", "generate_sbom", "run-rescan", rescanned, ("draft", "draft"))
        s.commit(8, "a-seal", "seal_ree", "run-seal", [], ("draft", "sealed"))
    return s


def build_spans() -> list[Span]:
    def span(
        span_id: str, trace: str, parent: str | None, name: str, service: str, start: float, end: float, **extra: Any
    ) -> Span:
        return Span(
            id=span_id,
            trace=trace,
            parent=parent,
            name=name,
            service=service,
            kind=extra.pop("kind", "INTERNAL"),
            start=clock(start),
            end=clock(end),
            **extra,
        )

    return [
        span(
            "r1",
            REQUEST,
            None,
            "POST /api/v1/rees/{ree_id}/build-runtime",
            "api",
            9.99,
            10.05,
            kind="SERVER",
            attributes={"http.target": f"/api/v1/rees/{REE}/build-runtime"},
        ),
        span("r2", REQUEST, "r1", "POST http send", "api", 10.04, 10.04, attributes={"http.status_code": 202}),
        span("w1", WORKER, None, "run.build", "api", 10.1, 12.1),
        span("w2", WORKER, "w1", "workbench.dispatch_action", "api", 10.2, 12.0),
        span(
            "w3",
            WORKER,
            "w2",
            "workbench.request",
            "workbench",
            10.25,
            11.95,
            attributes={"repo2ree.operation": "start_run"},
        ),
        span(
            "w4",
            WORKER,
            "w3",
            "executor.build_runtime",
            "exec",
            10.6,
            11.9,
            events=(
                SpanEvent(
                    name="repo2ree.result",
                    at=clock(11.89),
                    attributes={"repo2ree.boundary": "executor.completed", "repo2ree.status": "succeeded"},
                ),
            ),
        ),
        span(
            "w5",
            WORKER,
            "w4",
            "command.build_runtime",
            "exec",
            10.6,
            11.9,
            attributes={"repo2ree.history.before_snapshot_id": "f" * 40},
        ),
        span(
            "w6",
            WORKER,
            "w5",
            "process.exec",
            "exec",
            10.65,
            11.8,
            attributes={"repo2ree.exec.argv": "sh build.sh", "repo2ree.exit_code": 0},
        ),
    ]


def verified(scenario: Scenario) -> VerifiedModel:
    gits: dict[str, set[str]] = {}
    for event in scenario.events:
        if event.source.startswith("git:"):
            gits.setdefault(event.source, set()).add(event.partition or "")
    journals = sorted({event.source for event in scenario.events if event.source.startswith("api-")} or {"api-000001"})
    sources = (
        *(
            Source(
                id=journal,
                kind="journal",
                process="api",
                rank=int(journal.rsplit("-", 1)[1]),
                hosts=frozenset({"api", "supervisor"}),
                complete=True,
                closed=journal not in scenario.crashed,
                vocabulary=SPEC.vocabulary_digest,
            )
            for journal in journals
        ),
        *(
            Source(
                id=git,
                kind="git",
                process="core",
                rank=0,
                hosts=frozenset({"core"}),
                complete=True,
                closed=False,
                partitions=frozenset(partitions),
            )
            for git, partitions in gits.items()
        ),
        Source(
            id=BENCH,
            kind="journal",
            process="workbench",
            instance="lab-1",
            rank=1,
            hosts=frozenset({"workbench"}),
            complete=True,
            closed=True,
            vocabulary=SPEC.vocabulary_digest,
        ),
    )
    evidence = Evidence(sources=sources, events=tuple(scenario.events))
    # Through the artifact, as the command line reads it: a view only ever sees what was verified.
    verification = Verification.model_validate_json(verify(SPEC, evidence).model_dump_json())
    return VerifiedModel.of(verification)


def trace_of(
    scenario: Scenario, spans: list[Span] | None = None, ree: str = REE, unreadable: int = 0
) -> BehaviourTrace:
    return build_trace(
        verified(scenario),
        SpanIndex(spans or [], unreadable),
        ree=ree,
        dossier=DossierInfo(name="synthetic"),
    )


def dossier_of(scenario: Scenario) -> BehaviourTrace:
    """The whole dossier's trace: every REE, every session, every API journal."""
    return build_dossier(verified(scenario), SpanIndex([]), dossier=DossierInfo(name="synthetic"))
