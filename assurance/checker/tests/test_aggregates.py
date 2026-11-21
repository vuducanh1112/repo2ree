"""The Ree aggregate: every part of the committed document as a machine, and the rule they make."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import ValidationError
from test_spec import documents

from repo2ree_assurance_checker.check import check
from repo2ree_assurance_checker.check.aggregates import EXTERNAL, check_aggregate, experiment_slug, histories
from repo2ree_assurance_checker.evidence import Event, Evidence, FieldChange, FileChange, Source
from repo2ree_assurance_checker.files import load_spec
from repo2ree_assurance_checker.sources import document_parts, load_evidence
from repo2ree_assurance_checker.spec import CREATED, AggregateSpec, SubMachine

REE = "ree-1"
GIT = os.environ.get("REPO2REE_TOOL_GIT") or shutil.which("git")
GIT_ENVIRONMENT = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def ree() -> AggregateSpec:
    return load_spec().aggregates["Ree"]


def machine(kind: str, name: str) -> SubMachine:
    return next(m for m in ree().machines if (m.kind, m.name) == (kind, name))


def allowed(kind: str, name: str, source: str, target: str) -> set[str]:
    return set(machine(kind, name).allowed(source, target))


# ---------------------------------------------------------------------------- the specification


def test_every_field_and_receipt_kind_has_a_machine_after_the_lifecycle() -> None:
    machines = ree().machines
    assert machines[0].kind == "lifecycle"
    assert {m.name for m in machines if m.kind == "field"} == set(ree().fields)
    receipt_kinds = load_spec().entities["Receipt"].allowed["kind"]
    assert {m.name for m in machines if m.kind == "receipt"} == set(receipt_kinds)


def test_a_field_moves_only_by_its_writers_or_by_restoring_the_whole_document() -> None:
    assert allowed("field", "definition.experiment_environment", "set", "set") == {
        "patch_ree_definition",
        "write_script",
        "load_ree_bundle",
    }
    assert allowed("field", "definition.catalog.*", CREATED, "unset") == {"initialize_ree"}
    # An item of a keyed field starts when it is declared or restored, not with the REE.
    assert allowed("field", "definition.experiments[*]", CREATED, "set") == {"patch_ree_definition", "load_ree_bundle"}


def test_a_receipt_goes_stale_when_anything_it_was_made_from_moves() -> None:
    # The build experiment environment script is a file: writing it changes the declaration the experiment environment
    # rests on.
    assert {"write_script", "acquire_source"} <= allowed("receipt", "build_experiment_environment", "current", "stale")
    # A new experiment environment makes everything run on the old one stale, but never the experiment environment
    # itself.
    assert "build_experiment_environment" in allowed("receipt", "activate_experiment_environment", "current", "stale")
    assert "build_experiment_environment" not in allowed("receipt", "build_experiment_environment", "current", "stale")
    assert allowed("receipt", "build_experiment_environment", "missing", "current") == {
        "build_experiment_environment",
        "load_ree_bundle",
    }


def test_what_runs_through_the_activation_rests_on_it_and_the_build_does_not() -> None:
    for name in ("activate_experiment_environment", "run_experiment"):
        assert "definition.activate_experiment_environment" in ree().receipts[name].rests_on
    assert "definition.activate_experiment_environment" not in ree().receipts["build_experiment_environment"].rests_on
    assert "write_script" in allowed("receipt", "run_experiment", "current", "stale")


def test_an_experiment_is_made_from_the_activation_and_the_activation_is_about_its_script() -> None:
    assert ree().receipts["activate_experiment_environment"].about == ("definition.activate_experiment_environment",)
    assert "activate_experiment_environment" in ree().receipts["run_experiment"].made_from
    # Testing the activation again may stale every experiment run through the one before.
    assert "activate_experiment_environment" in allowed("receipt", "run_experiment", "current", "stale")


def test_the_check_of_the_working_environment_rests_on_its_script_and_the_launch() -> None:
    # The REE declares no working environment: its check says what the scripts need, and what ran it is the launch.
    assert ree().receipts["check_working_environment"].rests_on == (
        "definition.check_working_environment",
        "definition.launch",
    )
    assert "definition.working_environment" not in ree().fields


def test_whatever_makes_a_receipt_stale_may_make_it_current_again() -> None:
    # Standing is the receipt against the document as it now stands: undoing an edit undoes its staleness.
    assert {"patch_ree_definition", "write_script", "build_experiment_environment"} <= allowed(
        "receipt", "activate_experiment_environment", "stale", "current"
    )
    assert allowed("receipt", "build_experiment_environment", "current", "stale") <= allowed(
        "receipt", "build_experiment_environment", "stale", "current"
    )
    # Declaring an orphaned receipt's subject again makes it speak for the REE again.
    assert "patch_ree_definition" in allowed("receipt", "build_experiment_environment", "stale", "current")


def test_undeclaring_a_keyed_item_discards_its_receipt() -> None:
    for source in ("current", "stale", "missing"):
        assert "patch_ree_definition" in allowed("receipt", "run_experiment", source, "not_applicable")
    # An unkeyed receipt is orphaned instead, and only removing the source clears it.
    assert allowed("receipt", "build_experiment_environment", "current", "not_applicable") == {
        "remove_source",
        "load_ree_bundle",
    }


def test_an_observation_applies_without_a_declaration_and_nothing_makes_it_stale() -> None:
    assert allowed("receipt", "observe_hardware", "not_applicable", "current") == {
        "observe_hardware",
        "load_ree_bundle",
    }
    assert allowed("receipt", "observe_hardware", "current", "stale") == {"load_ree_bundle"}


def test_a_receipt_starts_applicable_only_when_what_it_is_about_is_declared_from_the_start() -> None:
    assert allowed("receipt", "activate_experiment_environment", CREATED, "missing") == {"initialize_ree"}
    assert allowed("receipt", "build_experiment_environment", CREATED, "not_applicable") == {"initialize_ree"}
    assert allowed("receipt", "run_experiment", CREATED, "missing") == {"patch_ree_definition"}


def test_what_a_receipt_rests_on_and_is_made_from_is_read_off_its_basis() -> None:
    build = ree().receipts["build_experiment_environment"]
    assert set(build.rests_on) == {
        "definition.experiment_environment",
        "definition.experiment_environment.artifact_path",
        "definition.launch",
    }
    assert build.made_from == ("acquire_source",)
    # An item's own declaration is the keyed field it falls in.
    assert "definition.experiments[*]" in ree().receipts["run_experiment"].rests_on


def test_the_evaluation_rests_on_the_source_alone() -> None:
    assert ree().receipts["evaluate_reproducibility"].made_from == ("acquire_source",)
    assert "write_script" not in allowed("receipt", "evaluate_reproducibility", "current", "stale")


def test_a_wildcard_field_is_one_machine_for_every_member_of_its_object() -> None:
    evidence = authored()
    member = change(4900, "definition.catalog.version", None, "1", "patch_ree_definition", "operation")
    moves = counted(evidence.model_copy(update={"changes": (*evidence.changes, member)}))
    assert moves[("definition.catalog.*", "unset", "set", "patch_ree_definition")] == 1
    history = histories(load_spec(), evidence.model_copy(update={"changes": (*evidence.changes, member)}))[0]
    assert "definition.catalog.version" in {part.name for part in history.parts}


def test_whole_document_operations_are_marked_bulk_for_views() -> None:
    assert set(machine("receipt", "build_experiment_environment").bulk) == {"load_ree_bundle", "remove_source"}
    assert machine("field", "definition.name").bulk == ("load_ree_bundle",)


def mutated(change: Any) -> dict[str, Any]:
    aggregate: dict[str, Any] = documents().aggregates[0]
    change(aggregate)
    return aggregate


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda a: a["receipts"]["build_experiment_environment"]["basis"].append(
                {"recorded": "x", "now": "definition.nothing"}
            ),
            "which no field or receipt holds",
        ),
        (
            lambda a: a["receipts"]["build_experiment_environment"].update(rests_on=["definition.launch"]),
            "read off its basis, never stated beside it",
        ),
        (
            lambda a: a["receipts"]["generate_sbom"]["basis"].append(
                {"recorded": "x", "now": "definition.experiments[$name].run_script_digest"}
            ),
            "only a keyed receipt's basis names its own item",
        ),
        (
            lambda a: (
                a["receipts"]["generate_sbom"]["basis"].append({"recorded": "x.y", "now": "definition.launch"})
                or a["receipts"]["generate_sbom"]["basis"].append({"recorded": "items[*]", "now": "definition.launch"})
            ),
            "records values of the receipt itself",
        ),
        (
            lambda a: a["fields"].update(
                {"definition.hbom.*": {"group": "observe_hardware", "initial": "unset", "files": ["x.sh"]}}
            ),
            "claim no files",
        ),
        (
            lambda a: a["receipts"]["build_experiment_environment"].update(about=["definition.experiments[*]"]),
            "is not keyed",
        ),
        (
            lambda a: a["receipts"]["generate_sbom"]["basis"].append(
                {"recorded": "x", "now": "receipts.experiments.one.run_script_digest"}
            ),
            "other, unkeyed receipts",
        ),
        (lambda a: a["fields"]["definition.experiments[*]"].update(initial="unset"), "needs an initial state"),
        (lambda a: a.update(writes_nothing=["write_script"]), "write nothing take edges"),
        (lambda a: a.pop("overlay"), "names no overlay"),
        (lambda a: a.pop("signed_by"), "names signatures exactly when"),
        (lambda a: a.pop("signatures"), "names signatures exactly when"),
        (lambda a: a.update(writes_nothing=["sign_ree"]), "operations that sign write a signature"),
        (
            lambda a: a["fields"]["definition.experiment_environment"].update(files=["ree-scripts/{slug}.sh"]),
            "name its item once",
        ),
        (lambda a: a["fields"]["definition.experiments[*]"].update(files=["ree-scripts/x.sh"]), "name its item once"),
        (
            lambda a: a["fields"]["definition.activate_experiment_environment"].update(
                files=["ree-scripts/build_experiment_environment.sh"]
            ),
            "claimed by more than one field",
        ),
    ],
)
def test_incoherent_aggregates_are_rejected(change: Any, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        AggregateSpec.model_validate(mutated(change))


def test_an_aggregate_must_describe_exactly_the_receipt_kinds_its_receipt_entity_lists() -> None:
    docs = documents()
    del docs.aggregates[0]["receipts"]["cross_check_sbom"]
    with pytest.raises(ValidationError, match="are not the kinds Receipt lists"):
        docs.parse()


# ---------------------------------------------------------------------------- reading the document


def test_document_parts_leave_out_what_is_empty_and_key_named_lists_by_name() -> None:
    parts = document_parts(
        {
            "definition": {
                "name": "demo",
                "catalog": {"description": "", "keywords": []},
                "experiments": [{"name": "one", "run_script_digest": "a"}],
            },
            "contents": {"entries": []},
        }
    )
    assert set(parts) == {
        "definition",
        "definition.name",
        "definition.experiments",
        "definition.experiments[one]",
        "definition.experiments[one].name",
        "definition.experiments[one].run_script_digest",
    }


def test_a_change_deep_in_the_document_changes_every_part_above_it() -> None:
    before = document_parts({"definition": {"experiment_environment": {"artifact_path": None, "script": "a"}}})
    after = document_parts({"definition": {"experiment_environment": {"artifact_path": "venv", "script": "a"}}})
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert changed == {
        "definition",
        "definition.experiment_environment",
        "definition.experiment_environment.artifact_path",
    }


def ree_commit(root: Path, operation: str, metadata: dict[str, Any], environment: dict[str, str]) -> str:
    """Commit what is staged in ``root`` as ree does: its message names the commit's parent and tree."""
    assert GIT is not None

    def run(*words: str) -> str:
        return subprocess.run(
            [GIT, "-C", str(root), *words], check=True, env=environment, capture_output=True, text=True
        ).stdout.strip()

    tree = run("write-tree")
    parent = (
        subprocess.run(
            [GIT, "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD"],
            env=environment,
            capture_output=True,
            text=True,
        ).stdout.strip()
        or None
    )
    message = f"{operation}\n\n{json.dumps({**metadata, 'parent': parent, 'tree': tree})}"
    commit = run("commit-tree", tree, *(("-p", parent) if parent else ()), "-m", message)
    run("update-ref", "HEAD", commit)
    return commit


