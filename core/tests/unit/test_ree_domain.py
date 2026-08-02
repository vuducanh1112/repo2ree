import pytest
from pydantic import ValidationError

from repo2ree_core.digests import Digest, digest_bytes
from repo2ree_core.domain.primitives import (
    GitRevision,
    ReeId,
    ReePath,
    RunId,
    ScriptPath,
    Swhid,
    WorkspacePath,
)
from repo2ree_core.domain.ree.assessment import assess
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.model import (
    AuthoredFile,
    Ree,
    ReeDefinition,
    ReeEvidence,
    ReeIdentity,
    ReePublications,
    SealedRee,
)
from repo2ree_core.domain.ree.queries import name_of, runtime_of, scripts_of
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt, BuildRuntimeReceipt, WorkspaceDrift
from repo2ree_core.domain.ree.state import ReeLifecycleState, record_evaluation, record_source, select_packaging
from repo2ree_core.domain.ree.transitions import (
    AcquiredSource,
    ReePreconditionError,
    SourceAcquired,
    SourceRequest,
    SourceSlot,
    apply_source_acquired,
    plan_source_acquisition,
    revision_of,
)
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import parse_utc_instant

# ================================================
# Helpers
# ================================================


def _intent_with_experiments(*names: str) -> ReeIntent:
    return ReeIntent.model_validate(
        {
            "name": "demo",
            "experiments": [{"name": n, "run_script": "ree/exp.sh"} for n in names],
        }
    )


# ================================================
# Experiment name uniqueness
# ================================================


def test_unique_experiment_names_accepts_distinct_names():
    intent = _intent_with_experiments("smoke", "integration", "benchmark")
    assert [e.name for e in intent.experiments] == ["smoke", "integration", "benchmark"]


def test_unique_experiment_names_rejects_duplicates():
    with pytest.raises(ValidationError, match="experiment names must be unique"):
        _intent_with_experiments("smoke", "integration", "smoke")


def test_unique_experiment_names_allows_multiple_empty_names():
    intent = _intent_with_experiments("", "", "smoke")
    assert len(intent.experiments) == 3


def test_unique_experiment_names_allows_empty_list():
    intent = ReeIntent(name="demo")
    assert intent.experiments == []


def test_experiment_estimates_default_to_empty_strings():
    intent = ReeIntent.model_validate(
        {
            "name": "demo",
            "experiments": [{"name": "smoke", "run_script": "ree/exp.sh"}],
        }
    )

    experiment = intent.experiments[0]
    assert experiment.runtime_estimate == ""
    assert experiment.resource_estimates.model_dump() == {
        "cpu": "",
        "memory": "",
        "gpu": "",
        "storage": "",
        "network": "",
    }


def test_experiment_estimates_accept_runtime_and_resource_hints():
    intent = ReeIntent.model_validate(
        {
            "name": "demo",
            "experiments": [
                {
                    "name": "benchmark",
                    "run_script": "ree/bench.sh",
                    "runtime_estimate": "15-20 min",
                    "resource_estimates": {
                        "cpu": "8 vCPU",
                        "memory": "16 GB",
                        "gpu": "1x A10",
                        "storage": "5 GB scratch",
                        "network": "offline",
                    },
                }
            ],
        }
    )

    experiment = intent.experiments[0]
    assert experiment.runtime_estimate == "15-20 min"
    assert experiment.resource_estimates.model_dump() == {
        "cpu": "8 vCPU",
        "memory": "16 GB",
        "gpu": "1x A10",
        "storage": "5 GB scratch",
        "network": "offline",
    }


# ================================================
# ReeLifecycleState transitions
# ================================================


def test_record_source_settles_the_whole_snapshot_triple():
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    session = ReeLifecycleState()
    updated = record_source(
        session,
        acquired_by="download",
        snapshot_archive=ReePath("snapshot.tar.gz"),
        snapshot_captured_at=parse_utc_instant("2026-01-01T00:00:00Z"),
        snapshot_digest=Digest("sha256:" + "0" * 64),
        resolved_commit=GitRevision("abc123"),
    )
    assert updated.source_available is True
    assert updated.source_acquired_by == "download"
    assert updated.source_snapshot_archive == "snapshot.tar.gz"
    assert updated.source_snapshot_digest == "sha256:" + "0" * 64
    assert updated.source_resolved_commit == "abc123"


def test_record_source_requires_the_snapshot_it_was_acquired_into():
    """The digest is the chain root, so a source cannot be recorded without one."""
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    with pytest.raises(TypeError):
        record_source(  # type: ignore[call-arg]
            ReeLifecycleState(),
            acquired_by="download",
            resolved_commit=GitRevision("abc123"),
        )


