"""A suite run: every test on a stack of its own, or the whole suite on one, laid out the same way.

A suite that places its tests runs each on a stack on the machine it names; a machine that cannot host
stacks side by side runs one at a time, whatever the jobs.
"""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, replace

from repo2ree_testbed import provenance
from repo2ree_testbed.artifacts import ROOT, execution_id, run_dir
from repo2ree_testbed.records import RunRecord, RunTest, TestResult, read, write
from repo2ree_testbed.stack.clients import Client, TestCase, reported_outcome
from repo2ree_testbed.stack.environments import ENVIRONMENTS, EnvironmentName
from repo2ree_testbed.stack.process import capture
from repo2ree_testbed.stack.services import Deployment
from repo2ree_testbed.stack.stack import E2EStack, Layout


@dataclass(frozen=True)
class PerTest:
    jobs: int
    # Parts of test ids; empty runs every test the suite lists.
    select: tuple[str, ...] = ()


@dataclass(frozen=True)
class WholeSuite:
    pass


type Schedule = PerTest | WholeSuite


class SuiteRun:
    def __init__(self, deployment: Deployment, client: Client, schedule: Schedule) -> None:
        self.deployment = deployment
        self.client = client
        self.schedule = schedule
        self.root = run_dir() / "e2e" / f"{deployment.tier}-{time.strftime('%Y%m%d-%H%M%S')}"
        self.revision = os.environ.get("REPO2REE_BUILD_REVISION") or capture([str(ROOT / "scripts/build-revision.sh")])
        self.tree = provenance.clean_tree()
        self.collector = bool(os.environ.get("OTLP_ENDPOINT"))
        self.lock = threading.Lock()
        self.active: set[E2EStack] = set()
        self.stopping = False
        self.last: E2EStack | None = None
        self.placed = False
        self.machines = {name: threading.Lock() for name, machine in ENVIRONMENTS.items() if not machine.parallel}

    def stop(self) -> None:
        with self.lock:
            self.stopping = True
            stacks = list(self.active)
        for stack in stacks:
            stack.stop()

    def stack(
        self, layout: Layout, selection: tuple[str, ...], *, first: bool, deployment: Deployment | None = None
    ) -> E2EStack:
        deployed = deployment or self.deployment
        stack = E2EStack(deployed, self.client, layout, selection, revision=self.revision, fresh_coverage=first)
        with self.lock:
            if self.stopping:
                raise KeyboardInterrupt
            self.active.add(stack)
        return stack

    def finish(self, tests: list[RunTest]) -> RunRecord:
        record = RunRecord(
            tier=self.deployment.tier,
            suite=self.client.suite,
            build_revision=self.revision,
            jobs=self.schedule.jobs if isinstance(self.schedule, PerTest) else 1,
            whole_suite=isinstance(self.schedule, WholeSuite),
            selected=self.schedule.select if isinstance(self.schedule, PerTest) else (),
            invocation=execution_id(),
            tree=self.tree if self.tree and provenance.clean_tree() == self.tree else "",
            parameters={
                "compute_locations": self.deployment.compute_locations,
                **({} if self.placed else {"backend": self.deployment.backend}),
                **({"environment": self.deployment.environment.name} if self.deployment.environment else {}),
            },
            platform=provenance.platform(),
            machine=provenance.machine(),
            tests=tuple(tests),
        )
        write(self.root / "run.json", record)
        if self.last is not None:
            self.last.coverage_report()
        print(f">> visualize its behaviour: just visualize-behaviour {self.root}")
        return record

    @property
    def completed(self) -> bool:
        """Whether the run got as far as recording itself, whatever its tests did."""
        return (self.root / "run.json").is_file()

    def run(self) -> int:
        if isinstance(self.schedule, WholeSuite):
            return self.run_whole()
        return self.run_per_test(self.schedule.jobs)

    def run_whole(self) -> int:
        directory = self.root / "tests/suite"
        layout = Layout.for_test(self.deployment.tier, directory, None, collector=self.collector, client_log=False)
        stack = self.stack(layout, (), first=True)
        started = time.time()
        status = stack.run_once()
        self.last = stack
        result = TestResult(
            name=f"{self.client.suite} (whole suite)",
            selection=(),
            outcome="passed" if status == 0 else "failed",
            reason="",
            exit_code=status,
            started=started,
            finished=time.time(),
            rees=layout.rees(),
            phases=stack.phases,
        )
        write(directory / "test.json", result)
        self.finish([RunTest.of(result, "tests/suite")])
        print(f">> suite run: {self.root}")
        return status

    def previous_durations(self) -> dict[str, float]:
        for path in sorted((run_dir() / "e2e").glob(f"{self.deployment.tier}-*/run.json"), reverse=True):
            record = read(RunRecord, path) if path.parent != self.root else None
            if record is not None:
                return {test.name: test.duration for test in record.tests}
        return {}

    def deployment_of(self, case: TestCase) -> Deployment:
        """The run's deployment, on the machine the test names if it names one."""
        if case.environment is None:
            return self.deployment
        machine = ENVIRONMENTS[case.environment]
        return replace(self.deployment, environment=machine, backend=machine.backend)

    def one_at_a_time(self, machine: EnvironmentName | None) -> AbstractContextManager[object]:
        lock = self.machines.get(machine) if machine is not None else None
        return lock if lock is not None else nullcontext()

    def run_case(self, case: TestCase, *, first: bool, jobs: int, total: int, index: int) -> RunTest:
        directory = self.root / "tests" / case.slug
        layout = Layout.for_test(
            self.deployment.tier, directory, case.name, collector=self.collector, client_log=jobs > 1
        )
        deployment = self.deployment_of(case)
        machine = deployment.environment.name if deployment.environment else None
        with self.one_at_a_time(machine):
            stack = self.stack(layout, case.selection, first=first, deployment=deployment)
            where = f" on {machine}" if machine else ""
            print(f">> [{index}/{total}] {case.name} on a fresh stack{where} -> {directory}")
            started = time.time()
            try:
                status = stack.run_once()
            finally:
                with self.lock:
                    self.active.discard(stack)
        outcome, reason = reported_outcome(directory / "junit.xml", status)
        result = TestResult(
            name=case.name,
            selection=case.selection,
            outcome=outcome,
            reason=reason,
            exit_code=status,
            started=started,
            finished=time.time(),
            rees=layout.rees(),
            phases=stack.phases,
            environment=machine or "",
        )
        write(directory / "test.json", result)
        with self.lock:
            self.last = stack
            print(f">> {outcome} in {result.duration:.0f} s: {case.name}")
            if outcome == "failed" and layout.client_log is not None and layout.client_log.is_file():
                tail = layout.client_log.read_text(errors="replace").splitlines()[-40:]
                print("\n".join(f"   | {line}" for line in tail))
        return RunTest.of(result, f"tests/{case.slug}")

    def run_per_test(self, jobs: int) -> int:
        cases = self.client.tests()
        if not cases:
            raise RuntimeError(f"the {self.deployment.tier} suite lists no tests")
        self.placed = any(case.environment is not None for case in cases)
        if self.placed and self.deployment.environment is not None:
            raise RuntimeError(f"the {self.deployment.tier} suite places its own tests: run it without --environment")
        if isinstance(self.schedule, PerTest) and self.schedule.select:
            cases = selected(cases, self.schedule.select, self.deployment.tier)
        durations = self.previous_durations()
        known = sorted(cases, key=lambda case: durations.get(case.name, float("inf")))
        first, rest = known[0], sorted(known[1:], key=lambda case: -durations.get(case.name, float("inf")))
        results = {first.name: self.run_case(first, first=True, jobs=jobs, total=len(cases), index=1)}
        pool = ThreadPoolExecutor(max_workers=jobs)
        try:
            futures = {
                pool.submit(self.run_case, case, first=False, jobs=jobs, total=len(cases), index=index): case
                for index, case in enumerate(rest, start=2)
            }
            for future in as_completed(futures):
                results[futures[future].name] = future.result()
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        ordered = [results[case.name] for case in cases]
        self.finish(ordered)
        print(f">> per-test run: {self.root}")
        return 0 if all(test.exit_code == 0 for test in ordered) else 1


def selected(cases: list[TestCase], select: tuple[str, ...], tier: str) -> list[TestCase]:
    """The cases whose id contains any of ``select``: a whole id, a file, or a test's name."""
    chosen = [case for case in cases if any(part in case.name for part in select)]
    if not chosen:
        raise RuntimeError(f"no test of the {tier} suite matches {' or '.join(select)}")
    print(f">> selected {len(chosen)} of {len(cases)} tests: {' or '.join(select)}")
    return chosen