def commit_document(root: Path, operation: str, document: dict[str, Any], record: dict[str, Any] | None) -> None:
    assert GIT is not None
    environment = {**os.environ, **GIT_ENVIRONMENT}
    (root / "ree.json").write_text(json.dumps(document))
    metadata = {"kind": "operation.completed", "schema_version": 2, "record": record} if record else {"kind": "x"}
    subprocess.run([GIT, "-C", str(root), "add", "ree.json"], check=True, env=environment)
    ree_commit(root, operation, metadata, environment)


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_each_capture_commit_reports_the_document_parts_it_changed(tmp_path: Path) -> None:
    assert GIT is not None
    root = tmp_path / "ree"
    subprocess.run([GIT, "init", "-q", "-b", "ree-history", str(root)], check=True)
    created = {"subject": {"definition": {"name": "demo"}}}
    commit_document(root, "initialize_ree", created, None)
    record = {"attempt_id": "a1", "context": {"ree_id": REE}, "command": {"operation": "patch_ree_definition"}}
    patched = {"subject": {"definition": {"name": "demo", "catalog": {"version": "1"}}}}
    commit_document(root, "patch_ree_definition", patched, record | {"operation_status": "succeeded"})
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    moved = [(c.cause, c.operation, c.path, c.before is None, c.after is None) for c in evidence.changes]
    assert moved == [
        ("created", "initialize_ree", "definition", True, False),
        ("created", "initialize_ree", "definition.name", True, False),
        ("operation", "patch_ree_definition", "definition", False, False),
        ("operation", "patch_ree_definition", "definition.catalog", True, False),
        ("operation", "patch_ree_definition", "definition.catalog.version", True, False),
    ]


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_changes_across_an_unreadable_document_are_owned_by_no_operation(tmp_path: Path) -> None:
    assert GIT is not None
    root = tmp_path / "ree"
    subprocess.run([GIT, "init", "-q", "-b", "ree-history", str(root)], check=True)
    commit_document(root, "initialize_ree", {"subject": {"definition": {"name": "demo"}}}, None)
    record = {"attempt_id": "a1", "context": {"ree_id": REE}, "command": {"operation": "write_script"}}
    (root / "ree.json").write_text("not json")
    environment = {**os.environ, **GIT_ENVIRONMENT}
    subprocess.run(
        [GIT, "-C", str(root), "commit", "-qam", "write_script\n\n" + json.dumps({"kind": "x"})],
        check=True,
        env=environment,
    )
    patched = {"subject": {"definition": {"name": "demo", "catalog": {"version": "1"}}}}
    commit_document(root, "patch_ree_definition", patched, record | {"operation_status": "succeeded"})
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    assert {change.cause for change in evidence.changes} == {"created"}
    assert any("ree.json is unreadable" in problem for problem in evidence.sources[0].problems)


