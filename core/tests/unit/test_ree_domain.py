import pytest
from pydantic import ValidationError

from repo2ree_core.digests import Digest, digest_bytes
from repo2ree_core.domain.primitives import GitRevision, ReeId, ReePath, RunId, ScriptPath, WorkspacePath
from repo2ree_core.domain.ree.assessment import assess
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.model import AuthoredFile, Ree, ReeDefinition, ReeEvidence, ReeIdentity
from repo2ree_core.domain.ree.queries import name_of, runtime_of, scripts_of
from repo2ree_core.domain.ree.receipt import BuildRuntimeReceipt, WorkspaceDrift
from repo2ree_core.domain.ree.state import ReeLifecycleState, record_evaluation, record_source, select_packaging
from repo2ree_core.domain.ree.transitions import request_runtime_build, revision_of, write_file
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


def test_session_with_source_sets_available():
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    session = ReeLifecycleState()
    updated = record_source(
        session,
        acquired_by="download",
        snapshot_archive=ReePath("snapshot.tar.gz"),
        snapshot_captured_at=parse_utc_instant("2026-01-01T00:00:00Z"),
    )
    assert updated.source_available is True
    assert updated.source_acquired_by == "download"
    assert updated.source_snapshot_archive == "snapshot.tar.gz"


def test_session_with_source_records_resolved_commit():
    from repo2ree_core.domain.ree.state import ReeLifecycleState

    session = ReeLifecycleState()
    updated = record_source(
        session,
        acquired_by="download",
        resolved_commit=GitRevision("abc123"),
    )
    assert updated.source_resolved_commit == "abc123"


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


def test_ree_is_data_only_and_transitions_are_external_functions():
    assert not hasattr(Ree, "patch_intent")
    assert not hasattr(Ree, "write_file")
    assert not hasattr(Ree, "request_runtime_build")
    assert not hasattr(Ree, "assessment")


def test_unrelated_file_edit_changes_revision_but_not_runtime_freshness():
    build = AuthoredFile(path=ReePath(RESERVED_BUILD_SCRIPT), digest=digest_bytes(b"build"), size=5)
    receipt = _successful_build(script_digest=build.digest)
    ree = _ree(intent=ReeIntent(name="demo", runtime="runtime.tar"), files=(build,), selected=(receipt,))

    transition = write_file(ree, ReePath("notes.txt"), b"new metadata-like content")
    updated = ree.model_copy(update={"authored": transition.authored})

    assert transition.after_revision != transition.before_revision
    assert assess(updated).runtime.status == "ready"


def test_build_script_edit_makes_matching_runtime_evidence_stale():
    build = AuthoredFile(path=ReePath(RESERVED_BUILD_SCRIPT), digest=digest_bytes(b"build"), size=5)
    receipt = _successful_build(script_digest=build.digest)
    ree = _ree(intent=ReeIntent(name="demo", runtime="runtime.tar"), files=(build,), selected=(receipt,))

    transition = write_file(ree, ReePath(RESERVED_BUILD_SCRIPT), b"different build")
    updated = ree.model_copy(update={"authored": transition.authored})

    assert assess(updated).runtime.status == "stale"
    assert assess(updated).runtime.reasons == ("runtime build script changed",)


def test_runtime_build_transition_pins_revision_and_inputs():
    build_digest = digest_bytes(b"build")
    ree = _ree(
        intent=ReeIntent(name="demo", runtime="runtime.tar"),
        files=(AuthoredFile(path=ReePath(RESERVED_BUILD_SCRIPT), digest=build_digest, size=5),),
    )

    transition = request_runtime_build(
        ree,
        snapshot_digest=Digest("sha256:snapshot"),
        build_script_digest=build_digest,
    )

    assert transition.ree_id == "ree-1"
    assert transition.revision == revision_of(ree)
    assert transition.snapshot_digest == "sha256:snapshot"
    assert transition.build_script_digest == build_digest
