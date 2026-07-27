"""Reviewer-side activation: what it probes, what it inherits, and what it refuses.

The step's whole job is a boolean, so most of what is worth pinning here is the
boundary around it: which failures are the runtime's (a verdict) and which are
the attempt's (a step failure), and that a pass never claims more than the
evidence it stands on.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from repo2ree_core.digests import digest_file_if_exists
from repo2ree_core.domain.experiment import Activation
from repo2ree_core.domain.ree_intent import ReeIntent
from repo2ree_core.domain.ree_session import ReeSession
from repo2ree_core.evidence.receipts.models import BuildRuntimeReceipt
from repo2ree_core.evidence.review.models import (
    BuildComparison,
    EvidenceBasis,
    ReviewRecord,
    SourceComparison,
    new_review_record,
    step_state,
    with_step,
)
from repo2ree_core.evidence.review.store import load_reviews, write_review_record
from repo2ree_core.operations.handlers.review import activation_test as handler
from repo2ree_core.ree.layout import ReeLayout, ReviewLayout
from repo2ree_core.ree.store import ReeStore
from repo2ree_core.ree.workspace.model import WorkspaceMetadata
from repo2ree_core.reserved_paths import RESERVED_ACTIVATION_SCRIPT
from repo2ree_protocol.command import ReviewActivationTestArgs

RUNTIME_PATH = "runtime.tar"
REVIEW_ID = "review-one"

_ACTIVATION_PASSES = "#!/bin/sh\nset -eu\ntest -f runtime.tar\n"
_ACTIVATION_FAILS = "#!/bin/sh\nexit 7\n"
_VERIFY_SCRIPT = ".ree/scripts/activation.verify.sh"


def _author_ree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    activation: Activation | None = None,
) -> ReeLayout:
    layout = ReeLayout(root=tmp_path / "ree")
    store = ReeStore(layout)
    store.ensure_dirs()
    store.write_metadata(
        WorkspaceMetadata(
            ree_id="ree-review",
            name="review",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            ree_intent=ReeIntent(
                name="review",
                runtime=RUNTIME_PATH,
                activation=activation or Activation(),
            ),
            ree_session=ReeSession(),
        )
    )
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))
    return layout


def _certified_attempt(
    layout: ReeLayout,
    *,
    activation_script: str | None = _ACTIVATION_PASSES,
    verify_script: str | None = None,
    runtime_contents: str = "runtime bytes\n",
    runtime_path: str = RUNTIME_PATH,
    certified_digest: str | None = None,
    build_status: str = "completed",
    source_basis: EvidenceBasis = "independent",
    build_basis: EvidenceBasis = "independent",
) -> ReviewLayout:
    """An attempt whose build already ran: a workspace with a runtime in it.

    Built by hand rather than by driving the build handler, so each test can
    disturb exactly one thing about the state activation depends on.
    """
    review = layout.review(REVIEW_ID)
    review.workspace.mkdir(parents=True, exist_ok=True)
    runtime = review.workspace / runtime_path
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(runtime_contents, encoding="utf-8")

    scripts = (
        (RESERVED_ACTIVATION_SCRIPT, activation_script),
        (_VERIFY_SCRIPT, verify_script),
    )
    for path, body in scripts:
        if body is None:
            continue
        script = review.workspace / path
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(body, encoding="utf-8")

    record = with_step(
        new_review_record(REVIEW_ID, at="2026-07-24T10:00:00Z"),
        "source",
        status="completed",
        at="2026-07-24T10:00:01Z",
    )
    record = with_step(record, "build", status=build_status, at="2026-07-24T10:00:02Z")  # type: ignore[arg-type]
    record = record.model_copy(
        update={
            "source_comparison": SourceComparison(basis=source_basis, verdict="identical"),
            "build_comparison": BuildComparison(basis=build_basis, verdict="equivalent"),
            "build_receipt": BuildRuntimeReceipt(
                run_id="review-build",
                started_at="2026-07-24T10:00:01Z",
                finished_at="2026-07-24T10:00:02Z",
                duration_ms=1000,
                recorded_at="2026-07-24T10:00:02Z",
                status="succeeded",
                runtime_path=runtime_path,
                produced_runtime_digest=(
                    certified_digest if certified_digest is not None else digest_file_if_exists(runtime)
                ),
            ),
        }
    )
    write_review_record(review, record)
    return review


def _activate(review_id: str = REVIEW_ID) -> Any:
    return handler.handle_review_activation_test(
        ReviewActivationTestArgs(review_id=review_id),
        run_id="review-activation-run",
        log=lambda *_: None,
        is_canceled=lambda: False,
    )


def _record(layout: ReeLayout) -> ReviewRecord:
    return load_reviews(layout).reviews[0]


# ================================================
# The probe itself
# ================================================


def test_a_runtime_that_comes_up_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout)

    result = _activate()

    assert result.status == "succeeded"
    outcome = result.outputs["outcome"]
    assert outcome["verdict"] == "passed"
    assert outcome["policy"] == "activation-probe"
    assert step_state(_record(layout), "activation").status == "completed"  # type: ignore[union-attr]


def test_a_runtime_that_does_not_come_up_completes_the_step_with_a_failed_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The review worked. Recording this as a step failure would say it did not,
    and would drag the whole attempt into ``failed`` alongside it."""
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout, activation_script=_ACTIVATION_FAILS)

    result = _activate()

    assert result.status == "succeeded"
    assert result.outputs["outcome"]["verdict"] == "failed"
    record = _record(layout)
    assert step_state(record, "activation").status == "completed"  # type: ignore[union-attr]
    assert record.status == "completed"
    assert record.failure is None