# ---------------------------------------------------------------------------- judging the moves


def git_source() -> Source:
    return Source(
        id="git:ree",
        kind="git",
        process="core",
        rank=0,
        hosts=frozenset({"core"}),
        complete=True,
        closed=False,
        partitions=frozenset({REE}),
    )


def commit(position: int) -> str:
    """Where the readers place a commit's records: every record of commit N shares its locator."""
    return f"git:ree@c{position // 1000}"


def lifecycle(position: int, source: str | None, target: str, operation: str, cause: str) -> Event:
    return Event(
        source="git:ree",
        position=position,
        kind="transition",
        owner="core",
        subject="Ree",
        key=REE,
        partition=REE,
        source_state=source,
        target_state=target,
        facts={"operation": operation, "cause": cause},
        locator=commit(position),
    )


def receipt(position: int, step: str, source: str | None, target: str, operation: str | None, cause: str) -> Event:
    return Event(
        source="git:ree",
        position=position,
        kind="transition",
        owner="core",
        subject="Receipt",
        key=f"{REE}/{step}",
        partition=REE,
        source_state=source,
        target_state=target,
        facts={"step": step, "kind": step.partition(":")[0], "operation": operation, "cause": cause},
        locator=commit(position),
    )


type Cause = Literal["created", "operation", "external"]


