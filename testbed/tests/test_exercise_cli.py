from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import get_args

import pytest
from hypothesis import given, settings
from pydantic import JsonValue

from repo2ree_ree.signature import UnverifiedSignatureError, signed_statement
from repo2ree_testbed.api_models import ScriptTarget
from repo2ree_testbed.exercise import (
    AcquireSource,
    CrossCheckSbom,
    EvaluateReproducibility,
    Exercise,
    Fetched,
    GenerateSbom,
    InitializeRee,
    LintScripts,
    LoadReeBundle,
    MaterializeWorkspace,
    ObserveHardware,
    RemoveSource,
    SealRee,
    SignRee,
    SignReview,
    Step,
    SuggestScripts,
)
from repo2ree_testbed.exercise_case import (
    Conforms,
    CoveredFile,
    HandWritten,
    Shows,
    blobs,
    case_of,
    cases,
    coverage_of,
    drifted,
    known,
    unmeasured,
    unmet,
    write,
)
from repo2ree_testbed.exercise_cli import Answer, CliReplay, Ran, Replayed, command_of
from repo2ree_testbed.exercise_signing import OTHER_SEAL, REVIEW_PREDICATE, SEAL_PREDICATE, review_bundle, seal_bundle
from repo2ree_testbed.exercise_strategy import ALONE, AUTHOR, EXPERIMENT, REVIEWER, REVIEWING, exercises
from repo2ree_testbed.exercise_verdict import (
    Arcs,
    Covered,
    Problem,
    SoFar,
    Trace,
    answer_problems,
    digest,
    keep,
    schema_command,
)

SEAL = "sha256:" + "a" * 64
OPERATIONS = {kind.model_fields["operation"].default for kind in get_args(get_args(Step.__value__)[0])}


def every_operation() -> list[Step]:
    targets = (ScriptTarget(kind="experiment_run", experiment_name=EXPERIMENT), ScriptTarget(kind="launch"))
    steps = [stage(AUTHOR) for stage in ALONE] + [stage(REVIEWER) for stage in REVIEWING]
    return [
        *steps,
        AcquireSource(ree=AUTHOR, source=Fetched(origin_url="https://example.org/a.git", source_type="git")),
        RemoveSource(ree=AUTHOR),
        SuggestScripts(ree=AUTHOR, targets=targets),
        LintScripts(ree=AUTHOR, targets=targets),
        EvaluateReproducibility(ree=AUTHOR, strict=True),
        ObserveHardware(ree=AUTHOR),
        MaterializeWorkspace(ree=AUTHOR),
        GenerateSbom(ree=AUTHOR),
        CrossCheckSbom(ree=AUTHOR),
        SealRee(ree=AUTHOR, source_included=False),
    ]


def test_the_samples_hold_every_operation() -> None:
    assert {step.operation for step in every_operation()} == OPERATIONS


@pytest.mark.parametrize("step", every_operation(), ids=lambda step: step.operation)
def test_a_step_runs_the_command_ree_schema_gives_its_operation_with_options_it_has(step: Step) -> None:
    command = command_of(step, Path("/staged/file"))
    described = schema_command(command.words)
    assert step.operation in described["operations"]
    spelled = {word.split("=")[0] for word in command.words if word.startswith("--")}
    declared = {param["name"] for param in described["params"] if param["kind"] == "option"}
    negated = {f"--no-{name.removeprefix('--')}" for name in declared}
    assert spelled <= declared | negated
    assert (command.stdin is not None) == (described["stdin"] is not None)


def test_a_valid_seal_signature_is_read_as_the_seal_s_approval() -> None:
    statement = signed_statement(seal_bundle(SEAL, "valid"))
    assert statement.digests == {SEAL}
    assert statement.predicate_type == SEAL_PREDICATE


def test_each_wrong_seal_signature_is_wrong_in_the_way_it_names() -> None:
    with pytest.raises(UnverifiedSignatureError):
        signed_statement(seal_bundle(SEAL, "foreign_key"))
    assert signed_statement(seal_bundle(SEAL, "other_seal")).digests == {OTHER_SEAL}
    assert signed_statement(seal_bundle(SEAL, "other_claim")).predicate_type != SEAL_PREDICATE
    with pytest.raises(UnverifiedSignatureError):
        signed_statement(seal_bundle(SEAL, "tampered"))


def test_a_review_signature_carries_the_record_or_another() -> None:
    record: dict[str, JsonValue] = {"review_id": "first", "subject": {"ree_digest": SEAL}}
    valid = signed_statement(review_bundle(SEAL, record, "valid"))
    assert (valid.digests, valid.predicate_type, valid.predicate) == (frozenset({SEAL}), REVIEW_PREDICATE, record)
    assert signed_statement(review_bundle(SEAL, record, "other_record")).predicate != record
    with pytest.raises(UnverifiedSignatureError):
        signed_statement(review_bundle(SEAL, record, "foreign_key"))


