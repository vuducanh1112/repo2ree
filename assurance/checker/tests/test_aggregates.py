"""The Ree aggregate: every part of the committed document as a machine, reported beside the verdict."""

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
from repo2ree_assurance_checker.check.aggregates import EXTERNAL, check_aggregate, histories
from repo2ree_assurance_checker.evidence import Event, Evidence, FieldChange, Source
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
    assert allowed("field", "definition.build_runtime", "set", "set") == {
        "patch_ree_definition",
        "write_file",
        "delete_file",
        "load_ree_bundle",
    }
    assert allowed("field", "definition.catalog.contributors", CREATED, "unset") == {"initialize_ree"}
    # An item of a keyed field starts when it is declared or restored, not with the REE.
    assert allowed("field", "definition.experiments[*]", CREATED, "set") == {"patch_ree_definition", "load_ree_bundle"}


def test_a_receipt_goes_stale_when_anything_it_was_made_from_moves() -> None:
    # The build script is a file: writing it changes the declaration the runtime rests on.
    assert {"write_file", "acquire_source"} <= allowed("receipt", "runtime", "current", "stale")
    # A new runtime makes everything run on the old one stale, but never the runtime itself.
    assert "build_runtime" in allowed("receipt", "test_activation", "current", "stale")
    assert "build_runtime" not in allowed("receipt", "runtime", "current", "stale")
    assert allowed("receipt", "runtime", "missing", "current") == {"build_runtime", "load_ree_bundle"}


def test_an_observation_applies_without_a_declaration_and_nothing_makes_it_stale() -> None:
    assert allowed("receipt", "hardware", "not_applicable", "current") == {"generate_hbom", "load_ree_bundle"}
    assert allowed("receipt", "hardware", "current", "stale") == {"load_ree_bundle"}


def test_a_receipt_starts_applicable_only_when_what_it_is_about_is_declared_from_the_start() -> None:
    assert allowed("receipt", "test_activation", CREATED, "missing") == {"initialize_ree"}
    assert allowed("receipt", "runtime", CREATED, "not_applicable") == {"initialize_ree"}
    assert allowed("receipt", "experiment", CREATED, "missing") == {"patch_ree_definition"}


def test_whole_document_operations_are_marked_bulk_for_views() -> None:
    assert set(machine("receipt", "runtime").bulk) == {"load_ree_bundle", "remove_source"}
    assert machine("field", "definition.name").bulk == ("load_ree_bundle",)


def mutated(change: Any) -> dict[str, Any]:
    aggregate: dict[str, Any] = documents().aggregates[0]
    change(aggregate)
    return aggregate


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda a: a["receipts"]["runtime"].update(rests_on=["definition.nothing"]), "names undeclared fields"),
        (lambda a: a["receipts"]["runtime"].update(about=["definition.experiments[*]"]), "is not keyed"),
        (lambda a: a["receipts"]["sbom"].update(made_from=["experiment"]), "other, unkeyed receipts"),
        (lambda a: a["fields"]["definition.experiments[*]"].update(initial="unset"), "needs an initial state"),
        (lambda a: a.update(writes_nothing=["write_file"]), "write nothing take edges"),
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
    before = document_parts({"definition": {"build_runtime": {"runtime_path": None, "script": "a"}}})
    after = document_parts({"definition": {"build_runtime": {"runtime_path": "venv", "script": "a"}}})
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    assert changed == {"definition", "definition.build_runtime", "definition.build_runtime.runtime_path"}


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
    """Created, a runtime declared and built, an experiment declared and run, then sealed."""
    return Evidence(
        sources=(git_source(),),
        events=(
            lifecycle(1900, None, "draft", "initialize_ree", "created"),
            receipt(2100, "runtime", None, "not_applicable", None, "baseline"),
            receipt(2300, "runtime", "not_applicable", "missing", "patch_ree_definition", "operation"),
            receipt(3300, "runtime", "missing", "current", "build_runtime", "operation"),
            receipt(4300, "experiment:one", None, "missing", "patch_ree_definition", "operation"),
            receipt(5300, "experiment:one", "missing", "current", "run_experiment", "operation"),
            lifecycle(6900, "draft", "sealed", "seal_ree", "operation"),
        ),
        changes=(
            *(
                change(1900, path, None, "x", "initialize_ree", "created")
                for path in ("capture", "definition.name", "definition.build_runtime", "definition.test_activation")
            ),
            change(2900, "definition.build_runtime.runtime_path", None, "p", "patch_ree_definition", "operation"),
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
    assert moves[("definition.build_runtime.runtime_path", "unset", "set", "patch_ree_definition")] == 1
    # A keyed item starts when it is declared; the parts inside it are not fields of their own.
    assert moves[("definition.experiments[*]", CREATED, "set", "patch_ree_definition")] == 1
    # A receipt's first audited standing is the one the REE was created with.
    assert moves[("runtime", CREATED, "not_applicable", "initialize_ree")] == 1
    assert moves[("experiment", "missing", "current", "run_experiment")] == 1
    assert not check_aggregate(ree(), authored()).findings


def test_a_move_no_edge_allows_is_reported_with_its_evidence() -> None:
    evidence = authored()
    late = change(7900, "definition.catalog.version", None, "2", "run_experiment", "operation")
    drift = receipt(7100, "runtime", "current", "stale", None, "external")
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
        (f"Ree {REE} runtime", f"current -> stale by {EXTERNAL}, which no edge allows", ("git:ree@c7",)),
    ]


def test_aggregate_findings_never_change_the_verdict() -> None:
    evidence = authored()
    late = change(7900, "definition.catalog.version", None, "2", "run_experiment", "operation")
    disallowed = evidence.model_copy(update={"changes": (*evidence.changes, late)})
    spec = load_spec()
    before, after = check(spec, evidence), check(spec, disallowed)
    assert after.aggregates[0].findings
    assert (after.verdict, after.rules) == (before.verdict, before.rules)


def test_each_instance_is_replayed_step_by_step_with_what_each_operation_moved() -> None:
    (replayed,) = histories(load_spec(), authored())
    steps = [(step.operation, step.moved) for step in replayed.steps]
    # The standings first audited belong to the step that created the REE, which moves nothing yet.
    assert steps[0] == ("initialize_ree", ())
    assert ("patch_ree_definition", ("experiment[one]", "definition.experiments[one]")) in steps
    assert steps[-1] == ("seal_ree", ("lifecycle", "contents"))
    final = replayed.steps[-1].states
    assert (final["lifecycle"], final["runtime"], final["experiment[one]"]) == ("sealed", "current", "current")
    names = [part.name for part in replayed.parts]
    # Drawing order: the lifecycle, each receipt after what it is about, the other groups last.
    assert names[0] == "lifecycle"
    assert names.index("definition.build_runtime.runtime_path") < names.index("runtime")
    assert names.index("experiment[one]") < names.index("definition.name")
    item = next(part for part in replayed.parts if part.name == "experiment[one]")
    assert (item.machine, item.item, item.group) == ("experiment", "one", "experiment")
