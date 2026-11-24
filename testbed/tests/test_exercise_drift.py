from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pydantic import JsonValue

from repo2ree_testbed.api_models import DefinitionPatch
from repo2ree_testbed.exercise import (
    Drift,
    Exercise,
    FileChange,
    FileDrift,
    FilePart,
    HistoryChange,
    HistoryDrift,
    InitializeRee,
    LoadReeBundle,
    MaterializeWorkspace,
    PatchReeDefinition,
    ReflogDrift,
    RevertedDrift,
)
from repo2ree_testbed.exercise_behaviours import Verdict
from repo2ree_testbed.exercise_case import CASES, ExerciseCase
from repo2ree_testbed.exercise_cli import HISTORY_REF, CliReplay, _git, _rewrite, local_ree
from repo2ree_testbed.exercise_verdict import Trace, judge

RULE = "drift-is-found-by-the-next-attempt"


def drifted(drift: Drift) -> Exercise:
    return Exercise(
        rees=("author",),
        steps=(
            InitializeRee(ree="author"),
            MaterializeWorkspace(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="renamed")),
        ),
        drifts=(drift,),
    )


def answered(trace: Trace, step: int) -> dict[str, JsonValue]:
    ran = trace.replayed[step].ran
    assert ran is not None
    assert isinstance(ran.result, dict)
    return ran.result


def found(trace: Trace) -> None:
    assert Verdict(rule=RULE, verdict="held") in trace.behaviours
    assert [problem for problem in trace.problems if problem.rule == RULE] == []


def test_a_record_changed_is_refused_by_the_next_command(tmp_path: Path) -> None:
    trace = judge(drifted(FileDrift(before=2, ree="author", part="records", change="append")), tmp_path)

    patched = answered(trace, 2)
    assert patched["status"] == "failed"
    assert isinstance(patched["failure"], dict)
    assert patched["failure"]["details"] == {"code": "drift"}
    found(trace)


def test_a_script_edited_in_the_overlay_is_recorded_before_the_next_command(tmp_path: Path) -> None:
    trace = judge(drifted(FileDrift(before=2, ree="author", part="overlay", change="write")), tmp_path)

    assert answered(trace, 2)["status"] == "succeeded"
    found(trace)


@pytest.mark.parametrize("change", ["commit", "amend", "reset"])
def test_a_history_changed_by_git_is_refused_until_it_is_put_back(tmp_path: Path, change: HistoryChange) -> None:
    exercise = Exercise(
        rees=("author",),
        steps=(
            InitializeRee(ree="author"),
            MaterializeWorkspace(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="refused")),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="put-back")),
        ),
        drifts=(HistoryDrift(before=2, ree="author", change=change, until=3),),
    )
    trace = judge(exercise, tmp_path)

    assert answered(trace, 2)["status"] == "failed"
    assert answered(trace, 3)["status"] == "succeeded"
    found(trace)
    assert [problem for problem in trace.problems if problem.kind == "violated"] == []


def test_an_ree_no_step_initialized_yet_does_not_drift() -> None:
    steps = (InitializeRee(ree="author"),)
    early = FileDrift(before=0, ree="author", part="overlay", change="add")
    with pytest.raises(ValueError, match="before any step initialized it"):
        Exercise(rees=("author",), steps=steps, drifts=(early,))
    with pytest.raises(ValueError, match="none of the REE's"):
        FileDrift(before=1, ree="author", part="records", change="add")
    assert Exercise(rees=("author",), steps=steps, drifts=(early.model_copy(update={"before": 1}),))


def test_every_kept_case_is_named_by_its_exercise_s_digest() -> None:
    kept = sorted(CASES.glob("*.json"))
    assert kept
    for path in kept:
        case = ExerciseCase.model_validate_json(path.read_text())
        assert path.stem == case.digest, (
            f"{path.name} holds the exercise named {case.digest}: rename it and its coverage"
        )


BUNDLE = "bundles-carry-what-attempts-captured"


def test_a_bundle_is_journaled_with_the_heads_it_carries(tmp_path: Path) -> None:
    exercise = Exercise(
        rees=("author", "other"),
        steps=(
            InitializeRee(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="bundled")),
            InitializeRee(ree="other"),
            LoadReeBundle(ree="other", exported_by="author"),
        ),
    )
    trace = judge(exercise, tmp_path)

    assert answered(trace, 3)["status"] == "succeeded"
    [rule] = [
        rule
        for rule in json.loads((tmp_path / "check" / "assurance.json").read_text())["rules"]
        if rule["rule"] == BUNDLE
    ]
    assert rule["verdict"] == "passed"


def test_a_bundle_of_a_history_committed_to_with_git_is_refused(tmp_path: Path) -> None:
    exercise = Exercise(
        rees=("author", "other"),
        steps=(
            InitializeRee(ree="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="bundled")),
            InitializeRee(ree="other"),
            LoadReeBundle(ree="other", exported_by="author"),
            PatchReeDefinition(ree="author", patch=DefinitionPatch(name="put-back")),
        ),
        drifts=(HistoryDrift(before=3, ree="author", change="commit", until=4),),
    )
    trace = judge(exercise, tmp_path)

    loaded = trace.replayed[3]
    assert loaded.ran is None
    assert [ran.exit for ran in loaded.prepared] != [0]
    assert answered(trace, 4)["status"] == "succeeded"
    assert trace.problems == ()


@pytest.mark.parametrize(("part", "change"), [("overlay", "write"), ("overlay", "remove"), ("records", "mode")])
def test_a_file_put_back_by_hand_before_the_next_command_is_no_drift(
    tmp_path: Path, part: FilePart, change: FileChange
) -> None:
    trace = judge(drifted(RevertedDrift(before=2, ree="author", part=part, change=change)), tmp_path)

    assert answered(trace, 2)["status"] == "succeeded"
    assert trace.problems == ()


def test_a_commit_made_with_git_holds_the_files_as_they_are(tmp_path: Path) -> None:
    scope = tmp_path / "ree"
    scope.mkdir()
    subprocess.run(["git", "init", "--quiet", "--initial-branch=ree-history", str(scope)], check=True)
    (scope / "ree.json").write_text("{}\n")
    assert _git(scope, "add", "ree.json").returncode == 0
    assert _git(scope, "commit", "--quiet", "-m", "initialize_ree").returncode == 0
    (scope / "ree.json").write_text("{} edited\n")

    assert _rewrite(scope, "commit", 1) == ".git/refs/heads/ree-history"
    assert _git(scope, "show", f"{HISTORY_REF}:ree.json").stdout == "{} edited\n"
    assert _git(scope, "rev-list", "--count", HISTORY_REF).stdout.strip() == "2"


def test_a_reflog_lost_changes_no_file_of_the_ree(tmp_path: Path) -> None:
    replay = CliReplay(local_ree, tmp_path)
    exercise = Exercise(
        rees=("author",), steps=(InitializeRee(ree="author"),), drifts=(ReflogDrift(before=1, ree="author"),)
    )
    replay.replay(exercise)

    assert _git(replay.root("author"), "reflog", "show", HISTORY_REF, "--").stdout == ""
    journaled = (replay.journals / "environment-000001.ndjson").read_text()
    assert '"Drift"' not in journaled
