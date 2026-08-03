from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repo2ree_core.digests import digest_bytes
from repo2ree_core.domain.primitives import ReePath, RunId, Swhid, WorkspacePath
from repo2ree_core.domain.ree.model import (
    ExperimentDefinition,
    Ree,
    ReeDefinition,
    ReeReceipts,
    ReeSubject,
    RuntimeDefinition,
    SourceDefinition,
)
from repo2ree_core.domain.ree.model import TestActivationDefinition as ActivationDefinition
from repo2ree_core.domain.ree.receipt import AcquireSourceReceipt, RunExperimentReceipt
from repo2ree_core.evidence.review.models import (
    BuildComparison,
    ReviewBuildRuntimeReceipt,
    SourceComparison,
    new_review_record,
    step_state,
    with_step,
)
from repo2ree_core.evidence.review.store import load_reviews, read_review_record, write_review_record
from repo2ree_core.operations.handlers.review import acquire_source, activation_test, build_runtime, run_experiment
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import (
    RESERVED_ACTIVATION_SCRIPT,
    RESERVED_ACTIVATION_VERIFY_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)
from repo2ree_core.source_repo.swhid import directory_swhid
from repo2ree_core.time_utils import parse_utc_instant
from repo2ree_protocol.command import (
    ReviewAcquireSourceArgs,
    ReviewActivationTestArgs,
    ReviewBuildRuntimeArgs,
    ReviewRunExperimentArgs,
)

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")
_REVIEW_ID = "review-one"
_RUNTIME_PATH = "runtime.tar"
_RUNTIME = b"runtime bytes\n"
_ACTIVATION = b"#!/bin/sh\ntest -f runtime.tar\n"
_ACTIVATION_VERIFY = b"#!/bin/sh\nexit 0\n"
_EXPERIMENT_NAME = "demo"
_EXPERIMENT = b"#!/bin/sh\nmkdir -p outputs && printf result > outputs/result.txt\n"
_EXPERIMENT_VERIFY = b'#!/bin/sh\ntest "$(cat outputs/result.txt)" = result\n'


def _author_ree() -> Ree:
    experiment = ExperimentDefinition(
        name=_EXPERIMENT_NAME,
        run_script_path=ReePath(experiment_run_script_path(_EXPERIMENT_NAME)),
        run_script_digest=digest_bytes(_EXPERIMENT),
        run_script_size=len(_EXPERIMENT),
        verify_script_path=ReePath(experiment_verify_script_path(_EXPERIMENT_NAME)),
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
        runtime_digest=digest_bytes(_RUNTIME),
        run_script_digest=digest_bytes(_EXPERIMENT),
        verify_script_digest=digest_bytes(_EXPERIMENT_VERIFY),
        verify_exit_code=0,
    )
    return Ree(
        subject=ReeSubject(
            definition=ReeDefinition(
                runtime=RuntimeDefinition(runtime_path=WorkspacePath(_RUNTIME_PATH)),
                test_activation=ActivationDefinition(
                    run_script_digest=digest_bytes(_ACTIVATION),
                    run_script_size=len(_ACTIVATION),
                    verify_script_path=ReePath(RESERVED_ACTIVATION_VERIFY_SCRIPT),
                    verify_script_digest=digest_bytes(_ACTIVATION_VERIFY),
                    verify_script_size=len(_ACTIVATION_VERIFY),
                ),
                experiments=(experiment,),
            ),
            receipts=ReeReceipts(experiments={_EXPERIMENT_NAME: author_experiment}),
        )
    )


def _workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, activation: bytes = _ACTIVATION) -> ReeLayout:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.write_ree(_author_ree())
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))

    review = layout.review(_REVIEW_ID)
    review.workspace.mkdir(parents=True)
    files = {
        _RUNTIME_PATH: _RUNTIME,
        RESERVED_ACTIVATION_SCRIPT: activation,
        RESERVED_ACTIVATION_VERIFY_SCRIPT: _ACTIVATION_VERIFY,
        experiment_run_script_path(_EXPERIMENT_NAME): _EXPERIMENT,
        experiment_verify_script_path(_EXPERIMENT_NAME): _EXPERIMENT_VERIFY,
    }
    for relative, contents in files.items():
        target = review.workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)

    record = new_review_record(_REVIEW_ID, at="2026-08-03T00:00:00Z")
    record = with_step(record, "source", status="completed", at="2026-08-03T00:00:01Z")
    record = with_step(record, "build", status="completed", at="2026-08-03T00:00:02Z")
    record = record.model_copy(
        update={
            "source_comparison": SourceComparison(basis="independent", verdict="identical"),
            "build_comparison": BuildComparison(basis="independent", verdict="identical"),
            "build_receipt": ReviewBuildRuntimeReceipt(
                run_id=RunId("review-build"),
                started_at=_NOW,
                finished_at=_NOW,
                duration_ms=0,
                recorded_at=_NOW,
                status="succeeded",
                runtime_path=WorkspacePath(_RUNTIME_PATH),
                produced_runtime_digest=digest_bytes(_RUNTIME),
            ),
        }
    )
    write_review_record(review, record)
    return layout