def test_session_with_evaluation():
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    session = ReeLifecycleState()
    updated = record_evaluation(
        session,
        dependency_level=3,
        environment_level=2,
        machine_level=0,
        detected_dependencies="4 dependencies across 1 manifest file",
    )
    assert updated.dependency_level == 3
    assert updated.environment_level == 2
    assert updated.machine_level == 0
    assert updated.detected_dependencies == "4 dependencies across 1 manifest file"


def test_session_with_packaging():
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    session = ReeLifecycleState()
    updated = select_packaging(
        session,
        source_included=True,
        runtime_included=True,
        results_included=True,
    )
    assert updated.source_included is True
    assert updated.runtime_included is True
    assert updated.results_included is True
    assert session.source_included is False


def test_session_has_no_apply_patch():
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    assert not hasattr(ReeLifecycleState, "apply_patch")
    assert not hasattr(ReeLifecycleState, "with_downloadables")


# ================================================
# run-script defaults and validation
# ================================================


def test_default_activation_run_script_is_reserved():
    intent = ReeIntent(name="x")
    assert intent.activation.run_script == "ree-scripts/activation.sh"


def test_empty_activation_run_script_normalizes_to_reserved():
    # A client zeroing the activation (e.g. on source reset) must not strand
    # the intent without a run-script path.
    intent = ReeIntent.model_validate({"name": "x", "activation": {"run_script": ""}})
    assert intent.activation.run_script == "ree-scripts/activation.sh"


def test_naming_an_experiment_settles_its_reserved_run_script():
    intent = ReeIntent.model_validate({"name": "x", "experiments": [{"name": "smoke test"}]})
    experiment = intent.experiments[0]
    assert experiment.run_script == "ree-scripts/experiments/smoke-test.sh"
    # Verify stays an explicit authoring act: declared means "must exist and pass".
    assert experiment.verify_script == ""


def test_unnamed_experiment_keeps_empty_run_script():
    intent = ReeIntent.model_validate({"name": "x", "experiments": [{"name": ""}]})
    assert intent.experiments[0].run_script == ""


def test_experiment_run_script_round_trips():
    intent = ReeIntent.model_validate(
        {
            "name": "x",
            "experiments": [{"name": "smoke", "run_script": "ree-scripts/experiments/smoke.sh"}],
        }
    )
    assert intent.experiments[0].run_script == "ree-scripts/experiments/smoke.sh"


@pytest.mark.parametrize("path", ["/setup.sh", "../setup.sh", "scripts/../setup.sh"])
def test_run_script_rejects_unsafe_paths(path):
    with pytest.raises(ValidationError):
        ReeIntent.model_validate(
            {
                "name": "x",
                "experiments": [{"name": "smoke", "run_script": path}],
            }
        )


# ================================================
# Canonical REE aggregate
# ================================================


def _ree(*, intent: ReeIntent | None = None, files: tuple[AuthoredFile, ...] = (), selected=()) -> Ree:
    return Ree(
        identity=ReeIdentity(
            ree_id=ReeId("ree-1"),
            created_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            updated_at=parse_utc_instant("2026-01-01T00:00:00Z"),
        ),
        authored=ReeDefinition(intent=intent or ReeIntent(name="demo"), files=files),
        evidence=ReeEvidence(
            selected=selected,
            state=ReeLifecycleState(source_available=True, source_snapshot_digest=Digest("sha256:snapshot")),
        ),
    )


def _successful_build(*, script_digest: str) -> BuildRuntimeReceipt:
    return BuildRuntimeReceipt(
        run_id=RunId("build-1"),
        started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
        finished_at=parse_utc_instant("2026-01-01T00:00:01Z"),
        duration_ms=1000,
        recorded_at=parse_utc_instant("2026-01-01T00:00:01Z"),
        status="succeeded",
        workspace_drift=WorkspaceDrift(status="clean"),
        snapshot_digest=Digest("sha256:snapshot"),
        build_script_path=ScriptPath(RESERVED_BUILD_SCRIPT),
        build_script_digest=Digest(script_digest),
        runtime_path=WorkspacePath("runtime.tar"),
        produced_runtime_digest=Digest("sha256:runtime"),
    )


def test_ree_exposes_its_authored_anatomy_from_one_root():
    build = AuthoredFile(path=ReePath(RESERVED_BUILD_SCRIPT), digest=digest_bytes(b"build"), size=5)
    ree = _ree(intent=ReeIntent(name="demo", runtime="runtime.tar"), files=(build,))

    assert name_of(ree.authored) == "demo"
    assert runtime_of(ree.authored).artifact_path == "runtime.tar"
    assert scripts_of(ree.authored).build_runtime == build
    assert ree.evidence.state.source_available is True
    assert ree.publications.sealed is None


