"""The REE anatomy is the contract drawn: every part, the files it is about, and where declarations meet receipts."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_repoview.diagrams.ree import LAYOUT, SCHEMA, Anatomy, Layout, Link, Pair, Schema, anatomy, render_dot
from repo2ree_repoview.overview import figures
from repo2ree_repoview.overview.bundle import Bundle
from repo2ree_repoview.overview.exports import SPEC_EXPORT, Spec, exported
from repo2ree_repoview.overview.pages.aggregate import page_aggregate
from repo2ree_repoview.overview.receipt import AggregateMoves, Evidence
from repo2ree_repoview.stamp import Stamp, stamp_svg


def contract() -> Schema:
    return Schema.model_validate_json(SCHEMA.read_text(encoding="utf-8"))


def drawn() -> Anatomy:
    return anatomy(contract(), Layout.model_validate_json(LAYOUT.read_text(encoding="utf-8")))


def test_every_section_of_the_definition_and_every_receipt_is_a_box() -> None:
    schema = contract()
    subject = schema.of(schema.properties["subject"])
    boxes = {(box.role, box.name) for box in drawn().boxes}
    for name, prop in schema.of(subject.properties["definition"]).properties.items():
        assert ("definition", name if prop.target() else "definition") in boxes
    receipts = schema.of(subject.properties["receipts"]).properties
    assert {name for role, name in boxes if role == "receipt"} == set(receipts)
    assert {name for role, name in boxes if role == "bundle"} == {"contents", "capture", "seal"}


def test_the_fields_every_receipt_carries_are_named_once_not_in_each_box() -> None:
    result = drawn()
    assert {"run_id", "started_at", "operation"} <= set(result.shared)
    for box in result.boxes:
        if box.role == "receipt":
            assert not set(box.fields) & set(result.shared)
            assert box.note.startswith("by ")


def test_a_declaration_and_the_receipts_that_ran_it_meet_at_the_file_they_are_digests_of() -> None:
    links = set(drawn().links)
    script = "overlay/ree-scripts/experiments/{experiment_slug}.sh"
    assert Link("definition:experiments", "run_script_digest", "definition", script) in links
    assert Link("receipt:experiments", "run_script_digest", "receipt", script) in links
    assert {link.node for link in links if link.entry == "snapshot.tar.gz"} == {
        "receipt:source",
        "receipt:evaluation",
        "receipt:experiment_environment",
        "receipt:activation",
        "receipt:experiments",
    }
    # The seal is the digest of the document's subject; a bundle entry, of the file its path names.
    assert Link("bundle:seal", "ree_digest", "bundle", "ree.json") in links
    assert Link("bundle:contents", "entries[*].digest", "bundle", ".") in links
    # Meeting in the tree, they need no pairing of their own.
    assert not [pair for pair in drawn().pairs if pair.field and pair.field.endswith(("_digest", "_path"))]


def test_every_digest_field_drawn_points_into_the_tree_unless_it_is_of_something_outside() -> None:
    result = drawn()
    linked = {(link.node, link.field) for link in result.links}
    for box in result.boxes:
        for name, prop in box.fields.items():
            of = prop.annotated().digest_of
            if of is not None and of.covers != "outside":
                assert (box.node, name) in linked, f"{box.node}.{name}"


def test_a_declared_field_no_file_joins_is_paired_with_the_receipt_field_that_records_it() -> None:
    pairs = set(drawn().pairs)
    assert Pair("experiments", "name", "experiments", "experiment_name", "field") in pairs
    assert Pair("source", "origin_url", "source", "origin_url", "field") in pairs
    for receipt in ("experiment_environment", "activation", "experiments"):
        assert Pair("workbench_environment", None, receipt, "workbench_environment", "section") in pairs
    # The hardware observation repeats no field by name, but holds the declaration's very fields.
    assert Pair("hardware", None, "hardware_observation", "observation", "same fields") in pairs
    # A field every receipt carries joins nothing.
    assert not [pair for pair in pairs if pair.receipt_field in drawn().shared]


def test_every_pair_ends_on_a_field_its_receipt_shows() -> None:
    result = drawn()
    receipts = {box.name: box for box in result.boxes if box.role == "receipt"}
    for pair in result.pairs:
        assert pair.receipt_field in receipts[pair.receipt].fields
    assert render_dot(result).count(" -> ") == len(result.pairs) + len(result.links)


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    return Bundle(tmp_path / "overview", "a" * 40)


def test_the_ree_page_shows_the_anatomy_with_its_commit_and_recipe(
    tmp_path: Path, bundle: Bundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(figures, "DIAGRAMS", tmp_path / "diagrams")
    ree = Spec.model_validate_json(exported(SPEC_EXPORT)).aggregates["Ree"]
    page = page_aggregate(ree, AggregateMoves.over(Evidence(), "Ree"), bundle).body
    assert "<h3>Anatomy</h3>" in page
    assert "Missing: run <code>just generate-ree-anatomy</code>" in page

    drawing = tmp_path / "diagrams/ree/anatomy.svg"
    drawing.parent.mkdir(parents=True)
    drawing.write_text('<svg width="20pt" height="10pt" viewBox="0 0 20 10"><g id="a"/></svg>\n', encoding="utf-8")
    stamp = Stamp(
        revision="a" * 40,
        tree="b" * 40,
        dirty=False,
        working_tree_sha256=None,
        generated="2026-11-12T09:00:00+00:00",
        by="generate-ree-anatomy",
    )
    stamp_svg(drawing, stamp)
    page = page_aggregate(ree, AggregateMoves.over(Evidence(), "Ree"), bundle).body
    assert "Generated from <code>aaaaaaaaaa</code>" in page
    assert "Drawn by <code>just generate-ree-anatomy</code>" in page
    assert '<g id="a"/>' in page
    assert "a digest of that file" in page
    assert "Open full size" not in page.split("<h3>Evidence graph</h3>")[0]
    assert (bundle.root / "diagrams/ree/anatomy.svg").is_file()
    assert page.index("<h3>Anatomy</h3>") < page.index("<h3>Evidence graph</h3>")