def _activate():
    return activation_test.handle_review_activation_test(
        ReviewActivationTestArgs(review_id=_REVIEW_ID),
        run_id="review-activation",
        log=lambda *_: None,
        is_canceled=lambda: False,
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
        Ree(
            subject=ReeSubject(
                definition=ReeDefinition(
                    source=SourceDefinition(origin_url=str(origin), source_type="git", requested_ref=revision)
                ),
                receipts=ReeReceipts(
                    source=AcquireSourceReceipt(
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
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))

    result = acquire_source.handle_review_acquire_source(
        ReviewAcquireSourceArgs(review_id=_REVIEW_ID, basis="independent"),
        run_id="review-source",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "identical"
    assert result.outputs["receipt"]["requested_ref"] == revision
    assert (layout.review(_REVIEW_ID).upstream / "source.txt").read_text() == "source\n"


def test_bundled_runtime_review_records_only_the_input_it_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    store.artifacts.write_bytes("runtime.tar", _RUNTIME)
    store.write_ree(
        Ree(
            subject=ReeSubject(
                definition=ReeDefinition(runtime=RuntimeDefinition(runtime_path=WorkspacePath("artifacts/runtime.tar")))
            )
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    review = layout.review(_REVIEW_ID)
    review.upstream.mkdir(parents=True)
    record = with_step(
        new_review_record(_REVIEW_ID, at="2026-08-03T00:00:00Z"),
        "source",
        status="completed",
        at="2026-08-03T00:00:01Z",
    ).model_copy(update={"source_comparison": SourceComparison(basis="bundled", verdict="identical")})
    write_review_record(review, record)

    result = build_runtime.handle_review_build_runtime(
        ReviewBuildRuntimeArgs(review_id=_REVIEW_ID, basis="bundled", prune_workspace=False),
        run_id="review-build",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert result.outputs["receipt"]["build_runtime_script_path"] is None
    assert result.outputs["receipt"]["build_runtime_script_digest"] is None
    assert result.outputs["receipt"]["produced_runtime_digest"] == digest_bytes(_RUNTIME)
    assert len(load_reviews(layout).reviews) == 1


def test_failed_activation_is_completed_review_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _workbench(tmp_path, monkeypatch, activation=b"#!/bin/sh\nexit 7\n")

    result = _activate()

    assert result.status == "succeeded"
    assert result.outputs["outcome"]["verdict"] == "failed"
    assert result.outputs["receipt"]["status"] == "failed"
    assert result.outputs["receipt"]["run_exit_code"] == 7
    record = read_review_record(layout.review(_REVIEW_ID))
    assert record is not None
    assert step_state(record, "activation").status == "completed"  # type: ignore[union-attr]


def test_experiment_uses_definition_and_author_receipt_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = _workbench(tmp_path, monkeypatch)
    assert _activate().outputs["outcome"]["verdict"] == "passed"

    result = run_experiment.handle_review_run_experiment(
        ReviewRunExperimentArgs(review_id=_REVIEW_ID, experiment_name=_EXPERIMENT_NAME),
        run_id="review-experiment",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )

    assert result.status == "succeeded"
    assert result.outputs["comparison"]["verdict"] == "reproduced"
    assert result.outputs["receipt"]["status"] == "succeeded"
    assert result.outputs["receipt"]["verify_script_digest"] == digest_bytes(_EXPERIMENT_VERIFY)
    record = read_review_record(layout.review(_REVIEW_ID))
    assert record is not None
    assert [receipt.experiment_name for receipt in record.experiment_receipts] == [_EXPERIMENT_NAME]
