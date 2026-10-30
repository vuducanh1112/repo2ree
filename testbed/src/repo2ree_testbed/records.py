"""The JSON documents the testbed writes and reads, parsed at the boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, ValidationError

type Outcome = Literal["passed", "failed", "skipped", "xfailed"]
type Behaviour = Literal["passed", "violated", "inconclusive", "missing", "error"]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def but(self, **changes: object) -> Self:
        return self.model_validate({**self.model_dump(), **changes})


class Foreign(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class TestResult(Record):
    __test__ = False

    name: str
    selection: tuple[str, ...]
    outcome: Outcome
    reason: str
    exit_code: int
    started: float
    finished: float
    rees: tuple[str, ...]
    phases: dict[str, float]

    @property
    def duration(self) -> float:
        return self.finished - self.started


class RunTest(TestResult):
    directory: str
    behaviour: Behaviour | None = None
    # An execution fact beside the outcome, not part of the behaviour verdict (which
    # judges the dossier against the spec): the last workbench command that failed
    # in a failed test, as its dossier's spans recorded it. Where to look first, not
    # why the test failed — a test may fail commands on purpose, or fail without one.
    last_failed_command: str = ""

    @classmethod
    def of(cls, result: TestResult, directory: str) -> RunTest:
        return cls.model_validate({**result.model_dump(), "directory": directory})

    def judged(self, behaviour: Behaviour) -> RunTest:
        return self.but(behaviour=behaviour)


class RunRecord(Record):
    tier: str
    suite: str
    build_revision: str
    jobs: int
    whole_suite: bool = False
    # What a per-test run was limited to; empty when it ran every test its suite lists.
    selected: tuple[str, ...] = ()
    # The aggregate invocation it ran in (REPO2REE_TEST_RUN_ID), which the assurance gate finds its runs by.
    invocation: str = ""
    # The clean tree it was built from, unchanged until it ended; "" for a dirty or moving tree.
    tree: str = ""
    # What the tier's stacks were deployed with: compute locations, location mode, Docker mode.
    parameters: dict[str, str | int] = {}
    # The Docker server's os/arch and the machine (`local`, or a machines.toml name) it ran on.
    platform: str = ""
    machine: str = ""
    # For a suite against built images: each image's local ID.
    images: dict[str, str] = {}
    tests: tuple[RunTest, ...]

    def with_tests(self, tests: tuple[RunTest, ...]) -> RunRecord:
        return self.but(tests=tests)

    def problem(self) -> bool:
        return any(
            test.outcome not in {"passed", "xfailed"} or (test.outcome == "passed" and test.behaviour != "passed")
            for test in self.tests
        )


class Receipt(Foreign):
    runs: tuple[str, ...] = ()


class DossierSource(Foreign):
    kind: str
    name: str


class DossierManifest(Foreign):
    sources: tuple[DossierSource, ...] = ()

    def rees(self) -> tuple[str, ...]:
        return tuple(sorted({source.name for source in self.sources if source.kind == "git"}))


class Provenance(Foreign):
    execution_id: str


def write(path: Path, record: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2, exclude_none=True) + "\n")


def read[T: BaseModel](kind: type[T], path: Path) -> T | None:
    try:
        return kind.model_validate_json(path.read_text())
    except (OSError, ValidationError):
        return None