def test_a_failed_probe_says_which_half_rejected_the_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ "It came up and verify rejected it" and "it never came up" both read as
    a failure and call for entirely different work."""
    layout = _author_ree(
        tmp_path,
        monkeypatch,
        activation=Activation(verify_script=_VERIFY_SCRIPT),
    )
    _certified_attempt(layout, verify_script="#!/bin/sh\nexit 4\n")

    outcome = _activate().outputs["outcome"]

    assert outcome["verdict"] == "failed"
    assert outcome["run_exit_code"] == 0
    assert outcome["verify_exit_code"] == 4


# ================================================
# What the pass is worth, and what it is about
# ================================================


def test_a_bundled_step_anywhere_in_the_chain_weakens_the_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runtime came out of the bundle, so the probe says that artifact is
    inhabitable — never that the origin and recipe still produce one that is."""
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout, source_basis="independent", build_basis="bundled")

    assert _activate().outputs["outcome"]["basis"] == "bundled"


def test_an_independent_chain_earns_the_stronger_basis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout)

    assert _activate().outputs["outcome"]["basis"] == "independent"


def test_the_probe_is_bound_to_the_runtime_the_build_certified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A runtime replaced since the build is refused rather than probed.

    Otherwise a pass would stand over bytes no recorded step ever certified —
    the reviewer-side form of the binding the author scorecard makes when it
    only counts activation against the runtime that was actually built.
    """
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout, certified_digest="sha256:" + "f" * 64)

    result = _activate()

    assert result.status == "failed"
    assert result.failure is not None and "not the one this attempt certified" in result.failure.message
    assert _record(layout).activation_outcome is None


def test_the_recorded_digest_is_the_artifact_actually_probed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    review = _certified_attempt(layout)

    outcome = _activate().outputs["outcome"]

    assert outcome["runtime_digest"] == digest_file_if_exists(review.workspace / RUNTIME_PATH)


def test_a_runtime_a_loaded_bundle_declares_under_artifacts_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Packaging remapped the declared path; the build staged it where the
    recipe expects it. Activation has to look in the same place the build did."""
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout, runtime_path=RUNTIME_PATH)
    # Re-declare the runtime the way a loaded bundle does, leaving the artifact
    # where the build left it.
    review = layout.review(REVIEW_ID)
    record = _record(layout)
    assert record.build_receipt is not None
    write_review_record(
        review,
        record.model_copy(
            update={
                "build_receipt": record.build_receipt.model_copy(update={"runtime_path": f"artifacts/{RUNTIME_PATH}"})
            }
        ),
    )

    assert _activate().outputs["outcome"]["verdict"] == "passed"


# ================================================
# Refusals: statements about the attempt, not the runtime
# ================================================


def test_activating_before_the_build_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout, build_status="failed")

    result = _activate()

    assert result.status == "failed"
    record = _record(layout)
    assert step_state(record, "activation").status == "failed"  # type: ignore[union-attr]
    assert record.activation_outcome is None


def test_a_reclaimed_workspace_is_refused_with_the_way_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pruning is a supported choice at build time, so this is a reviewer's own
    doing and the message has to say how to undo it."""
    layout = _author_ree(tmp_path, monkeypatch)
    review = _certified_attempt(layout)
    shutil.rmtree(review.workspace)

    result = _activate()

    assert result.status == "failed"
    assert result.failure is not None and "re-run the build review" in result.failure.message


def test_an_activation_script_that_is_not_there_is_refused_not_reported_as_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing was probed, so there is nothing to say about the runtime.

    Left to run, a missing script exits nonzero like any other and would be
    recorded as "the runtime would not come up" — a verdict about a runtime the
    step never touched.
    """
    layout = _author_ree(tmp_path, monkeypatch)
    _certified_attempt(layout, activation_script=None)

    result = _activate()

    assert result.status == "failed"
    assert result.failure is not None and "not there" in result.failure.message
    assert _record(layout).activation_outcome is None


def test_an_unknown_attempt_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _author_ree(tmp_path, monkeypatch)

    result = _activate("review-nonexistent")

    assert result.status == "failed"
    assert result.failure is not None and "review-nonexistent" in result.failure.message


# ================================================
# Isolation
# ================================================


def test_the_probe_never_writes_to_author_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    layout = _author_ree(tmp_path, monkeypatch)
    review = _certified_attempt(layout)

    assert _activate().status == "succeeded"

    # Reviewer evidence lands in the attempt...
    assert review.operation_receipt("activation_test").is_file()
    assert review.comparison("activation").is_file()
    # ...and the author's selected receipts never learn of this run, nor does
    # their workspace, which the probe ran entirely beside.
    assert not (layout.author_receipts / "activation_test.json").exists()
    assert list(layout.workspace.iterdir()) == []