def change(
    position: int, path: str, before: str | None, after: str | None, operation: str, cause: Cause
) -> FieldChange:
    return FieldChange(
        source="git:ree",
        position=position,
        partition=REE,
        path=path,
        before=before,
        after=after,
        operation=operation,
        cause=cause,
        locator=commit(position),
    )


def authored() -> Evidence:
    """Created, an experiment environment declared and built, an experiment declared and run, then sealed."""
    return Evidence(
        sources=(git_source(),),
        events=(
            lifecycle(1900, None, "draft", "initialize_ree", "created"),
            receipt(2100, "build_experiment_environment", None, "not_applicable", None, "baseline"),
            receipt(
                2300, "build_experiment_environment", "not_applicable", "missing", "patch_ree_definition", "operation"
            ),
            receipt(
                3300, "build_experiment_environment", "missing", "current", "build_experiment_environment", "operation"
            ),
            receipt(4300, "run_experiment:one", None, "missing", "patch_ree_definition", "operation"),
            receipt(5300, "run_experiment:one", "missing", "current", "run_experiment", "operation"),
            lifecycle(6900, "draft", "sealed", "seal_ree", "operation"),
        ),
        changes=(
            *(
                change(1900, path, None, "x", "initialize_ree", "created")
                for path in (
                    "capture",
                    "definition.name",
                    "definition.experiment_environment",
                    "definition.activate_experiment_environment",
                    "definition.launch",
                    "definition.check_working_environment",
                )
            ),
            change(
                2900,
                "definition.experiment_environment.artifact_path",
                None,
                "p",
                "patch_ree_definition",
                "operation",
            ),
            change(4900, "definition.experiments[one]", None, "e", "patch_ree_definition", "operation"),
            change(
                4900, "definition.experiments[one].run_script_digest", None, "d", "patch_ree_definition", "operation"
            ),
            change(6900, "contents", None, "c", "seal_ree", "operation"),
        ),
    )