@settings(max_examples=50)
@given(exercises())
def test_a_drawn_exercise_is_one_and_round_trips(exercise: Exercise) -> None:
    assert exercise.steps
    assert Exercise.model_validate_json(exercise.model_dump_json()) == exercise


class FakeRee:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def __call__(self, root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
        self.calls.append((root.name, tuple(words)))
        if words == ("bundle",):
            return Answer(2, b"", "no REE")
        result = {"status": "succeeded", "exit_code": 0, "outputs": {}, "failure": None}
        return Answer(0, json.dumps(result).encode() + b"\n", "")


def test_a_load_whose_export_is_refused_runs_no_command(tmp_path: Path) -> None:
    fake = FakeRee()
    exercise = Exercise(
        rees=(AUTHOR, REVIEWER),
        steps=(LoadReeBundle(ree=REVIEWER, exported_by=AUTHOR), RemoveSource(ree=AUTHOR)),
    )
    load, remove = CliReplay(fake, tmp_path).replay(exercise)
    assert load.ran is None
    assert load.prepared == (Ran(words=("bundle",), exit=2, log=("no REE",)),)
    assert remove.ran is not None
    [exported, (removed_in, removed)] = fake.calls
    assert exported == (AUTHOR, ("bundle",))
    assert removed_in == AUTHOR
    assert (removed[0], removed[1], removed[3], removed[-1]) == ("--json", "--run-id", "--context", "remove-source")
    assert json.loads(removed[4])["dispatch_record"] == "environment-000001#4"
    journaled = [
        json.loads(line) for line in (tmp_path / "journal" / "environment-000001.ndjson").read_text().splitlines()
    ]
    asked, refused = journaled[1:3]
    assert (asked["subject"], asked["key"], asked["partition"]) == ("export_bundle", "bundle-0", AUTHOR)
    assert (refused["key"], refused["message"], refused["facts"]) == (asked["key"], "refused", {"exit": 2})


def test_a_signature_is_made_over_the_seal_ree_shows(tmp_path: Path) -> None:
    def shows_a_seal(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
        outputs = {"ree": {"seal": {"ree_digest": SEAL}}} if "show" in words else {}
        return Answer(0, json.dumps({"status": "succeeded", "outputs": outputs}).encode(), "")

    replay = CliReplay(shows_a_seal, tmp_path)
    [signed] = replay.replay(Exercise(rees=(AUTHOR,), steps=(SignRee(ree=AUTHOR),)))
    assert signed.ran is not None
    bundle = tmp_path / signed.ran.words[signed.ran.words.index("--bundle") + 1]
    assert signed_statement(bundle.read_bytes()).digests == {SEAL}


def test_a_review_signature_is_made_over_the_record_ree_holds(tmp_path: Path) -> None:
    record = {"review_id": "first", "subject": {"ree_digest": SEAL}}

    def holds_a_record(root: Path, words: Sequence[str], stdin: bytes | None) -> Answer:
        if words[0] == "cat":
            return Answer(0, json.dumps(record).encode(), "")
        return Answer(0, b'{"status": "succeeded", "outputs": {}}', "")

    [signed] = CliReplay(holds_a_record, tmp_path).replay(
        Exercise(rees=(AUTHOR,), steps=(SignReview(ree=AUTHOR, review="first"),))
    )
    assert signed.ran is not None
    bundle = tmp_path / signed.ran.words[signed.ran.words.index("--bundle") + 1]
    assert signed_statement(bundle.read_bytes()).predicate == record


def test_an_answer_ree_schema_does_not_declare_is_a_problem() -> None:
    def step(ran: Ran) -> Replayed:
        return Replayed(step=0, ree=AUTHOR, operation="remove_source", ran=ran)

    undeclared = step(Ran(words=("remove-source",), exit=3, result=None))
    silent = step(Ran(words=("remove-source",), exit=1, result=None))
    shapeless = step(Ran(words=("remove-source",), exit=2, result={"status": "nonsense"}))
    keys = [[problem.key for problem in answer_problems([one])] for one in (undeclared, silent, shapeless)]
    assert keys == [
        [("answer", 0, "exit_status", "ree remove-source")],
        [("answer", 0, "no_result", "ree remove-source")],
        [("answer", 0, "result_shape", "ree remove-source")] * len(keys[2]),
    ]
    assert keys[2]


def trace_of(exercise: Exercise, *problems: Problem, reached: tuple[str, ...] = ("machine:Attempt",)) -> Trace:
    return Trace(exercise=exercise, replayed=(), problems=problems, reached=reached, spec_digest=SEAL)


ALONE_EXERCISE = Exercise(rees=(AUTHOR,), steps=(RemoveSource(ree=AUTHOR),))
NO_EDGE = Problem(kind="violated", rule="aggregate:Ree", subject="Ree author", detail="no edge allows it")
NO_RESULT = Problem(kind="answer", step=0, rule="no_result", subject="ree remove-source", detail="printed nothing")


def test_a_case_expects_what_its_trace_showed_and_is_read_back_by_its_exercise(tmp_path: Path) -> None:
    conforming = case_of(trace_of(ALONE_EXERCISE), HandWritten())
    showing = case_of(trace_of(Exercise(rees=(AUTHOR,), steps=(ObserveHardware(ree=AUTHOR),)), NO_EDGE), HandWritten())
    assert conforming.expects == Conforms()
    assert showing.expects == Shows(problems=(NO_EDGE,))
    assert write(conforming, tmp_path).name == f"{digest(ALONE_EXERCISE)}.json"
    write(showing, tmp_path)
    assert set(cases(tmp_path)) == {conforming, showing}
    assert known(tmp_path) == {NO_EDGE.known_as}


def test_a_case_is_unmet_by_a_problem_it_does_not_name_or_one_no_longer_shown() -> None:
    conforming = case_of(trace_of(ALONE_EXERCISE), HandWritten())
    showing = case_of(trace_of(ALONE_EXERCISE, NO_EDGE), HandWritten())
    assert unmet(conforming, trace_of(ALONE_EXERCISE)) == []
    assert unmet(conforming, trace_of(ALONE_EXERCISE, NO_EDGE)) == [f"shown, though the case conforms: {NO_EDGE}"]
    assert unmet(showing, trace_of(ALONE_EXERCISE, NO_EDGE)) == []
    assert unmet(showing, trace_of(ALONE_EXERCISE))[0].startswith("stale:")
    assert unmet(showing, trace_of(ALONE_EXERCISE, NO_RESULT)) == [
        f"no longer shown: {NO_EDGE}",
        f"shown, though the case does not name it: {NO_RESULT}",
    ]


def test_what_a_case_reaches_otherwise_is_told_not_failed() -> None:
    case = case_of(trace_of(ALONE_EXERCISE), HandWritten())
    assert drifted(case, trace_of(ALONE_EXERCISE)) is None
    told = drifted(case, trace_of(ALONE_EXERCISE, reached=("machine:Ree",)))
    assert told is not None
    assert "gained ['machine:Ree'], lost ['machine:Attempt']" in told
    assert unmet(case, trace_of(ALONE_EXERCISE, reached=("machine:Ree",))) == []


def test_each_line_names_what_no_exercise_before_it_reached(tmp_path: Path) -> None:
    def kept(name: str, reached: tuple[str, ...], arcs: Arcs) -> None:
        exercise = Exercise(rees=(AUTHOR,), steps=(InitializeRee(ree=AUTHOR, name=name),))
        workdir = tmp_path / name
        workdir.mkdir()
        keep(workdir, Trace(exercise=exercise, replayed=(), problems=(), reached=reached, spec_digest=SEAL, arcs=arcs))

    kept("first", ("machine:Attempt", "Attempt pending -> executing"), {"cli/a.py": ((1, 2), (2, 3))})
    second_arcs: Arcs = {"cli/a.py": ((2, 3), (3, 4)), "core/b.py": ((5, 6),)}
    kept("second", ("machine:Attempt", "Attempt executing -> completed"), second_arcs)
    first, second = (
        Covered.model_validate_json(line) for line in (tmp_path / "coverage.ndjson").read_text().splitlines()
    )
    assert (first.arcs, first.new_reached) == (2, ("machine:Attempt", "Attempt pending -> executing"))
    assert second.new_reached == ("Attempt executing -> completed",)
    assert (second.arcs, second.new_arcs) == (3, {"cli/a.py": ((3, 4),), "core/b.py": ((5, 6),)})
    so_far = SoFar.model_validate_json((tmp_path / "covered.json").read_text())
    assert so_far.exercises == 2
    assert so_far.arcs == {"cli/a.py": ((1, 2), (2, 3), (3, 4)), "core/b.py": ((5, 6),)}


TRACKED = "testbed/src/repo2ree_testbed/exercise.py"


def test_coverage_holds_until_a_covered_file_differs_or_is_gone() -> None:
    measured = coverage_of({TRACKED: ((1, 2),)})
    assert measured.files[TRACKED].blob == blobs((TRACKED,))[TRACKED]
    assert measured.stale() == ()
    changed = measured.model_copy(update={"files": {TRACKED: CoveredFile(blob="0" * 40, arcs=((1, 2),))}})
    assert changed.stale() == (TRACKED,)
    gone = measured.model_copy(update={"files": {"no/such/file.py": CoveredFile(blob="0" * 40, arcs=())}})
    assert gone.stale() == ("no/such/file.py",)


def test_a_case_s_coverage_is_kept_apart_and_read_back_with_it(tmp_path: Path) -> None:
    case = case_of(trace_of(ALONE_EXERCISE), HandWritten(), coverage_of({TRACKED: ((1, 2), (2, -1))}))
    path = write(case, tmp_path)
    assert "coverage" not in path.read_text()
    assert (tmp_path / "coverage" / path.name).is_file()
    [read] = cases(tmp_path)
    assert read == case
    assert unmeasured(read) is None
    assert unmeasured(read.model_copy(update={"coverage": None})) == f"{case.digest} has no coverage measured yet"
