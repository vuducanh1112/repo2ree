from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from repo2ree_core.digests import Digest, digest_bytes
from repo2ree_core.domain.primitives import RunId, ScriptPath
from repo2ree_core.domain.ree.intent import ReeIntent
from repo2ree_core.domain.ree.receipt import (
    BuildRuntimeReceipt,
    CrossCheckSbomReceipt,
    RunExperimentReceipt,
    RunReceipt,
    latest_successful_receipts,
    receipt_run_id,
)
from repo2ree_core.domain.ree.state import ReeLifecycleState
from repo2ree_core.evidence.consistency import (
    ConsistencyReport,
    ConsistencyStep,
    build_consistency_report,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.persistence.receipts import (
    load_author_receipts,
    load_receipts,
    record_receipt,
)
from repo2ree_core.reserved_paths import RESERVED_BUILD_SCRIPT
from repo2ree_core.time_utils import parse_utc_instant
from repo2ree_core.workspace.drift import check_workspace_drift
from repo2ree_core.workspace.materialization import record_materialization


def _silent_log(*_: object) -> None:
    return None


@pytest.fixture
def layout(tmp_path: Path) -> ReeLayout:
    layout = ReeLayout(root=tmp_path)
    ReeDirectory(layout).ensure_dirs()
    return layout


def _build_receipt(run_id: str, recorded_at: str, status: str = "succeeded") -> BuildRuntimeReceipt:
    return BuildRuntimeReceipt(
        run_id=RunId(run_id),
        started_at=parse_utc_instant(recorded_at),
        finished_at=parse_utc_instant(recorded_at),
        duration_ms=0,
        recorded_at=parse_utc_instant(recorded_at),
        status=status,  # type: ignore[arg-type]
        build_script_path=ScriptPath("ree-scripts/build_script.sh"),
        build_script_digest=digest_bytes(b"script"),
    )


class TestPersistence:
    def test_record_and_load_roundtrip(self, layout: ReeLayout) -> None:
        receipt = _build_receipt("run-1", "2026-01-01T00:00:00Z")
        record_receipt(layout, receipt, log=_silent_log)

        loaded = load_receipts(layout)
        assert loaded == [receipt]
        # The immutable JSON receipt sits beside the NDJSON log slot.
        raw = json.loads(layout.run_receipt("run-1").read_text(encoding="utf-8"))
        assert raw["run_id"] == "run-1"
        assert raw["operation"] == "build_runtime"
        assert raw["schema_version"] == 1
        assert raw["duration_ms"] == 0

        selected = load_author_receipts(layout)
        assert selected == {"build_runtime": receipt}
        assert layout.author_operation_receipt("build_runtime").read_bytes() == layout.run_receipt("run-1").read_bytes()

    def test_timing_fields_are_required(self) -> None:
        with pytest.raises(ValidationError):
            BuildRuntimeReceipt.model_validate(
                {
                    "run_id": "legacy",
                    "recorded_at": "2026-01-01T00:00:00Z",
                    "status": "succeeded",
                }
            )

    def test_failed_run_keeps_previous_selected_author_receipt(self, layout: ReeLayout) -> None:
        succeeded = _build_receipt("ok", "2026-01-01T00:00:00Z")
        failed = _build_receipt("failed", "2026-01-02T00:00:00Z", status="failed")
        record_receipt(layout, succeeded, log=_silent_log)
        record_receipt(layout, failed, log=_silent_log)

        assert load_author_receipts(layout)["build_runtime"] == succeeded
        assert layout.run_receipt("failed").is_file()

    def test_run_history_is_never_implicitly_selected(self, layout: ReeLayout) -> None:
        receipt = _build_receipt("historical", "2026-01-01T00:00:00Z")
        layout.run_receipt(receipt.run_id).write_text(receipt.model_dump_json(), encoding="utf-8")

        assert load_receipts(layout) == [receipt]
        assert load_author_receipts(layout) == {}

    def test_experiments_have_independent_selected_paths(self, layout: ReeLayout) -> None:
        first = RunExperimentReceipt(
            run_id=RunId("exp-a-run"),
            started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            finished_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            duration_ms=0,
            recorded_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            status="succeeded",
            experiment_name="Experiment A",
        )
        second = RunExperimentReceipt(
            run_id=RunId("exp-b-run"),
            started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            finished_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            duration_ms=0,
            recorded_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            status="succeeded",
            experiment_name="Experiment B",
        )
        record_receipt(layout, first, log=_silent_log)
        record_receipt(layout, second, log=_silent_log)

        assert load_author_receipts(layout) == {
            "experiment:Experiment A": first,
            "experiment:Experiment B": second,
        }
        assert layout.author_experiment_receipt("Experiment-A").is_file()
        assert layout.author_experiment_receipt("Experiment-B").is_file()

    def test_unparseable_receipts_are_skipped(self, layout: ReeLayout) -> None:
        layout.run_receipt("bad").write_text("{not json", encoding="utf-8")
        record_receipt(layout, _build_receipt("ok", "2026-01-01T00:00:00Z"), log=_silent_log)
        assert [r.run_id for r in load_receipts(layout)] == ["ok"]

    def test_manual_run_ids_are_made_unique(self) -> None:
        assert receipt_run_id("real-id") == "real-id"
        assert receipt_run_id("manual") != receipt_run_id("manual")
        assert receipt_run_id("manual").startswith("manual-")

    def test_cross_check_receipt_roundtrips_with_aggregates(self, layout: ReeLayout) -> None:
        receipt = CrossCheckSbomReceipt(
            run_id=RunId("crosscheck-1"),
            started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            finished_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            duration_ms=0,
            recorded_at=parse_utc_instant("2026-01-01T00:00:00Z"),
            status="succeeded",
            sbom_digest=digest_bytes(b"sbom"),
            declared_direct_total=4,
            observed_matched=3,
            version_mismatches=1,
            undeclared_same_ecosystem=2,
            observed_total=120,
        )
        record_receipt(layout, receipt, log=_silent_log)
        assert load_receipts(layout) == [receipt]
        assert latest_successful_receipts([receipt])["cross_check_sbom"] is receipt


class TestLatestSelection:
    def test_picks_latest_success_and_skips_failures(self) -> None:
        receipts: list[RunReceipt] = [
            _build_receipt("r1", "2026-01-01T00:00:00Z"),
            _build_receipt("r2", "2026-01-02T00:00:00Z"),
            _build_receipt("r3", "2026-01-03T00:00:00Z", status="failed"),
        ]
        latest = latest_successful_receipts(receipts)
        assert latest["build_runtime"].run_id == "r2"

    def test_experiments_are_keyed_per_name(self) -> None:
        def experiment(run_id: str, recorded_at: str, name: str) -> RunExperimentReceipt:
            return RunExperimentReceipt(
                run_id=RunId(run_id),
                started_at=parse_utc_instant(recorded_at),
                finished_at=parse_utc_instant(recorded_at),
                duration_ms=0,
                recorded_at=parse_utc_instant(recorded_at),
                status="succeeded",
                experiment_name=name,
            )

        latest = latest_successful_receipts(
            [
                experiment("r1", "2026-01-01T00:00:00Z", "exp-a"),
                experiment("r2", "2026-01-01T00:00:00Z", "exp-b"),
                experiment("r3", "2026-01-02T00:00:00Z", "exp-a"),
            ]
        )
        assert latest["experiment:exp-a"].run_id == "r3"
        assert latest["experiment:exp-b"].run_id == "r2"


class TestWorkspaceDrift:
    def _materialize(self, layout: ReeLayout, files: dict[str, str]) -> None:
        """Fake a materialization: upstream + workspace share ``files``."""
        for rel, content in files.items():
            (layout.upstream / rel).parent.mkdir(parents=True, exist_ok=True)
            (layout.upstream / rel).write_text(content)
            (layout.workspace / rel).parent.mkdir(parents=True, exist_ok=True)
            (layout.workspace / rel).write_text(content)
        record_materialization(layout, snapshot_digest="sha256:snap", log=_silent_log)

    def test_no_marker_means_unknown(self, layout: ReeLayout) -> None:
        assert check_workspace_drift(layout, excluded_paths=set()).status == "unknown"

    def test_untouched_workspace_is_clean(self, layout: ReeLayout) -> None:
        self._materialize(layout, {"main.py": "print(1)"})
        assert check_workspace_drift(layout, excluded_paths=set()).status == "clean"

    def test_authored_edit_mirrored_to_overlay_is_not_drift(self, layout: ReeLayout) -> None:
        self._materialize(layout, {"main.py": "print(1)"})
        # write_file semantics: content lands in overlay AND workspace, so a
        # re-materialization reproduces it — not drift.
        (layout.overlay / "ree-scripts").mkdir(parents=True)
        (layout.overlay / "ree-scripts" / "build_script.sh").write_text("make all")
        (layout.workspace / "ree-scripts").mkdir(parents=True)
        (layout.workspace / "ree-scripts" / "build_script.sh").write_text("make all")
        assert check_workspace_drift(layout, excluded_paths=set()).status == "clean"

    def test_hand_patched_upstream_file_is_drift(self, layout: ReeLayout) -> None:
        self._materialize(layout, {"main.py": "print(1)"})
        patched = layout.workspace / "main.py"
        patched.write_text("print(2)")
        # The stat-walk is only as fine as filesystem mtime granularity; a
        # real hand-patch happens well after materialization, so model that.
        os.utime(patched, ns=(patched.stat().st_atime_ns, patched.stat().st_mtime_ns + 1_000_000))
        drift = check_workspace_drift(layout, excluded_paths=set())
        assert drift.status == "modified"
        assert drift.changed_paths == ["main.py"]
        assert drift.changed_path_count == 1

    def test_deleted_materialized_file_is_drift(self, layout: ReeLayout) -> None:
        self._materialize(layout, {"main.py": "print(1)"})
        (layout.workspace / "main.py").unlink()
        drift = check_workspace_drift(layout, excluded_paths=set())
        assert drift.status == "modified"
        assert drift.changed_paths == ["main.py"]

    def test_residue_file_is_drift_but_declared_outputs_are_excluded(self, layout: ReeLayout) -> None:
        self._materialize(layout, {"main.py": "print(1)"})
        (layout.workspace / "runtime.tar").write_bytes(b"tar")
        (layout.workspace / "leftover.log").write_text("junk")
        drift = check_workspace_drift(layout, excluded_paths={"runtime.tar"})
        assert drift.status == "modified"
        assert drift.changed_paths == ["leftover.log"]


class TestConsistencyReport:
    def _seed(self, layout: ReeLayout, intent: ReeIntent) -> tuple[ReeIntent, ReeLifecycleState]:
        session = ReeLifecycleState(source_snapshot_digest=Digest("sha256:snap"))
        script = layout.workspace / "ree-scripts" / "build_script.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("make all")
        return intent, session

    def _record_build(self, layout: ReeLayout) -> None:
        record_receipt(
            layout,
            BuildRuntimeReceipt(
                run_id=RunId("run-b"),
                started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
                finished_at=parse_utc_instant("2026-01-01T00:00:00Z"),
                duration_ms=0,
                recorded_at=parse_utc_instant("2026-01-01T00:00:00Z"),
                status="succeeded",
                snapshot_digest=Digest("sha256:snap"),
                build_script_path=ScriptPath("ree-scripts/build_script.sh"),
                build_script_digest=digest_bytes(b"make all"),
            ),
            log=_silent_log,
        )

    def _step(self, report: ConsistencyReport, name: str) -> ConsistencyStep:
        return next(s for s in report.steps if s.step == name)

    def test_matching_receipt_is_fresh(self, layout: ReeLayout) -> None:
        intent, session = self._seed(layout, ReeIntent())
        self._record_build(layout)
        step = self._step(build_consistency_report(layout, intent, session), "build_runtime")
        assert step.status == "fresh"
        assert step.stale_inputs == []

    def test_edited_build_script_names_the_moved_input(self, layout: ReeLayout) -> None:
        intent, session = self._seed(layout, ReeIntent())
        self._record_build(layout)
        (layout.workspace / "ree-scripts" / "build_script.sh").write_text("make other")

        step = self._step(build_consistency_report(layout, intent, session), "build_runtime")
        assert step.status == "stale"
        assert [entry.input for entry in step.stale_inputs] == ["build_script"]
        assert step.stale_inputs[0].recorded == digest_bytes(b"make all")
        assert step.stale_inputs[0].current == digest_bytes(b"make other")

    def test_steps_without_receipts_are_missing(self, layout: ReeLayout) -> None:
        intent, session = self._seed(layout, ReeIntent())
        report = build_consistency_report(layout, intent, session)
        assert {s.step: s.status for s in report.steps} == {
            "build_runtime": "missing",
            "generate_sbom": "missing",
            "activation_test": "missing",
        }

    def test_experiment_verify_script_change_is_stale(self, layout: ReeLayout) -> None:
        intent = ReeIntent.model_validate(
            {
                "experiments": [
                    {
                        "name": "exp-a",
                        "run_script": "ree-scripts/experiments/exp-a.sh",
                        "verify_script": "ree-scripts/experiments/exp-a.verify.sh",
                    }
                ]
            }
        )
        intent, session = self._seed(layout, intent)
        experiment = intent.experiments[0]
        script = layout.workspace / experiment.run_script
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("run it")
        verify = layout.workspace / experiment.verify_script
        verify.write_text("check it")

        record_receipt(
            layout,
            RunExperimentReceipt(
                run_id=RunId("run-e"),
                started_at=parse_utc_instant("2026-01-01T00:00:00Z"),
                finished_at=parse_utc_instant("2026-01-01T00:00:00Z"),
                duration_ms=0,
                recorded_at=parse_utc_instant("2026-01-01T00:00:00Z"),
                status="succeeded",
                experiment_name="exp-a",
                snapshot_digest=Digest("sha256:snap"),
                run_script_path=ScriptPath(experiment.run_script),
                run_script_digest=digest_bytes(b"run it"),
                verify_script_path=ScriptPath(experiment.verify_script),
                verify_script_digest=digest_bytes(b"check it"),
            ),
            log=_silent_log,
        )

        fresh = self._step(build_consistency_report(layout, intent, session), "experiment:exp-a")
        assert fresh.status == "fresh"

        verify.write_text("check something else")
        stale = self._step(build_consistency_report(layout, intent, session), "experiment:exp-a")
        assert stale.status == "stale"
        assert [entry.input for entry in stale.stale_inputs] == ["verify_script"]


class TestHandlerWiring:
    """The executor-side wiring: handlers record receipts as they run."""

    @pytest.fixture
    def workbench(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReeDirectory:
        from repo2ree_core.persistence.sidecar import ReeSidecar

        layout = ReeLayout(root=tmp_path)
        store = ReeDirectory(layout)
        store.ensure_dirs()
        store.write_sidecar(
            ReeSidecar(
                ree_id="ree123",
                name="demo",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                ree_intent=ReeIntent(runtime="runtime.tar"),
                ree_state=ReeLifecycleState(source_snapshot_digest=Digest("sha256:snap")),
            )
        )
        monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: ReeLayout(root=tmp_path)))
        return store

    def test_build_run_records_receipt_with_input_slice_and_produced_digest(self, workbench: ReeDirectory) -> None:
        from repo2ree_core.operations.handlers.author.build_runtime import handle_build_runtime

        layout = workbench.layout
        script = layout.workspace / RESERVED_BUILD_SCRIPT
        script.parent.mkdir(parents=True)
        script.write_text("printf runtime-bytes > runtime.tar\n")

        result = handle_build_runtime(run_id="run-42", log=_silent_log, is_canceled=lambda: False)

        assert result.status == "succeeded"
        receipt = json.loads(layout.run_receipt("run-42").read_text(encoding="utf-8"))
        assert receipt["operation"] == "build_runtime"
        assert receipt["status"] == "succeeded"
        assert receipt["snapshot_digest"] == "sha256:snap"
        assert receipt["build_script_digest"] == digest_bytes(script.read_bytes())
        assert receipt["produced_runtime_digest"] == digest_bytes(b"runtime-bytes")
        assert receipt["workspace_drift"]["status"] == "unknown"  # never materialized
        assert result.outputs["receipt"] == receipt

    def _seed_experiment(self, workbench: ReeDirectory, *, runtime: str = "runtime.tar") -> ReeIntent:
        from repo2ree_core.persistence.sidecar import ReeSidecar

        layout = workbench.layout
        intent = ReeIntent.model_validate(
            {
                "runtime": runtime,
                "experiments": [
                    {
                        "name": "exp-a",
                        "run_script": "ree-scripts/experiments/exp-a.sh",
                        "output_paths": ["results/out.txt"],
                    }
                ],
            }
        )
        workbench.write_sidecar(
            ReeSidecar(
                ree_id="ree123",
                name="demo",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
                ree_intent=intent,
                ree_state=ReeLifecycleState(source_snapshot_digest=Digest("sha256:snap")),
            )
        )
        script = layout.workspace / "ree-scripts" / "experiments" / "exp-a.sh"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("mkdir -p results && printf answer > results/out.txt\n")
        return intent

    def test_experiment_run_captures_outputs_and_records_digest(self, workbench: ReeDirectory) -> None:
        from repo2ree_core.digests import digest_output_paths
        from repo2ree_core.operations.handlers.author.run_experiment import handle_run_experiment
        from repo2ree_protocol.command import RunExperimentArgs

        self._seed_experiment(workbench)
        layout = workbench.layout

        result = handle_run_experiment(
            RunExperimentArgs(experiment_name="exp-a"),
            run_id="run-e",
            log=_silent_log,
            is_canceled=lambda: False,
        )

        assert result.status == "succeeded"
        # Output captured into the produced-results store, keyed by name.
        assert (layout.results_dir("exp-a") / "results" / "out.txt").read_text() == "answer"
        receipt = json.loads(layout.run_receipt("run-e").read_text(encoding="utf-8"))
        assert receipt["produced_output_digest"] == digest_output_paths(layout.workspace, ["results/out.txt"])

    def test_native_experiment_run_warns_and_omits_runtime_binding(self, workbench: ReeDirectory) -> None:
        from repo2ree_core.operations.handlers.author.run_experiment import handle_run_experiment
        from repo2ree_protocol.command import RunExperimentArgs

        self._seed_experiment(workbench, runtime="")
        layout = workbench.layout
        lines: list[tuple[str, str, str]] = []

        result = handle_run_experiment(
            RunExperimentArgs(experiment_name="exp-a"),
            run_id="run-native",
            log=lambda stream, level, message: lines.append((stream, level, message)),
            is_canceled=lambda: False,
        )

        assert result.status == "succeeded"
        warns = [message for stream, level, message in lines if level == "warn"]
        assert any("No runtime artifact declared" in message for message in warns)
        receipt = json.loads(layout.run_receipt("run-native").read_text(encoding="utf-8"))
        assert receipt["runtime_path"] is None
        assert receipt["declared_runtime_digest"] is None

    def test_rewritten_output_makes_experiment_stale(self, workbench: ReeDirectory) -> None:
        from repo2ree_core.operations.handlers.author.run_experiment import handle_run_experiment
        from repo2ree_protocol.command import RunExperimentArgs

        intent = self._seed_experiment(workbench)
        layout = workbench.layout
        handle_run_experiment(
            RunExperimentArgs(experiment_name="exp-a"),
            run_id="run-e",
            log=_silent_log,
            is_canceled=lambda: False,
        )

        session = workbench.read_state()
        fresh = build_consistency_report(layout, intent, session)
        exp = next(s for s in fresh.steps if s.step == "experiment:exp-a")
        assert exp.status == "fresh"

        # The shared workspace mutated the declared output after the run.
        (layout.workspace / "results" / "out.txt").write_text("tampered")
        stale = build_consistency_report(layout, intent, session)
        exp = next(s for s in stale.steps if s.step == "experiment:exp-a")
        assert exp.status == "stale"
        assert "produced_output" in [entry.input for entry in exp.stale_inputs]

    def test_snapshot_upstream_reports_its_digest_and_records_nothing(self, workbench: ReeDirectory) -> None:
        """The freeze is an effect: it returns the digest and touches no REE state.

        Persisting from here is what used to let a receipt claim a digest the
        state never received. The acquire lifecycle holds the hydrated REE the
        digest belongs to, so it is the only thing that records it.
        """
        from repo2ree_core.digests import digest_file
        from repo2ree_core.operations.handlers.author.snapshot_upstream import handle_snapshot_upstream

        layout = workbench.layout
        (layout.upstream / "a.txt").write_text("alpha")
        before = workbench.read_state().source_snapshot_digest

        result = handle_snapshot_upstream(run_id="run-snap", log=_silent_log, is_canceled=lambda: False)

        assert result.status == "succeeded"
        expected = digest_file(layout.snapshot_archive)
        assert result.outputs["snapshot_digest"] == expected
        assert workbench.read_state().source_snapshot_digest == before
        assert not layout.run_receipt("run-snap").exists()


class TestCurrentRuntimeDigest:
    def test_caches_by_stat_and_invalidates_on_change(self, layout: ReeLayout) -> None:
        from repo2ree_core.workspace.drift import current_runtime_digest

        runtime = layout.workspace / "runtime.tar"
        runtime.write_bytes(b"tar-v1")

        first = current_runtime_digest(layout, "runtime.tar")
        assert first == digest_bytes(b"tar-v1")
        # Cache is primed; poison the real file digestion path by asserting the
        # cache file exists and short-circuits to the same digest.
        assert layout.digest_cache.is_file()
        assert current_runtime_digest(layout, "runtime.tar") == first

        runtime.write_bytes(b"tar-v2-longer")  # different size → stat mismatch
        assert current_runtime_digest(layout, "runtime.tar") == digest_bytes(b"tar-v2-longer")

    def test_missing_or_undeclared_runtime_is_none(self, layout: ReeLayout) -> None:
        from repo2ree_core.workspace.drift import current_runtime_digest

        assert current_runtime_digest(layout, None) is None
        assert current_runtime_digest(layout, "absent.tar") is None
