from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from ree_definitions import LAUNCH, ree_definition, with_fixed_scripts

from repo2ree_authoring.templates import reserved_script_template
from repo2ree_core.digests import digest_tree
from repo2ree_core.evidence.review.records import new_review_record, step_state, with_step
from repo2ree_core.evidence.review.store import load_reviews, read_review_record, write_review_record
from repo2ree_core.operations.handlers.review import (
    acquire_source,
    activate_experiment_environment,
    build_experiment_environment,
    run_experiment,
)
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout, ReviewLayout
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_protocol.command import (
    ReviewAcquireSourceArgs,
    ReviewActivateExperimentEnvironmentArgs,
    ReviewBuildExperimentEnvironmentArgs,
    ReviewRunExperimentArgs,
)
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.instant import parse_utc_instant
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    CheckWorkingEnvironmentDefinition,
    ExperimentDefinition,
    ExperimentEnvironmentDefinition,
    LaunchDefinition,
    Ree,
    ReeReceipts,
    ReeSubject,
    SourceDefinition,
)
from repo2ree_ree.primitives import (
    ExperimentEnvironmentPath,
    LaunchOption,
    OverlayPath,
    RunId,
    Swhid,
    WorkspacePath,
)
from repo2ree_ree.receipt import AcquireSourceReceipt, RunExperimentReceipt
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
    RESERVED_LAUNCH_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)
from repo2ree_ree.review import (
    EvidenceBasis,
    ExperimentEnvironmentComparison,
    ReviewAcquireSourceReceipt,
    ReviewBuildExperimentEnvironmentReceipt,
    ReviewLaunch,
    ReviewReceipts,
    ReviewRecord,
    ReviewSubject,
    SourceComparison,
)

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_REVIEW_ID = "review-one"
_SUBJECT = ReviewSubject(name="ree-under-review")
_EXPERIMENT_ENVIRONMENT_PATH = "runtime.tar"
_EXPERIMENT_ENVIRONMENT = b"experiment environment bytes\n"
_ACTIVATE = b'#!/bin/sh\nexec "$@"\n'


def _build_recipe(experiment_environment_path: ExperimentEnvironmentPath) -> ExperimentEnvironmentDefinition:
    return ExperimentEnvironmentDefinition(
        build_experiment_environment_script_digest=digest_bytes(b"build_experiment_environment"),
        build_experiment_environment_script_size=5,
        artifact_path=experiment_environment_path,
    )


_EXPERIMENT_NAME = "demo"
_EXPERIMENT = b"#!/bin/sh\nmkdir -p outputs && printf result > outputs/result.txt\n"
_EXPERIMENT_VERIFY = b'#!/bin/sh\ntest "$(cat outputs/result.txt)" = result\n'


_DIRECT = reserved_script_template(RESERVED_LAUNCH_SCRIPT).encode()


def _author_ree(launch: bytes = _DIRECT) -> Ree:
    experiment = ExperimentDefinition(
        name=_EXPERIMENT_NAME,
        run_script_path=OverlayPath(experiment_run_script_path(_EXPERIMENT_NAME)),
        run_script_digest=digest_bytes(_EXPERIMENT),
        run_script_size=len(_EXPERIMENT),
        verify_script_path=OverlayPath(experiment_verify_script_path(_EXPERIMENT_NAME)),
        verify_script_digest=digest_bytes(_EXPERIMENT_VERIFY),
        verify_script_size=len(_EXPERIMENT_VERIFY),
        output_paths=(WorkspacePath("outputs/result.txt"),),
    )
    author_experiment = RunExperimentReceipt(
        run_id=RunId("author-experiment"),
        started_at=_NOW,
        finished_at=_NOW,
        duration_ms=0,
        recorded_at=_NOW,
        experiment_name=_EXPERIMENT_NAME,
        snapshot_digest=digest_bytes(b"snapshot"),
        experiment_environment_digest=digest_bytes(_EXPERIMENT_ENVIRONMENT),
        activate_experiment_environment_script_digest=digest_bytes(_ACTIVATE),
        run_script_digest=digest_bytes(_EXPERIMENT),
        verify_script_digest=digest_bytes(_EXPERIMENT_VERIFY),
        verify_exit_code=0,
        launch_script_digest=LAUNCH,
    )
    return Ree(
        subject=ReeSubject(
            definition=ree_definition(
                experiment_environment=_build_recipe(ExperimentEnvironmentPath(_EXPERIMENT_ENVIRONMENT_PATH)),
                activate_experiment_environment=ActivateExperimentEnvironmentDefinition(
                    activate_experiment_environment_script_digest=digest_bytes(_ACTIVATE),
                    activate_experiment_environment_script_size=len(_ACTIVATE),
                ),
                experiments=(experiment,),
                launch=LaunchDefinition(launch_script_digest=digest_bytes(launch), launch_script_size=len(launch)),
            ),
            receipts=ReeReceipts(experiments={_EXPERIMENT_NAME: author_experiment}),
        )
    )