def test_ree_is_data_only():
    """The aggregate carries no behaviour: every transition is a free function."""
    assert not hasattr(Ree, "patch_intent")
    assert not hasattr(Ree, "write_file")
    assert not hasattr(Ree, "assessment")


def _with_file(ree: Ree, path: str, content: bytes) -> Ree:
    """``ree`` with one authored file added or replaced, as a save would leave it."""
    file = AuthoredFile(path=ReePath(path), digest=digest_bytes(content), size=len(content))
    remaining = tuple(item for item in ree.authored.files if item.path != file.path)
    return ree.model_copy(
        update={
            "authored": ree.authored.model_copy(
                update={"files": tuple(sorted((*remaining, file), key=lambda item: item.path))}
            )
        }
    )


def test_unrelated_file_edit_changes_revision_but_not_runtime_freshness():
    build = AuthoredFile(path=ReePath(RESERVED_BUILD_SCRIPT), digest=digest_bytes(b"build"), size=5)
    receipt = _successful_build(script_digest=build.digest)
    ree = _ree(intent=ReeIntent(name="demo", runtime="runtime.tar"), files=(build,), selected=(receipt,))

    updated = _with_file(ree, "notes.txt", b"new metadata-like content")

    assert revision_of(updated) != revision_of(ree)
    assert assess(updated).runtime.status == "ready"


def test_build_script_edit_makes_matching_runtime_evidence_stale():
    build = AuthoredFile(path=ReePath(RESERVED_BUILD_SCRIPT), digest=digest_bytes(b"build"), size=5)
    receipt = _successful_build(script_digest=build.digest)
    ree = _ree(intent=ReeIntent(name="demo", runtime="runtime.tar"), files=(build,), selected=(receipt,))

    updated = _with_file(ree, RESERVED_BUILD_SCRIPT, b"different build")

    assert assess(updated).runtime.status == "stale"
    assert assess(updated).runtime.reasons == ("runtime build script changed",)


# ================================================
# Source acquisition: plan and apply
# ================================================

_TOKEN = "tok"  # noqa: S105 — an upload-staging id, not a secret
_EMPTY_SLOT = SourceSlot(upstream_populated=False, snapshot_archive_present=False, staged_upload_present=False)
_SNAPSHOT = ReePath("snapshot.tar.gz")


def _sourceless_ree(*, sealed: SealedRee | None = None) -> Ree:
    return Ree(
        identity=ReeIdentity(
            ree_id=ReeId("ree-1"),
            created_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            updated_at=parse_utc_instant("2026-01-01T00:00:00Z"),
        ),
        authored=ReeDefinition(intent=ReeIntent(name="demo")),
        evidence=ReeEvidence(state=ReeLifecycleState()),
        publications=ReePublications(sealed=sealed),
    )


def _download_request() -> SourceRequest:
    return SourceRequest(mode="download", origin_url="https://x/y.git", source_type="git", requested_revision="v1.2.0")


def _plan(ree: Ree, slot: SourceSlot = _EMPTY_SLOT, request: SourceRequest | None = None):
    return plan_source_acquisition(ree, slot, request or _download_request(), snapshot_archive=_SNAPSHOT)


def test_plan_source_acquisition_names_the_effect_for_an_empty_slot():
    plan = _plan(_sourceless_ree())

    assert plan.mode == "download"
    assert plan.origin_url == "https://x/y.git"
    assert plan.requested_revision == "v1.2.0"
    assert plan.snapshot_archive == "snapshot.tar.gz"
    assert plan.before_revision == revision_of(_sourceless_ree())


def test_plan_source_acquisition_refuses_an_occupied_slot():
    ree = _sourceless_ree()
    occupied = ree.model_copy(
        update={
            "evidence": ree.evidence.model_copy(
                update={"state": ReeLifecycleState(source_available=True)},
            )
        }
    )

    with pytest.raises(ReePreconditionError, match="already has a source"):
        _plan(occupied)


def test_plan_source_acquisition_refuses_a_sealed_ree():
    sealed = SealedRee(seal_hash=Digest("sha256:seal"), sealed_at=parse_utc_instant("2026-01-02T00:00:00Z"))

    with pytest.raises(ReePreconditionError, match="sealed"):
        _plan(_sourceless_ree(sealed=sealed))


