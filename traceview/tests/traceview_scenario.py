"""A recorded scenario the real checker passes: provisioning, operations with authoring between them, a seal."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from repo2ree_conformance import Event, Evidence, Source, Verification, VerifiedModel, load_spec, verify
from repo2ree_traceview.model import OperationTrace, Recording
from repo2ree_traceview.operations import build_trace
from repo2ree_traceview.spans import Span, SpanEvent, SpanIndex

SPEC = load_spec()
REE = "ree-1"
START = datetime(2026, 10, 18, 10, 0, tzinfo=UTC)
REQUEST, WORKER, PROVISION = "a" * 32, "b" * 32, "c" * 32


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
        self.ree, self.git, self.alloc = REE, "git:ree", "alloc-1"
        # Each dispatched attempt's request, which its record cites, as the supervisor's context carries it.
        self.requests: dict[str, str] = {}

    def journal(self, t: float, trace: str | None = None, **fields: Any) -> None:
        self.seq += 1
        self.events.append(
            Event(source="api-000001", position=self.seq, partition=self.ree, at=at(t), trace_id=trace, **fields)
        )

    def run(self, key: str, path: list[tuple[float, str]], trace: str | None = None, **facts: Any) -> None:
        previous: str | None = None
        for t, state in path:
            settled = state in {"succeeded", "failed", "canceled"}
            step_facts = {"operation": facts["operation"]} if previous is None else {}
            if settled:
                step_facts = {"attempt_id": facts.get("attempt_id"), "failure_category": None}
            self.journal(
                t,
                trace,
                kind="transition",
                owner="api",
                subject="Run",
                key=key,
                source_state=previous,
                target_state=state,
                facts=step_facts,
            )
            previous = state

    def allocation(self, path: list[tuple[float, str]], start: str | None = None) -> None:
        previous = start
        for t, state in path:
            self.journal(
                t,
                kind="transition",
                owner="supervisor",
                subject="Allocation",
                key=self.alloc,
                source_state=previous,
                target_state=state,
            )
            previous = state

    def dispatch(
        self, attempt: str, operation: str, run_id: str, sent: float, answered: float, trace: str | None = None
    ) -> None:
        self.journal(
            sent,
            trace,
            kind="send",
            owner="supervisor",
            subject="dispatch",
            key=attempt,
            message="exec_action",
            facts={"operation": operation, "run_id": run_id},
        )
        self.requests[attempt] = f"api-000001#{self.seq}"
        self.journal(
            answered,
            trace,
            kind="receive",
            owner="supervisor",
            subject="dispatch",
            key=attempt,
            message="result",
            facts={"status": "succeeded"},
        )

    def operation(self, run: str, kind: str, attempt: str, operation: str, t: float) -> None:
        """A background run whose one dispatched attempt succeeds."""
        self.run(run, [(t, "queued"), (t + 0.1, "running")], operation=kind)
        self.dispatch(attempt, operation, run, t + 0.2, t + 1.0)
        self.journal(
            t + 1.1,
            kind="transition",
            owner="api",
            subject="Run",
            key=run,
            source_state="running",
            target_state="succeeded",
            facts={"attempt_id": attempt, "failure_category": None},
        )

    def provision(self, run: str, t: float, trace: str | None = None) -> None:
        """A provision run, and the allocation it moves while it runs, as the API journals them."""
        self.run(run, [(t, "queued"), (t + 0.01, "provisioning")], trace, operation="provision")
        self.allocation(
            [
                (t + 0.02, "requested"),
                (t + 0.03, "provisioning"),
                (t + 5.0, "waiting_for_workbench"),
                (t + 5.1, "ready"),
                (t + 5.2, "assigned"),
            ]
        )
        self.journal(
            t + 5.3,
            kind="transition",
            owner="api",
            subject="Run",
            key=run,
            source_state="provisioning",
            target_state="succeeded",
            facts={"attempt_id": None, "failure_category": None},
            trace=trace,
        )

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
                if event.subject == "dispatch" and event.key == attempt and event.message == "result"
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
                    subject="Step",
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
    s.run("run-build", [(10.0, "queued")], REQUEST, operation="build")
    s.journal(
        10.1,
        WORKER,
        kind="transition",
        owner="api",
        subject="Run",
        key="run-build",
        source_state="queued",
        target_state="running",
        facts={},
    )
    s.dispatch("a-build", "build_runtime", "run-build", 10.2, 12.0, WORKER)
    s.journal(
        12.1,
        WORKER,
        kind="transition",
        owner="api",
        subject="Run",
        key="run-build",
        source_state="running",
        target_state="succeeded",
        facts={"attempt_id": "a-build", "failure_category": None},
    )
    s.dispatch("a-patch", "patch_ree_definition", "patch-definition", 13.0, 13.2)
    s.run("run-sbom", [(20.0, "queued"), (20.1, "running")], operation="sbom")
    s.dispatch("a-sbom", "generate_sbom", "run-sbom", 20.2, 21.0)
    s.journal(
        21.1,
        kind="transition",
        owner="api",
        subject="Run",
        key="run-sbom",
        source_state="running",
        target_state="succeeded",
        facts={"attempt_id": "a-sbom", "failure_category": None},
    )
    if sealed:
        # An edit stales the runtime; rebuilding refreshes it and stales the SBOM; a rescan; then the seal.
        s.dispatch("a-edit", "patch_ree_definition", "patch-definition", 30.0, 30.2)
        s.operation("run-rebuild", "build", "a-rebuild", "build_runtime", 40.0)
        s.operation("run-rescan", "sbom", "a-rescan", "generate_sbom", 45.0)
        s.operation("run-seal", "seal", "a-seal", "seal_ree", 50.0)
    s.allocation([(60.0, "draining"), (60.5, "released")], start="assigned")

    s.commit(1, None, "initialize_ree", "", [], (None, "draft"))
    s.commit(
        2,
        "a-build",
        "build_runtime",
        "run-build",
        [
            ("runtime", None, "missing", "baseline"),
            ("sbom", None, "missing", "baseline"),
            ("runtime", "missing", "current", "operation"),
        ],
        ("draft", "draft"),
    )
    s.commit(
        3,
        "a-patch",
        "patch_ree_definition",
        "patch-definition",
        [("test_activation", None, "missing", "operation")],
        ("draft", "draft"),
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


def provision_spans() -> list[Span]:
    """Provisioning as the supervisor, and the provider under its traceparent, record it."""
    return [
        Span(
            id="p1",
            trace=PROVISION,
            parent=None,
            name="run.provision",
            service="api",
            kind="INTERNAL",
            start=clock(0.0),
            end=clock(5.3),
        ),
        Span(
            id="p2",
            trace=PROVISION,
            parent="p1",
            name="workbench.provision",
            service="api",
            kind="INTERNAL",
            start=clock(0.01),
            end=clock(5.2),
        ),
        Span(
            id="p3",
            trace=PROVISION,
            parent="p2",
            name="provider.request",
            service="provider-docker",
            kind="INTERNAL",
            start=clock(0.04),
            end=clock(4.9),
            attributes={"repo2ree.operation": "ensure_allocation", "repo2ree.allocation_id": "alloc-1"},
        ),
        Span(
            id="p4",
            trace=PROVISION,
            parent="p3",
            name="docker.pull",
            service="provider-docker",
            kind="INTERNAL",
            start=clock(0.05),
            end=clock(1.0),
        ),
        Span(
            id="p5",
            trace=PROVISION,
            parent="p3",
            name="docker.run",
            service="provider-docker",
            kind="INTERNAL",
            start=clock(1.1),
            end=clock(1.5),
        ),
    ]


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
            attributes={"repo2ree.operation": "exec_action"},
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


def trace_of(scenario: Scenario, spans: list[Span] | None = None, ree: str = REE) -> OperationTrace:
    gits: dict[str, set[str]] = {}
    for event in scenario.events:
        if event.source.startswith("git:"):
            gits.setdefault(event.source, set()).add(event.partition or "")
    sources = (
        Source(
            id="api-000001",
            kind="journal",
            process="api",
            rank=1,
            hosts=frozenset({"api", "supervisor"}),
            complete=True,
            closed=True,
            spec_digest=SPEC.digest,
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
    )
    evidence = Evidence(sources=sources, events=tuple(scenario.events))
    # Through the artifact, as the command line reads it: a view only ever sees what was verified.
    verification = Verification.model_validate_json(verify(SPEC, evidence).model_dump_json())
    return build_trace(
        VerifiedModel.of(verification),
        SpanIndex(spans or []),
        ree=ree,
        recording=Recording(name="synthetic"),
    )