def counted(evidence: Evidence) -> dict[tuple[str, str, str, str], int]:
    result = check_aggregate(ree(), evidence)
    return {(m.machine, m.source, m.target, m.operation): m.count for m in result.moves}


def test_every_part_is_counted_under_the_operation_that_moved_it() -> None:
    moves = counted(authored())
    assert moves[("lifecycle", CREATED, "draft", "initialize_ree")] == 1
    assert moves[("lifecycle", "draft", "sealed", "seal_ree")] == 1
    # Unkeyed fields start where the creating commit left them, whether it held them or not.
    assert moves[("definition.name", CREATED, "set", "initialize_ree")] == 1
    assert moves[("definition.experiment_environment.artifact_path", "unset", "set", "patch_ree_definition")] == 1
    # A keyed item starts when it is declared; the parts inside it are not fields of their own.
    assert moves[("definition.experiments[*]", CREATED, "set", "patch_ree_definition")] == 1
    # A receipt's first audited standing is the one the REE was created with.
    assert moves[("build_experiment_environment", CREATED, "not_applicable", "initialize_ree")] == 1
    assert moves[("run_experiment", "missing", "current", "run_experiment")] == 1
    assert not check_aggregate(ree(), authored()).findings


def test_a_move_no_edge_allows_is_reported_with_its_evidence() -> None:
    evidence = authored()
    late = change(7900, "definition.catalog.version", None, "2", "run_experiment", "operation")
    drift = receipt(7100, "build_experiment_environment", "current", "stale", None, "external")
    result = check_aggregate(
        ree(), evidence.model_copy(update={"changes": (*evidence.changes, late), "events": (*evidence.events, drift)})
    )
    reasons = sorted((finding.subject, finding.reason, finding.evidence) for finding in result.findings)
    assert reasons == [
        (
            f"Ree {REE} build_experiment_environment",
            f"current -> stale by {EXTERNAL}, which no edge allows",
            ("git:ree@c7",),
        ),
        (
            f"Ree {REE} definition.catalog.version",
            "unset -> set by run_experiment, which no edge allows",
            ("git:ree@c7",),
        ),
    ]


def test_a_move_no_edge_allows_violates_the_aggregate_rule() -> None:
    evidence = authored()
    late = change(7900, "definition.catalog.version", None, "2", "run_experiment", "operation")
    disallowed = evidence.model_copy(update={"changes": (*evidence.changes, late)})
    spec = load_spec()
    before, after = check(spec, evidence), check(spec, disallowed)

    def rule(result: Any) -> Any:
        return next(rule for rule in result.rules if rule.rule == "aggregate:Ree")

    assert (rule(before).kind, rule(before).verdict) == ("aggregate", "passed")
    assert rule(before).triggered == sum(move.count for move in before.aggregates[0].moves)
    assert rule(after).findings == after.aggregates[0].findings
    assert (rule(after).verdict, after.verdict) == ("violated", "violated")
    # Every other rule judges the same evidence as before.
    assert [r for r in after.rules if r.kind != "aggregate"] == [r for r in before.rules if r.kind != "aggregate"]


def test_each_instance_is_replayed_step_by_step_with_what_each_operation_moved() -> None:
    (replayed,) = histories(load_spec(), authored())
    steps = [(step.operation, step.moved) for step in replayed.steps]
    # The standings first audited belong to the step that created the REE, which moves nothing yet.
    assert steps[0] == ("initialize_ree", ())
    assert ("patch_ree_definition", ("run_experiment[one]", "definition.experiments[one]")) in steps
    assert steps[-1] == ("seal_ree", ("lifecycle", "contents"))
    final = replayed.steps[-1].states
    assert (final["lifecycle"], final["build_experiment_environment"], final["run_experiment[one]"]) == (
        "sealed",
        "current",
        "current",
    )
    names = [part.name for part in replayed.parts]
    # Drawing order: the lifecycle, each receipt after what it is about, the other groups last.
    assert names[0] == "lifecycle"
    assert names.index("definition.experiment_environment.artifact_path") < names.index("build_experiment_environment")
    assert names.index("run_experiment[one]") < names.index("definition.name")
    item = next(part for part in replayed.parts if part.name == "run_experiment[one]")
    assert (item.machine, item.item, item.group) == ("run_experiment", "one", "run_experiment")


