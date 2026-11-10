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
        "write_file",
        "load_ree_bundle",
    }
    assert allowed("field", "definition.catalog.contributors", CREATED, "unset") == {"initialize_ree"}
    # An item of a keyed field starts when it is declared or restored, not with the REE.
    assert allowed("field", "definition.experiments[*]", CREATED, "set") == {"patch_ree_definition", "load_ree_bundle"}


def test_a_receipt_goes_stale_when_anything_it_was_made_from_moves() -> None:
    # The build experiment environment script is a file: writing it changes the declaration the experiment environment
    # rests on.
    assert {"write_file", "acquire_source"} <= allowed("receipt", "experiment_environment", "current", "stale")
    # A new experiment environment makes everything run on the old one stale, but never the experiment environment
    # itself.
    assert "build_experiment_environment" in allowed("receipt", "test_activation", "current", "stale")
    assert "build_experiment_environment" not in allowed("receipt", "experiment_environment", "current", "stale")
    assert allowed("receipt", "experiment_environment", "missing", "current") == {
        "build_experiment_environment",
        "load_ree_bundle",
    }


def test_what_runs_in_the_workbench_environment_rests_on_it() -> None:
    # The author's scripts run in the declared workbench environment: changing it changes what their receipts prove.
    for name in ("experiment_environment", "test_activation", "experiment"):
        assert "definition.workbench_environment" in ree().receipts[name].rests_on
    assert "patch_ree_definition" in allowed("receipt", "experiment_environment", "current", "stale")
    assert allowed("field", "definition.workbench_environment", CREATED, "unset") == {"initialize_ree"}


def test_whatever_makes_a_receipt_stale_may_make_it_current_again() -> None:
    # Standing is the receipt against the document as it now stands: undoing an edit undoes its staleness.
    assert {"patch_ree_definition", "write_file", "build_experiment_environment"} <= allowed(
        "receipt", "test_activation", "stale", "current"
    )
    assert allowed("receipt", "experiment_environment", "current", "stale") <= allowed(
        "receipt", "experiment_environment", "stale", "current"
    )
    # Declaring an orphaned receipt's subject again makes it speak for the REE again.
    assert "patch_ree_definition" in allowed("receipt", "experiment_environment", "stale", "current")


def test_undeclaring_a_keyed_item_discards_its_receipt() -> None:
    for source in ("current", "stale", "missing"):
        assert "patch_ree_definition" in allowed("receipt", "experiment", source, "not_applicable")
    # An unkeyed receipt is orphaned instead, and only removing the source clears it.
    assert allowed("receipt", "experiment_environment", "current", "not_applicable") == {
        "remove_source",
        "load_ree_bundle",
    }


def test_an_observation_applies_without_a_declaration_and_nothing_makes_it_stale() -> None:
    assert allowed("receipt", "hardware", "not_applicable", "current") == {"generate_hbom", "load_ree_bundle"}
    assert allowed("receipt", "hardware", "current", "stale") == {"load_ree_bundle"}


def test_a_receipt_starts_applicable_only_when_what_it_is_about_is_declared_from_the_start() -> None:
    assert allowed("receipt", "test_activation", CREATED, "missing") == {"initialize_ree"}
    assert allowed("receipt", "experiment_environment", CREATED, "not_applicable") == {"initialize_ree"}
    assert allowed("receipt", "experiment", CREATED, "missing") == {"patch_ree_definition"}


def test_whole_document_operations_are_marked_bulk_for_views() -> None:
    assert set(machine("receipt", "experiment_environment").bulk) == {"load_ree_bundle", "remove_source"}
    assert machine("field", "definition.name").bulk == ("load_ree_bundle",)