def _acquired(
    review: ReviewLayout, *, basis: EvidenceBasis = "independent", launch: ReviewLaunch | None = None
) -> ReviewRecord:
    review.upstream.mkdir(parents=True, exist_ok=True)
    (review.upstream / "source.txt").write_text("source\n")
    record = with_step(
        new_review_record(_REVIEW_ID, subject=_SUBJECT, at=parse_utc_instant("2026-08-03T00:00:00Z"), launch=launch),
        "acquire_source",
        status="completed",
        at=parse_utc_instant("2026-08-03T00:00:01Z"),
    )
    return record.model_copy(
        update={
            "source_comparison": SourceComparison(basis=basis, verdict="identical"),
            "receipts": ReviewReceipts(
                acquire_source=ReviewAcquireSourceReceipt(
                    run_id=RunId("review-source"),
                    started_at=_NOW,
                    finished_at=_NOW,
                    duration_ms=0,
                    recorded_at=_NOW,
                    status="succeeded",
                    source_type="",
                    observed_swhid=Swhid(directory_swhid(review.upstream)),
                )
            ),
        }
    )


def _workbench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    activate: bytes = _ACTIVATE,
    launch: bytes = _DIRECT,
    reviewer_launch: ReviewLaunch | None = None,
    reviewer_copy: bytes | None = None,
) -> ReeLayout:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_ree(_author_ree(launch))
    review = layout.review(_REVIEW_ID)
    kept = review.kept_environment(_EXPERIMENT_ENVIRONMENT_PATH)
    kept.parent.mkdir(parents=True)
    kept.write_bytes(_EXPERIMENT_ENVIRONMENT)
    files = {
        RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT: activate,
        experiment_run_script_path(_EXPERIMENT_NAME): _EXPERIMENT,
        experiment_verify_script_path(_EXPERIMENT_NAME): _EXPERIMENT_VERIFY,
    }
    files[RESERVED_LAUNCH_SCRIPT] = reviewer_copy if reviewer_copy is not None else launch
    for relative, contents in files.items():
        target = review.overlay / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    record = _acquired(review, launch=reviewer_launch)
    record = with_step(
        record, "build_experiment_environment", status="completed", at=parse_utc_instant("2026-08-03T00:00:02Z")
    )
    record = record.model_copy(
        update={
            "experiment_environment_comparison": ExperimentEnvironmentComparison(
                basis="independent", verdict="identical"
            ),
            "receipts": record.receipts.model_copy(
                update={
                    "build_experiment_environment": ReviewBuildExperimentEnvironmentReceipt(
                        run_id=RunId("review-build"),
                        started_at=_NOW,
                        finished_at=_NOW,
                        duration_ms=0,
                        recorded_at=_NOW,
                        status="succeeded",
                        artifact_path=WorkspacePath(_EXPERIMENT_ENVIRONMENT_PATH),
                        produced_artifact_digest=digest_bytes(_EXPERIMENT_ENVIRONMENT),
                        overlay_digest=digest_tree(review.overlay),
                    )
                }
            ),
        }
    )
    write_review_record(review, record)
    return layout


def _activate(layout: ReeLayout):
    return activate_experiment_environment.handle_review_activate_experiment_environment(
        ReviewActivateExperimentEnvironmentArgs(review_id=_REVIEW_ID),
        run_id="review-activation",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )


