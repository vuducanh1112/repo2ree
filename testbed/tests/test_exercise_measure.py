from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from repo2ree_testbed import exercise_measure
from repo2ree_testbed.api_models import DefinitionPatch
from repo2ree_testbed.artifacts import ROOT
from repo2ree_testbed.cli_machine import Machine
from repo2ree_testbed.exercise import Exercise, InitializeRee, PatchReeDefinition
from repo2ree_testbed.exercise_case import ExerciseCase, HandWritten, case_of, cases, write
from repo2ree_testbed.exercise_cli import Measuring
from repo2ree_testbed.exercise_measure import MEASURED, measure_all
from repo2ree_testbed.exercise_verdict import judge
from repo2ree_testbed.stack.environments import LOADED

PLAIN = Exercise(rees=("author",), steps=(InitializeRee(ree="author"),))
RENAMED = Exercise(
    rees=("author",),
    steps=(InitializeRee(ree="author"), PatchReeDefinition(ree="author", patch=DefinitionPatch(name="renamed"))),
)


def written(directory: Path, *exercises: Exercise) -> tuple[ExerciseCase, ...]:
    for number, exercise in enumerate(exercises):
        write(case_of(judge(exercise, directory / "first" / str(number)), HandWritten()), directory)
    return cases(directory)


def test_each_case_is_measured_on_a_machine_of_its_own_with_its_workdir_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = written(tmp_path, PLAIN, RENAMED)
    machines: list[tuple[str, Path]] = []

    @contextmanager
    def machine_for(name: str, mounted: Path) -> Iterator[Machine]:
        machines.append((name, mounted))
        yield Machine(MEASURED.name, name, mounted)

    def measured(
        case: ExerciseCase, workdir: Path, directory: Path, measuring: Measuring
    ) -> tuple[ExerciseCase, list[str]]:
        return case, []

    monkeypatch.setattr(exercise_measure, "machine_for", machine_for)
    monkeypatch.setattr(exercise_measure, "measure", measured)

    done = [measured_case.case.digest for measured_case in measure_all(found, tmp_path, "baseline", jobs=1)]

    assert done == [case.digest for case in found]
    assert [name for name, _ in machines] == [f"measure-{digest}" for digest in done]
    assert [mounted.name for _, mounted in machines] == done
    assert all(mounted.parent.name == "baseline" for _, mounted in machines)


@pytest.mark.skipif(
    not (LOADED / f"{MEASURED.name}.image").is_file(), reason="needs the machine: just _load-environment bare-measured"
)
def test_cases_measured_side_by_side_on_their_machines_record_their_behaviours_and_the_checkout_s_arcs(
    tmp_path: Path,
) -> None:
    found = written(tmp_path, PLAIN, RENAMED)

    measured = list(measure_all(found, tmp_path, "coverage", jobs=2))

    assert {done.case.digest for done in measured} == {case.digest for case in found}
    assert all(done.differences == () and done.arcs > 0 for done in measured)
    for case in cases(tmp_path):
        assert case.coverage is not None
        assert case.behaviours.behaviours
        assert all((ROOT / path).is_file() for path in case.coverage.files)
