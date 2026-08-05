from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.primitives import ReePath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_core.domain.ree.audit import audit
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    BundleContents,
    BundleEntry,
    ExperimentDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
    SourceDefinition,
)
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt, BuildRuntimeReceipt, WorkspaceDrift
from repo2ree_core.domain.ree.transitions import (
    clear_source,
    commit_receipt,
    record_seal,
    subject_digest,
    validate_seal,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import experiment_run_script_path

_DIGEST = digest_bytes(b"content")
_OTHER_DIGEST = digest_bytes(b"other")
_NOW = parse_utc_instant("2026-08-03T00:00:00Z")


def test_ree_round_trips_as_the_same_local_and_bundle_model() -> None:
    ree = Ree(subject=ReeSubject(definition=ReeDefinition(name="demo")))

    assert Ree.model_validate_json(ree.model_dump_json()) == ree


def test_bundle_inventory_requires_sorted_unique_paths() -> None:
    with pytest.raises(ValidationError, match="sorted"):
        BundleContents(
            entries=(
                BundleEntry(path=ReePath("z"), digest=_DIGEST, size=1),
                BundleEntry(path=ReePath("a"), digest=_DIGEST, size=1),
            )
        )


def test_the_ree_document_round_trips_through_disk_under_one_name(tmp_path: Path) -> None:
    """One document, one spelling — the same file a bundle carries."""
    store = ReeDirectory(ReeLayout(tmp_path / "ree"))
    store.ensure_dirs()
    draft = Ree(
        subject=ReeSubject(
            definition=ReeDefinition(name="demo"),
            # A restored draft keeps the inventory it arrived with; nothing
            # reads it as a claim until a seal binds it.
            contents=BundleContents(
                entries=(BundleEntry(path=ReePath("ree/overlay/build.sh"), digest=_DIGEST, size=1),)
            ),
        )
    )

    store.write_ree(draft)

    assert store.layout.manifest.name == "ree.json"
    assert store.read_ree() == draft
    assert audit(draft).source.payload == "not_applicable"


def test_experiment_slug_collisions_are_rejected() -> None:
    def experiment(name: str) -> ExperimentDefinition:
        return ExperimentDefinition(
            name=name,
            run_script_path=ReePath(experiment_run_script_path(name)),
            run_script_digest=_DIGEST,
            run_script_size=1,
        )

    with pytest.raises(ValidationError, match="slugs"):
        ReeDefinition(experiments=(experiment("one two"), experiment("one  two")))


def test_committed_receipt_is_audited_and_contributes_to_subject_identity() -> None:
    ree = Ree(subject=ReeSubject(definition=ReeDefinition()))
    before = subject_digest(ree.subject)
    receipt = BuildRuntimeReceipt(
        run_id=RunId("run-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        snapshot_digest=_DIGEST,
        build_runtime_script_path=ReePath("ree-scripts/build_script.sh"),
        build_runtime_script_digest=_DIGEST,
        workspace_drift=WorkspaceDrift(status="clean"),
        runtime_path=WorkspacePath("runtime.tar"),
        produced_runtime_digest=_OTHER_DIGEST,
    )

    updated = commit_receipt(ree, receipt)

    assert updated.subject.receipts.build == receipt
    assert subject_digest(updated.subject) != before
    # The build definition is intentionally absent, so this receipt attests a
    # recipe the REE does not declare. Present and unbacked is stale, not
    # not_applicable — the latter would keep it out of the seal gate's reach.
    assert audit(updated).runtime.evidence == "stale"


def test_seal_binds_and_freezes_the_subject() -> None:
    ree = record_seal(Ree(), sealed_at=_NOW)
    validate_seal(ree)

    changed = ree.model_copy(
        update={"subject": ree.subject.model_copy(update={"definition": ReeDefinition(name="changed")})}
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_seal(changed)


def test_clear_source_preserves_recipe_definition_but_clears_source_chain() -> None:
    source = SourceDefinition(origin_url="https://example.test/repo.git", source_type="git")
    source_receipt = AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url=source.origin_url,
        source_type=source.source_type,
        snapshot_digest=_DIGEST,
    )
    ree = Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                source=source,
                build_runtime=BuildRuntimeDefinition(
                    build_runtime_script_digest=_DIGEST,
                    build_runtime_script_size=1,
                ),
            ),
            contents=BundleContents(
                entries=(
                    BundleEntry(path=ReePath("ree/overlay/build.sh"), digest=_DIGEST, size=1),
                    BundleEntry(path=ReePath("ree/snapshot.tar.gz"), digest=_OTHER_DIGEST, size=2),
                )
            ),
        )
    )
    ree = commit_receipt(ree, source_receipt)

    cleared = clear_source(ree)

    assert cleared.subject.definition.source is None
    assert cleared.subject.definition.build_runtime == ree.subject.definition.build_runtime
    assert cleared.subject.receipts.source is None
    assert cleared.subject.contents.entries == ()


def test_bundle_payload_is_not_audited_until_the_ree_is_sealed() -> None:
    source = SourceDefinition(origin_url="https://example.test/repo.git", source_type="git")
    receipt = AcquireSourceReceipt(
        run_id=RunId("source-1"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        origin_url=source.origin_url,
        source_type=source.source_type,
        snapshot_digest=_DIGEST,
    )
    draft = commit_receipt(
        Ree(subject=ReeSubject(definition=ReeDefinition(source=source))),
        receipt,
    )

    assert audit(draft).source.evidence == "current"
    assert audit(draft).source.payload == "not_applicable"

    inventoried = draft.model_copy(
        update={
            "subject": draft.subject.model_copy(
                update={
                    "contents": BundleContents(
                        entries=(BundleEntry(path=ReePath("ree/snapshot.tar.gz"), digest=_DIGEST, size=1),)
                    )
                }
            )
        }
    )
    sealed = record_seal(inventoried, sealed_at=_NOW)

    assert audit(sealed).source.payload == "present"