def test_source_review_reads_definition_and_author_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is required for local review acquisition")
    origin = tmp_path / "origin"
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    (origin / "source.txt").write_text("source\n")
    git = ["git", "-C", str(origin), "-c", "user.name=Test", "-c", "user.email=test@example.test"]
    subprocess.run([*git, "add", "source.txt"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "source"], check=True)
    revision = subprocess.run(
        [*git, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    swhid = directory_swhid(origin)

    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_ree(
        with_fixed_scripts(
            layout,
            Ree(
                subject=ReeSubject(
                    definition=ree_definition(
                        source=SourceDefinition(origin_url=str(origin), source_type="git", requested_ref=revision)
                    ),
                    receipts=ReeReceipts(
                        acquire_source=AcquireSourceReceipt(
                            run_id=RunId("author-source"),
                            started_at=_NOW,
                            finished_at=_NOW,
                            duration_ms=0,
                            recorded_at=_NOW,
                            origin_url=str(origin),
                            source_type="git",
                            requested_ref=revision,
                            resolved_revision=revision,
                            observed_swhid=Swhid(swhid),
                            snapshot_digest=digest_bytes(b"snapshot"),
                        )
                    ),
                )
            ),
        )
    )
    result = acquire_source.handle_review_acquire_source(
        ReviewAcquireSourceArgs(review_id=_REVIEW_ID, basis="independent"),
        run_id="review-source",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "identical"
    assert result.outputs["receipt"]["requested_ref"] == revision
    assert (layout.review(_REVIEW_ID).upstream / "source.txt").read_text() == "source\n"
    record = read_review_record(layout.review(_REVIEW_ID))
    assert record is not None
    definition = store.read_ree().subject.definition
    assert record.subject == ReviewSubject(
        name=definition.name,
        version=definition.catalog.version,
        ree_digest=None,
        experiments=tuple(experiment.name for experiment in definition.experiments),
    ), "a draft is named by what it declares, and by no seal"
    assert record.machine.system
    assert record.machine.architecture


def test_bundled_experiment_environment_review_records_only_the_input_it_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.artifacts.write_bytes("runtime.tar", _EXPERIMENT_ENVIRONMENT)
    store.write_ree(
        with_fixed_scripts(
            layout,
            Ree(
                subject=ReeSubject(
                    definition=ree_definition(
                        experiment_environment=_build_recipe(ExperimentEnvironmentPath("artifacts/runtime.tar"))
                    )
                )
            ),
        )
    )
    review = layout.review(_REVIEW_ID)
    write_review_record(review, _acquired(review, basis="bundled"))

    result = build_experiment_environment.handle_review_build_experiment_environment(
        ReviewBuildExperimentEnvironmentArgs(review_id=_REVIEW_ID, basis="bundled"),
        run_id="review-build",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "succeeded"
    assert result.outputs["receipt"]["build_experiment_environment_script_path"] is None
    assert result.outputs["receipt"]["build_experiment_environment_script_digest"] is None
    assert result.outputs["receipt"]["produced_artifact_digest"] == digest_bytes(_EXPERIMENT_ENVIRONMENT)
    assert result.outputs["receipt"]["overlay_digest"] == digest_tree(review.overlay)
    assert review.kept_environment("artifacts/runtime.tar").read_bytes() == _EXPERIMENT_ENVIRONMENT
    assert not list(review.runs.glob("*.workspace")), "a build that succeeded leaves no workspace"
    assert not review.workspace.exists()
    assert len(load_reviews(layout).reviews) == 1


def test_an_independent_review_build_keeps_what_it_built_beside_the_review(tmp_path: Path) -> None:
    build = b"#!/bin/sh\nprintf built > runtime.tar\n"
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.overlay.write_bytes(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT, build)
    store.write_ree(
        with_fixed_scripts(
            layout,
            Ree(
                subject=ReeSubject(
                    definition=ree_definition(
                        experiment_environment=_build_recipe(ExperimentEnvironmentPath(_EXPERIMENT_ENVIRONMENT_PATH))
                    )
                )
            ),
        )
    )
    review = layout.review(_REVIEW_ID)
    write_review_record(review, _acquired(review))

    result = build_experiment_environment.handle_review_build_experiment_environment(
        ReviewBuildExperimentEnvironmentArgs(review_id=_REVIEW_ID, basis="independent"),
        run_id="review-build",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "succeeded"
    assert result.outputs["receipt"]["build_experiment_environment_script_digest"] == digest_bytes(build)
    assert result.outputs["receipt"]["produced_artifact_digest"] == digest_bytes(b"built")
    assert review.kept_environment(_EXPERIMENT_ENVIRONMENT_PATH).read_bytes() == b"built"
    assert not list(review.runs.glob("*.workspace"))


@pytest.mark.parametrize(("check", "status"), [(b"exit 0\n", "succeeded"), (b"echo no gpu >&2; exit 3\n", "failed")])
def test_a_review_runs_the_authors_check_before_anything_else_runs_there(
    tmp_path: Path, check: bytes, status: str
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.artifacts.write_bytes("runtime.tar", _EXPERIMENT_ENVIRONMENT)
    store.overlay.write_bytes(RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT, check)
    store.write_ree(
        with_fixed_scripts(
            layout,
            Ree(
                subject=ReeSubject(
                    definition=ree_definition(
                        experiment_environment=_build_recipe(ExperimentEnvironmentPath("artifacts/runtime.tar")),
                        check_working_environment=CheckWorkingEnvironmentDefinition(
                            check_working_environment_script_digest=digest_bytes(check),
                            check_working_environment_script_size=len(check),
                        ),
                    )
                )
            ),
        )
    )
    review = layout.review(_REVIEW_ID)
    write_review_record(review, _acquired(review, basis="bundled"))
    lines: list[str] = []

    result = build_experiment_environment.handle_review_build_experiment_environment(
        ReviewBuildExperimentEnvironmentArgs(review_id=_REVIEW_ID, basis="bundled"),
        run_id="review-build",
        log=lambda _stream, _level, message: lines.append(message),
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == status
    if status == "failed":
        assert "no gpu" in lines
        assert result.failure is not None
        assert "does not pass the author's check" in result.failure.message


def test_failed_activation_is_completed_review_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _workbench(tmp_path, monkeypatch, activate=b"#!/bin/sh\nexit 7\n")

    result = _activate(layout)

    assert result.status == "succeeded"
    assert result.outputs["outcome"]["verdict"] == "failed"
    assert result.outputs["receipt"]["status"] == "failed"
    assert result.outputs["receipt"]["exit_code"] == 7
    record = read_review_record(layout.review(_REVIEW_ID))
    assert record is not None
    assert step_state(record, "activate_experiment_environment").status == "completed"  # type: ignore[union-attr]


def test_experiment_uses_definition_and_author_receipt_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _workbench(tmp_path, monkeypatch)
    assert _activate(layout).outputs["outcome"]["verdict"] == "passed"

    result = run_experiment.handle_review_run_experiment(
        ReviewRunExperimentArgs(review_id=_REVIEW_ID, experiment_name=_EXPERIMENT_NAME),
        run_id="review-experiment",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "reproduced"
    assert result.outputs["receipt"]["status"] == "succeeded"
    assert result.outputs["receipt"]["verify_script_digest"] == digest_bytes(_EXPERIMENT_VERIFY)
    record = read_review_record(layout.review(_REVIEW_ID))
    assert record is not None
    assert [receipt.experiment_name for receipt in record.receipts.experiments] == [_EXPERIMENT_NAME]


def test_an_experiment_run_through_another_activate_script_is_inconclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _workbench(tmp_path, monkeypatch, activate=b'#!/bin/sh\necho elsewhere\nexec "$@"\n')
    assert _activate(layout).outputs["outcome"]["verdict"] == "passed"

    result = run_experiment.handle_review_run_experiment(
        ReviewRunExperimentArgs(review_id=_REVIEW_ID, experiment_name=_EXPERIMENT_NAME),
        run_id="review-experiment",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )

    comparison = result.outputs["comparison"]
    assert comparison["verdict"] == "inconclusive"
    assert comparison["expected_activate_experiment_environment_script_digest"] == digest_bytes(_ACTIVATE)


def _launch(options: Path) -> bytes:
    return (
        b"#!/bin/sh\nSLURM_JOB_ID=4711\nexport SLURM_JOB_ID\n"
        + f'printf "%s" "${{REE_LAUNCH_OPTIONS:-}}" > {options}\n'.encode()
        + b'exec "$@"\n'
    )


def _experiment(layout: ReeLayout) -> dict[str, Any]:
    result = run_experiment.handle_review_run_experiment(
        ReviewRunExperimentArgs(review_id=_REVIEW_ID, experiment_name=_EXPERIMENT_NAME),
        run_id="review-experiment",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )
    assert result.status == "succeeded"
    return result.outputs


def test_a_review_launches_the_authors_scripts_through_the_authors_launch_with_its_own_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = tmp_path / "options.txt"
    launch = _launch(options)
    layout = _workbench(
        tmp_path,
        monkeypatch,
        launch=launch,
        reviewer_launch=ReviewLaunch(options=(LaunchOption("--partition=short"),)),
    )
    activation = _activate(layout).outputs["receipt"]
    assert activation["launch_script_digest"] == digest_bytes(launch)
    assert activation["launched"]["slurm_job_id"] == "4711"
    assert options.read_text() == "--partition=short"

    outputs = _experiment(layout)
    assert outputs["receipt"]["launched"]["slurm_job_id"] == "4711"
    assert outputs["comparison"]["expected_launch_script_digest"] == LAUNCH
    assert outputs["comparison"]["launch_script_digest"] == digest_bytes(launch)
    assert outputs["comparison"]["verdict"] == "reproduced"


def test_a_review_that_chose_native_runs_the_authors_scripts_directly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = tmp_path / "options.txt"
    layout = _workbench(tmp_path, monkeypatch, launch=_launch(options), reviewer_launch=ReviewLaunch(mode="native"))
    activation = _activate(layout).outputs["receipt"]
    assert (activation["launch_script_digest"], activation["launched"]) == (None, None)
    assert not options.exists()
    assert _experiment(layout)["comparison"]["verdict"] == "reproduced"


def test_a_review_does_not_launch_through_a_copy_that_is_not_the_authors_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = _launch(tmp_path / "options.txt")
    layout = _workbench(tmp_path, monkeypatch, launch=launch, reviewer_copy=launch + b"# edited\n")
    result = _activate(layout)
    assert result.status == "failed"
    assert result.failure is not None
    assert "cannot launch the author's scripts" in result.failure.message


def _experiment_result(layout: ReeLayout):
    return run_experiment.handle_review_run_experiment(
        ReviewRunExperimentArgs(review_id=_REVIEW_ID, experiment_name=_EXPERIMENT_NAME),
        run_id="review-experiment",
        log=lambda *_: None,
        is_canceled=lambda: False,
        layout=layout,
    )


def test_each_review_step_runs_in_a_workspace_of_its_own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _workbench(tmp_path, monkeypatch, activate=b'#!/bin/sh\ntest ! -e left || exit 9\ntouch left\nexec "$@"\n')
    assert _activate(layout).outputs["outcome"]["verdict"] == "passed"
    assert not list(layout.review(_REVIEW_ID).runs.glob("*.workspace"))

    result = _experiment_result(layout)

    assert result.status == "succeeded"
    assert result.outputs["receipt"]["run_exit_code"] == 0
    assert result.outputs["receipt"]["verify_exit_code"] == 0


def test_a_review_step_refuses_an_overlay_changed_since_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _workbench(tmp_path, monkeypatch)
    (layout.review(_REVIEW_ID).overlay / experiment_run_script_path(_EXPERIMENT_NAME)).write_bytes(b"exit 0\n")

    result = _activate(layout)

    assert result.status == "failed"
    assert result.failure is not None
    assert "not the one its build copied" in result.failure.message


def test_a_review_step_refuses_an_experiment_environment_not_the_one_certified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _workbench(tmp_path, monkeypatch)
    layout.review(_REVIEW_ID).kept_environment(_EXPERIMENT_ENVIRONMENT_PATH).write_bytes(b"another\n")

    result = _activate(layout)

    assert result.status == "failed"
    assert result.failure is not None
    assert "not the one this review certified" in result.failure.message


def test_a_review_step_refuses_a_source_not_the_one_acquired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _workbench(tmp_path, monkeypatch)
    (layout.review(_REVIEW_ID).upstream / "source.txt").write_text("edited\n")

    result = _activate(layout)

    assert result.status == "failed"
    assert result.failure is not None
    assert "not the one its acquisition observed" in result.failure.message