# ---------------------------------------------------------------------------- the overlay


@pytest.mark.parametrize(
    ("path", "claim"),
    [
        ("ree-scripts/build_experiment_environment.sh", ("definition.experiment_environment", "")),
        ("ree-scripts/activate_experiment_environment.sh", ("definition.activate_experiment_environment", "")),
        ("ree-scripts/test_activation.sh", None),
        ("ree-scripts/experiments/train-model.sh", ("definition.experiments[*]", "train-model")),
        ("ree-scripts/experiments/train-model.verify.sh", ("definition.experiments[*]", "train-model")),
        ("ree-scripts/experiments/nested/train.sh", None),
        ("ree-scripts/experiments/.sh", None),
        ("instant/requirements-extra.txt", None),
    ],
)
def test_each_script_is_claimed_by_the_field_that_declares_it(path: str, claim: tuple[str, str] | None) -> None:
    assert ree().claim(path) == claim


def test_an_item_is_named_in_its_files_by_the_slug_the_product_gives_it() -> None:
    slugs = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts/ree/fixtures/experiment-slugs.json").read_text()
    )
    for case in slugs["cases"]:
        assert experiment_slug(case["name"]) == case["slug"]


def file(
    position: int,
    path: str,
    before: str | None,
    after: str | None,
    operation: str,
    cause: Cause,
    storage: Literal["git", "lfs"] = "git",
    named_by: tuple[str, ...] = (),
) -> FileChange:
    return FileChange(
        source="git:ree",
        position=position,
        partition=REE,
        path=path,
        before=before,
        after=after,
        operation=operation,
        cause=cause,
        locator=commit(position),
        storage=storage if after is not None else None,
        named_by=named_by,
    )


def overlay_findings(*files: FileChange, changes: tuple[FieldChange, ...] = ()) -> list[str]:
    evidence = authored()
    evidence = evidence.model_copy(update={"changes": (*evidence.changes, *changes), "files": files})
    result = check_aggregate(ree(), evidence)
    assert result.files == len(files)
    return [f"{finding.subject}: {finding.reason}" for finding in result.findings]


def test_a_script_changes_with_the_field_that_declares_it() -> None:
    build = "overlay/ree-scripts/build_experiment_environment.sh"
    run = "overlay/ree-scripts/experiments/one.sh"
    assert (
        overlay_findings(
            file(1900, build, None, "b1", "initialize_ree", "created"),
            file(5900, run, None, "r1", "write_script", "operation"),
            changes=(
                change(5900, "definition.experiments[one].run_script_digest", "d", "d2", "write_script", "operation"),
            ),
        )
        == []
    )
    assert overlay_findings(file(5900, build, "b1", "b2", "write_script", "operation")) == [
        f"Ree {REE} {build}: changed by write_script, but definition.experiment_environment, which claims it, did not"
    ]


def test_scripts_of_what_is_not_declared_need_no_field_to_change() -> None:
    assert (
        overlay_findings(
            file(5900, "overlay/ree-scripts/experiments/not-yet.sh", None, "r", "write_script", "operation"),
            file(5900, "overlay/ree-scripts/experiments/not-yet.verify.sh", None, "v", "write_script", "operation"),
        )
        == []
    )


def test_a_file_no_field_claims_violates_the_aggregate_rule() -> None:
    extra = "overlay/instant/requirements-extra.txt"
    assert overlay_findings(file(5900, extra, None, "m", "write_script", "operation")) == [
        f"Ree {REE} {extra}: is in the overlay, but no field claims it",
        f"Ree {REE} {extra}: is committed, but no entry of the tree is it (it falls in overlay)",
    ]
    # Taking it away again is what the rule asks for.
    assert overlay_findings(file(5900, extra, "m", None, "write_script", "operation")) == []


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_each_capture_commit_reports_the_files_it_changed(tmp_path: Path) -> None:
    assert GIT is not None
    root = tmp_path / "ree"
    subprocess.run([GIT, "init", "-q", "-b", "ree-history", str(root)], check=True)
    (root / "overlay/ree-scripts").mkdir(parents=True)
    (root / "overlay/ree-scripts/build_experiment_environment.sh").write_text("echo one\n")
    subprocess.run([GIT, "-C", str(root), "add", "overlay"], check=True)
    commit_document(root, "initialize_ree", {"subject": {"definition": {"name": "demo"}}}, None)
    (root / "overlay/ree-scripts/build_experiment_environment.sh").write_text("echo two\n")
    (root / "overlay/notes.txt").write_text("kept\n")
    subprocess.run([GIT, "-C", str(root), "add", "overlay"], check=True)
    record = {"attempt_id": "a1", "context": {"ree_id": REE}, "command": {"operation": "write_script"}}
    commit_document(
        root, "write_script", {"subject": {"definition": {"name": "demo"}}}, record | {"operation_status": "succeeded"}
    )
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    moved = [(c.cause, c.operation, c.path, c.before is None, c.after is None) for c in evidence.files]
    assert moved == [
        ("created", "initialize_ree", "overlay/ree-scripts/build_experiment_environment.sh", True, False),
        ("created", "initialize_ree", "ree.json", True, False),
        ("operation", "write_script", "overlay/notes.txt", True, False),
        ("operation", "write_script", "overlay/ree-scripts/build_experiment_environment.sh", False, False),
    ]