def test_plan_source_acquisition_refuses_content_the_state_never_recorded():
    """The slot check is what makes an interrupted acquisition detectable."""
    interrupted = SourceSlot(upstream_populated=True, snapshot_archive_present=False, staged_upload_present=False)

    with pytest.raises(ReePreconditionError, match="remove the source"):
        _plan(_sourceless_ree(), interrupted)


def test_plan_source_acquisition_rejects_a_download_without_an_origin():
    with pytest.raises(ValueError, match="origin url"):
        _plan(_sourceless_ree(), request=SourceRequest(mode="download", source_type="git"))


def test_plan_source_acquisition_requires_the_staged_upload_it_names():
    request = SourceRequest(mode="upload", upload_token=_TOKEN, archive_name=ReePath("src.tar.gz"))

    with pytest.raises(ReePreconditionError, match="staged upload"):
        _plan(_sourceless_ree(), _EMPTY_SLOT, request)


def test_plan_source_acquisition_drops_the_other_mode_s_fields():
    """An upload has no origin; a download has no token. The plan says so."""
    staged = SourceSlot(upstream_populated=False, snapshot_archive_present=False, staged_upload_present=True)
    request = SourceRequest(
        mode="upload",
        upload_token=_TOKEN,
        archive_name=ReePath("src.tar.gz"),
        origin_url="https://ignored/",
    )

    plan = _plan(_sourceless_ree(), staged, request)

    assert plan.origin_url == ""
    assert plan.source_type == ""
    assert plan.archive_name == "src.tar.gz"


def _acquire_receipt(run_id: str) -> AcquireSourceReceipt:
    return AcquireSourceReceipt(
        run_id=RunId(run_id),
        started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
        finished_at=parse_utc_instant("2026-01-01T00:00:01Z"),
        duration_ms=1000,
        recorded_at=parse_utc_instant("2026-01-01T00:00:01Z"),
        status="succeeded",
        origin_url="https://x/y.git",
        source_type="git",
    )


def _acquired(**overrides) -> AcquiredSource:
    return AcquiredSource(
        captured_at=parse_utc_instant("2026-01-01T00:00:02Z"),
        snapshot_digest=Digest("sha256:snap"),
        **overrides,
    )


def test_apply_source_acquired_returns_a_whole_ree():
    ree = _sourceless_ree()
    plan = _plan(ree)
    receipt = _acquire_receipt("run-1")

    updated = apply_source_acquired(
        ree,
        SourceAcquired(
            plan=plan,
            observed=_acquired(resolved_commit=GitRevision("abc123"), swhid=Swhid("swh:1:dir:deadbeef")),
            receipts=(receipt,),
        ),
    )

    # intent: the resolved commit and the content identity are settled onto it
    assert updated.authored.intent.origin_url == "https://x/y.git"
    assert updated.authored.intent.revision == "abc123"
    assert updated.authored.intent.swhid == "swh:1:dir:deadbeef"
    # state: every source fact, including the digest, in the same value
    assert updated.evidence.state.source_available is True
    assert updated.evidence.state.source_acquired_by == "download"
    assert updated.evidence.state.source_snapshot_digest == "sha256:snap"
    assert updated.evidence.state.source_resolved_commit == "abc123"
    # evidence: recorded as history and promoted to selected
    assert receipt in updated.evidence.history
    assert receipt in updated.evidence.selected
    # and the head moved, so the save it was planned from can tell
    assert revision_of(updated) != plan.before_revision


def test_apply_source_acquired_leaves_the_intent_alone_for_an_upload():
    """An upload has no origin to record, and no ref to pin."""
    ree = _sourceless_ree()
    staged = SourceSlot(upstream_populated=False, snapshot_archive_present=False, staged_upload_present=True)
    plan = _plan(
        ree,
        staged,
        SourceRequest(mode="upload", upload_token=_TOKEN, archive_name=ReePath("src.tar.gz")),
    )

    updated = apply_source_acquired(ree, SourceAcquired(plan=plan, observed=_acquired()))

    assert updated.authored.intent.origin_url == ""
    assert updated.authored.intent.revision == ""
    assert updated.evidence.state.source_acquired_by == "upload"
    assert updated.evidence.state.uploaded_archive == "src.tar.gz"


def test_apply_source_acquired_does_not_promote_a_failed_receipt():
    ree = _sourceless_ree()
    plan = _plan(ree)
    failed = _acquire_receipt("run-1").model_copy(update={"status": "failed"})

    updated = apply_source_acquired(
        ree,
        SourceAcquired(plan=plan, observed=_acquired(), receipts=(failed,)),
    )

    assert failed in updated.evidence.history
    assert updated.evidence.selected == ()
