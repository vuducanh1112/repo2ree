import json
import subprocess
from pathlib import Path

from pydantic import JsonValue

from repo2ree_testbed.api_models import DefinitionPatch
from repo2ree_testbed.exercise import Exercise, InitializeRee, PatchReeDefinition
from repo2ree_testbed.exercise_behaviours import Verdict
from repo2ree_testbed.exercise_case import HandWritten, case_of, cases, write
from repo2ree_testbed.exercise_cli import Ran, Replayed
from repo2ree_testbed.exercise_verdict import Trace
from repo2ree_testbed.runs.exercise_export import exported

AUTHOR = "author"
EVIDENCE = Verdict(rule="evidence", verdict="held")
IDENTITY = ("-c", "user.name=ree", "-c", "user.email=ree@repo2ree.invalid")


def _commit(root: Path, document: dict[str, object]) -> str:
    (root / "ree.json").write_text(json.dumps(document))
    subprocess.run(["git", "-C", str(root), *IDENTITY, "add", "ree.json"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), *IDENTITY, "commit", "-qm", "step"], check=True, capture_output=True)
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _ran(words: tuple[str, ...], before: str | None, after: str) -> Ran:
    history: dict[str, JsonValue] = {"scope": ".", "before_snapshot_id": before, "after_snapshot_id": after}
    return Ran(words=words, exit=0, result={"status": "succeeded", "history": history})


def test_a_case_is_exported_with_its_newest_replay_and_its_session(tmp_path: Path) -> None:
    exercise = Exercise(
        rees=(AUTHOR,),
        steps=(
            InitializeRee(ree=AUTHOR, name="first"),
            PatchReeDefinition(ree=AUTHOR, patch=DefinitionPatch(name="second")),
        ),
    )
    trace = Trace(exercise=exercise, replayed=(), problems=(), behaviours=(EVIDENCE,), spec_digest="sha256:spec")
    directory = tmp_path / "cases"
    write(case_of(trace, HandWritten()), directory)
    [case] = cases(directory)

    workdir = tmp_path / "runs" / "run-1" / "replay" / case.digest
    history = workdir / "rees" / AUTHOR
    history.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "ree-history", str(history)], check=True)
    first = _commit(history, {"subject": {"definition": {"name": "first"}}})
    second = _commit(history, {"subject": {"definition": {"name": "second"}}})
    replayed = (
        Replayed(step=0, ree=AUTHOR, operation="initialize_ree", ran=_ran(("initialize-ree",), None, first)),
        Replayed(
            step=1, ree=AUTHOR, operation="patch_ree_definition", ran=_ran(("patch-ree-definition",), first, second)
        ),
    )
    (workdir / "trace.json").write_text(trace.model_copy(update={"replayed": replayed}).model_dump_json())

    [found] = exported([case], [], tmp_path / "runs").cases

    assert found.replay is not None
    assert [step.commit for step in found.replay.steps] == [first, second]
    page = Path(found.replay.session).read_text()
    assert "ree patch-ree-definition" in page
    assert second[:10] in page
    assert found.unique_behaviours == (EVIDENCE,)


def test_a_case_with_no_replay_kept_is_exported_without_one(tmp_path: Path) -> None:
    exercise = Exercise(rees=(AUTHOR,), steps=(InitializeRee(ree=AUTHOR, name="first"),))
    trace = Trace(exercise=exercise, replayed=(), problems=(), behaviours=(), spec_digest="sha256:spec")

    [found] = exported([case_of(trace, HandWritten())], [], tmp_path / "runs").cases

    assert found.replay is None
    assert found.coverage is None