def tree_findings(*files: FileChange) -> list[str]:
    evidence = authored().model_copy(update={"files": files})
    result = check_aggregate(ree(), evidence)
    assert result.committed == len([f for f in files if f.after is not None])
    return [f"{finding.subject}: {finding.reason}" for finding in result.findings]


ARTIFACT_PATH = "definition.experiment_environment.artifact_path"


def test_what_a_capture_commits_is_an_entry_of_the_tree_stored_as_it_says() -> None:
    assert (
        tree_findings(
            file(1900, "ree.json", None, "j", "initialize_ree", "created"),
            file(1900, "snapshot.tar.gz", None, "s", "seal_ree", "operation", "lfs"),
            file(1900, "artifacts/sbom.json", None, "b", "generate_sbom", "operation"),
            file(1900, "artifacts/runtime.tar", None, "r", "seal_ree", "operation", "lfs", (ARTIFACT_PATH,)),
            file(1900, "results/train/metrics/out.json", None, "o", "seal_ree", "operation", "lfs"),
            file(1900, "reviews/r1/review.json", None, "v", "review_acquire_source", "operation"),
            file(1900, "reviews/r1/receipts/experiments/train.json", None, "e", "review_run_experiment", "operation"),
            file(1900, "reviews/r1/overlay/ree-scripts/experiments/train.sh", None, "t", "review_acquire", "operation"),
        )
        == []
    )


def test_a_file_the_tree_does_not_name_or_never_captures_violates_the_aggregate_rule() -> None:
    assert tree_findings(
        file(1900, "artifacts/runtime.tar", None, "r", "seal_ree", "operation", "lfs"),
        file(1900, "notes.txt", None, "n", "write_script", "operation"),
        file(1900, "workspace/build/out.o", None, "w", "seal_ree", "operation"),
        file(1900, "reviews/r1/runs/a.ndjson", None, "l", "review_run_experiment", "operation"),
    ) == [
        f"Ree {REE} artifacts/runtime.tar: is committed, but no entry of the tree is it (it falls in artifacts)",
        f"Ree {REE} notes.txt: is committed, but no entry of the tree is it (it falls in .)",
        f"Ree {REE} workspace/build/out.o: is committed, but the tree never captures workspace",
        (
            f"Ree {REE} reviews/r1/runs/a.ndjson: is committed, but the tree never captures "
            "reviews/{review}/runs/{run}.ndjson"
        ),
    ]


def test_a_file_stored_otherwise_than_the_tree_says_violates_the_aggregate_rule() -> None:
    assert tree_findings(
        file(1900, "snapshot.tar.gz", None, "s", "seal_ree", "operation", "git"),
        file(1900, "artifacts/sbom.json", None, "b", "generate_sbom", "operation", "lfs"),
    ) == [
        f"Ree {REE} snapshot.tar.gz: is stored as git, but the tree stores snapshot.tar.gz as lfs",
        f"Ree {REE} artifacts/sbom.json: is stored as lfs, but the tree stores artifacts/sbom.json as git",
    ]
    # A removal is not judged: the file is no longer committed.
    assert tree_findings(file(1900, "notes.txt", "n", None, "write_script", "operation")) == []


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_a_committed_file_records_how_it_is_stored_and_which_fields_name_it(tmp_path: Path) -> None:
    assert GIT is not None
    root = tmp_path / "ree"
    subprocess.run([GIT, "init", "-q", "-b", "ree-history", str(root)], check=True)
    (root / "artifacts").mkdir()
    (root / "artifacts/runtime.tar").write_text("environment\n")
    (root / "snapshot.tar.gz").write_text("snapshot\n")
    (root / ".gitattributes").write_text('"/snapshot.tar.gz" filter=lfs diff=lfs merge=lfs -text\n')
    subprocess.run([GIT, "-C", str(root), "add", "."], check=True)
    document = {"subject": {"definition": {"experiment_environment": {"artifact_path": "out/runtime.tar"}}}}
    record = {"attempt_id": "a1", "context": {"ree_id": REE}, "command": {"operation": "initialize_ree"}}
    commit_document(root, "initialize_ree", document, record | {"operation_status": "succeeded"})
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    recorded = {change.path: (change.storage, change.named_by) for change in evidence.files}
    assert recorded["snapshot.tar.gz"] == ("lfs", ())
    assert recorded["artifacts/runtime.tar"] == ("git", (ARTIFACT_PATH,))
    assert recorded["ree.json"] == ("git", ())