def mutated(change: Any) -> dict[str, Any]:
    aggregate: dict[str, Any] = documents().aggregates[0]
    change(aggregate)
    return aggregate


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda a: a["receipts"]["experiment_environment"].update(rests_on=["definition.nothing"]),
            "names undeclared fields",
        ),
        (lambda a: a["receipts"]["experiment_environment"].update(about=["definition.experiments[*]"]), "is not keyed"),
        (lambda a: a["receipts"]["sbom"].update(made_from=["experiment"]), "other, unkeyed receipts"),
        (lambda a: a["fields"]["definition.experiments[*]"].update(initial="unset"), "needs an initial state"),
        (lambda a: a.update(writes_nothing=["write_file"]), "write nothing take edges"),
        (lambda a: a.pop("overlay"), "names no overlay"),
        (
            lambda a: a["fields"]["definition.experiment_environment"].update(files=["ree-scripts/{slug}.sh"]),
            "name its item once",
        ),
        (lambda a: a["fields"]["definition.experiments[*]"].update(files=["ree-scripts/x.sh"]), "name its item once"),
        (
            lambda a: a["fields"]["definition.test_activation"].update(
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
    del docs.aggregates[0]["receipts"]["sbom_cross_check"]
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


def commit_document(root: Path, operation: str, document: dict[str, Any], record: dict[str, Any] | None) -> None:
    assert GIT is not None
    environment = {**os.environ, **GIT_ENVIRONMENT}
    (root / "ree.json").write_text(json.dumps(document))
    metadata = {"kind": "operation.completed", "schema_version": 2, "record": record} if record else {"kind": "x"}
    subprocess.run([GIT, "-C", str(root), "add", "ree.json"], check=True, env=environment)
    subprocess.run(
        [GIT, "-C", str(root), "commit", "-q", "-m", f"{operation}\n\n{json.dumps(metadata)}"],
        check=True,
        env=environment,
    )


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
    record = {"attempt_id": "a1", "context": {"ree_id": REE}, "command": {"operation": "write_file"}}
    (root / "ree.json").write_text("not json")
    environment = {**os.environ, **GIT_ENVIRONMENT}
    subprocess.run(
        [GIT, "-C", str(root), "commit", "-qam", "write_file\n\n" + json.dumps({"kind": "x"})],
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
            receipt(2100, "experiment_environment", None, "not_applicable", None, "baseline"),
            receipt(2300, "experiment_environment", "not_applicable", "missing", "patch_ree_definition", "operation"),
            receipt(3300, "experiment_environment", "missing", "current", "build_experiment_environment", "operation"),
            receipt(4300, "experiment:one", None, "missing", "patch_ree_definition", "operation"),
            receipt(5300, "experiment:one", "missing", "current", "run_experiment", "operation"),
            lifecycle(6900, "draft", "sealed", "seal_ree", "operation"),
        ),
        changes=(
            *(
                change(1900, path, None, "x", "initialize_ree", "created")
                for path in (
                    "capture",
                    "definition.name",
                    "definition.experiment_environment",
                    "definition.test_activation",
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
    assert moves[("definition.catalog.version", CREATED, "unset", "initialize_ree")] == 1
    assert moves[("definition.experiment_environment.artifact_path", "unset", "set", "patch_ree_definition")] == 1
    # A keyed item starts when it is declared; the parts inside it are not fields of their own.
    assert moves[("definition.experiments[*]", CREATED, "set", "patch_ree_definition")] == 1
    # A receipt's first audited standing is the one the REE was created with.
    assert moves[("experiment_environment", CREATED, "not_applicable", "initialize_ree")] == 1
    assert moves[("experiment", "missing", "current", "run_experiment")] == 1
    assert not check_aggregate(ree(), authored()).findings


def test_a_move_no_edge_allows_is_reported_with_its_evidence() -> None:
    evidence = authored()
    late = change(7900, "definition.catalog.version", None, "2", "run_experiment", "operation")
    drift = receipt(7100, "experiment_environment", "current", "stale", None, "external")
    result = check_aggregate(
        ree(), evidence.model_copy(update={"changes": (*evidence.changes, late), "events": (*evidence.events, drift)})
    )
    reasons = sorted((finding.subject, finding.reason, finding.evidence) for finding in result.findings)
    assert reasons == [
        (
            f"Ree {REE} definition.catalog.version",
            "unset -> set by run_experiment, which no edge allows",
            ("git:ree@c7",),
        ),
        (f"Ree {REE} experiment_environment", f"current -> stale by {EXTERNAL}, which no edge allows", ("git:ree@c7",)),
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
    assert ("patch_ree_definition", ("experiment[one]", "definition.experiments[one]")) in steps
    assert steps[-1] == ("seal_ree", ("lifecycle", "contents"))
    final = replayed.steps[-1].states
    assert (final["lifecycle"], final["experiment_environment"], final["experiment[one]"]) == (
        "sealed",
        "current",
        "current",
    )
    names = [part.name for part in replayed.parts]
    # Drawing order: the lifecycle, each receipt after what it is about, the other groups last.
    assert names[0] == "lifecycle"
    assert names.index("definition.experiment_environment.artifact_path") < names.index("experiment_environment")
    assert names.index("experiment[one]") < names.index("definition.name")
    item = next(part for part in replayed.parts if part.name == "experiment[one]")
    assert (item.machine, item.item, item.group) == ("experiment", "one", "experiment")


# ---------------------------------------------------------------------------- the overlay


@pytest.mark.parametrize(
    ("path", "claim"),
    [
        ("ree-scripts/build_experiment_environment.sh", ("definition.experiment_environment", "")),
        ("ree-scripts/activation.verify.sh", ("definition.test_activation", "")),
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
    slugs = json.loads((Path(__file__).resolve().parents[3] / "contracts/experiment-slugs.json").read_text())
    for case in slugs["cases"]:
        assert experiment_slug(case["name"]) == case["slug"]


def file(position: int, path: str, before: str | None, after: str | None, operation: str, cause: Cause) -> FileChange:
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
            file(5900, run, None, "r1", "write_file", "operation"),
            changes=(
                change(5900, "definition.experiments[one].run_script_digest", "d", "d2", "write_file", "operation"),
            ),
        )
        == []
    )
    assert overlay_findings(file(5900, build, "b1", "b2", "write_file", "operation")) == [
        f"Ree {REE} {build}: changed by write_file, but definition.experiment_environment, which claims it, did not"
    ]


def test_scripts_of_what_is_not_declared_need_no_field_to_change() -> None:
    assert (
        overlay_findings(
            file(5900, "overlay/ree-scripts/experiments/not-yet.sh", None, "r", "write_file", "operation"),
            file(5900, "overlay/ree-scripts/experiments/not-yet.verify.sh", None, "v", "write_file", "operation"),
        )
        == []
    )


def test_a_file_no_field_claims_violates_the_aggregate_rule() -> None:
    extra = "overlay/instant/requirements-extra.txt"
    assert overlay_findings(file(5900, extra, None, "m", "write_file", "operation")) == [
        f"Ree {REE} {extra}: is in the overlay, but no field claims it"
    ]
    # Taking it away again is what the rule asks for.
    assert overlay_findings(file(5900, extra, "m", None, "delete_file", "operation")) == []


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_each_capture_commit_reports_the_overlay_files_it_changed(tmp_path: Path) -> None:
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
    record = {"attempt_id": "a1", "context": {"ree_id": REE}, "command": {"operation": "write_file"}}
    commit_document(
        root, "write_file", {"subject": {"definition": {"name": "demo"}}}, record | {"operation_status": "succeeded"}
    )
    evidence = load_evidence(repositories=[root], git_executable=GIT)
    moved = [(c.cause, c.operation, c.path, c.before is None, c.after is None) for c in evidence.files]
    assert moved == [
        ("created", "initialize_ree", "overlay/ree-scripts/build_experiment_environment.sh", True, False),
        ("operation", "write_file", "overlay/notes.txt", True, False),
        ("operation", "write_file", "overlay/ree-scripts/build_experiment_environment.sh", False, False),
    ]