SIGNATURE = "signatures/author_approval.sigstore.json"


def signed(*files: FileChange, events: tuple[Event, ...] = ()) -> Evidence:
    evidence = authored()
    return evidence.model_copy(update={"events": (*evidence.events, *events), "files": files})


def signature_findings(*files: FileChange, events: tuple[Event, ...] = ()) -> list[str]:
    result = check_aggregate(ree(), signed(*files, events=events))
    assert result.signatures == sum(1 for file in files if file.path.startswith("signatures/"))
    return [f"{finding.subject}: {finding.reason}" for finding in result.findings]


def test_a_signature_is_added_to_a_sealed_ree_by_signing_it() -> None:
    signing = lifecycle(7900, "sealed", "sealed", "sign_ree", "operation")
    assert signature_findings(file(7900, SIGNATURE, None, "s", "sign_ree", "operation"), events=(signing,)) == []


def test_a_sealed_bundle_that_is_loaded_brings_its_signatures() -> None:
    loading = lifecycle(7900, "draft", "sealed", "load_ree_bundle", "operation")
    assert signature_findings(file(7900, SIGNATURE, None, "s", "load_ree_bundle", "operation"), events=(loading,)) == []


def test_a_draft_is_never_signed() -> None:
    editing = lifecycle(5900, "draft", "draft", "sign_ree", "operation")
    assert signature_findings(file(5900, SIGNATURE, None, "s", "sign_ree", "operation"), events=(editing,)) == [
        f"Ree {REE} {SIGNATURE}: added by sign_ree to a document that is not sealed"
    ]


def test_only_signing_adds_a_signature_and_none_is_changed_or_removed_after() -> None:
    sealed = lifecycle(7900, "sealed", "sealed", "write_script", "operation")
    assert signature_findings(file(7900, SIGNATURE, None, "s", "write_script", "operation"), events=(sealed,)) == [
        f"Ree {REE} {SIGNATURE}: changed by write_script, but only sign_ree signs"
    ]
    assert signature_findings(file(7900, SIGNATURE, None, "s", "external", "external")) == [
        f"Ree {REE} {SIGNATURE}: changed by {EXTERNAL}, but only sign_ree signs"
    ]
    assert signature_findings(file(8900, SIGNATURE, "s", "t", "sign_ree", "operation")) == [
        f"Ree {REE} {SIGNATURE}: changed by sign_ree, but a signature, once added, stays as it is"
    ]
    assert signature_findings(file(8900, SIGNATURE, "s", None, "sign_ree", "operation")) == [
        f"Ree {REE} {SIGNATURE}: removed by sign_ree, but a signature, once added, stays as it is"
    ]


def test_signing_changes_nothing_beside_the_signature() -> None:
    signing = lifecycle(7900, "sealed", "sealed", "sign_ree", "operation")
    assert signature_findings(
        file(7900, SIGNATURE, None, "s", "sign_ree", "operation"),
        file(7900, "REPRODUCING.md", "a", "b", "sign_ree", "operation"),
        events=(signing,),
    ) == [f"Ree {REE} REPRODUCING.md: changed by sign_ree, which only adds signatures"]


def test_a_sealed_ree_changes_only_by_signing_it() -> None:
    def broken(operation: str) -> list[str]:
        moved = lifecycle(7900, "sealed", "sealed", operation, "operation")
        result = check(load_spec(), signed(events=(moved,)))
        rule = next(rule for rule in result.rules if rule.rule == "sealed-rees-are-only-signed")
        assert rule.triggered == 1
        return [finding.reason for finding in rule.findings]

    assert broken("sign_ree") == []
    assert len(broken("write_script")) == 1
