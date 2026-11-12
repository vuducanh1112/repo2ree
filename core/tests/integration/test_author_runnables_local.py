"""Local script-process coverage for author activation and experiments."""

from __future__ import annotations

from pathlib import Path

import pytest

from repo2ree_core.domain.ree.transitions import commit_receipt
from repo2ree_core.operations.handlers.author.activation_test import handle_activation_test
from repo2ree_core.operations.handlers.author.run_experiment import handle_run_experiment
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_protocol.command import RunExperimentArgs
from repo2ree_ree.digest import digest_bytes
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    ExperimentDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
)
from repo2ree_ree.primitives import OverlayPath, RunId, WorkspacePath, parse_utc_instant
from repo2ree_ree.receipt import AcquireSourceReceipt
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    experiment_run_script_path,
    experiment_verify_script_path,
)

_NOW = parse_utc_instant("2026-08-03T00:00:00Z")


def test_activation_and_experiment_scripts_commit_successful_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layout = ReeLayout(tmp_path / "ree")
    store = ReeDirectory(layout)
    store.ensure_dirs()
    # The activation enters an "environment" (a variable) and hands over to whatever it is given.
    activate = (
        b'#!/bin/sh\nset -eu\nprintf entered >> activation.out\nprintf "%s\\n" "$*" >> handed.out\n'
        b'ACTIVE=yes\nexport ACTIVE\nexec "$@"\n'
    )
    experiment_run = b'#!/bin/sh\nset -eu\nmkdir -p outputs\nprintf "result $ACTIVE" > outputs/result.txt\n'
    experiment_verify = b'#!/bin/sh\nset -eu\ntest "$(cat outputs/result.txt)" = "result yes"\n'
    name = "local experiment"
    experiment_run_path = experiment_run_script_path(name)
    experiment_verify_path = experiment_verify_script_path(name)

    store.workspace.write_bytes(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT, activate)
    store.workspace.write_bytes(experiment_run_path, experiment_run)
    store.workspace.write_bytes(experiment_verify_path, experiment_verify)
    definition = ReeDefinition(
        activate_experiment_environment=ActivateExperimentEnvironmentDefinition(
            activate_experiment_environment_script_digest=digest_bytes(activate),
            activate_experiment_environment_script_size=len(activate),
        ),
        experiments=(
            ExperimentDefinition(
                name=name,
                run_script_path=OverlayPath(experiment_run_path),
                run_script_digest=digest_bytes(experiment_run),
                run_script_size=len(experiment_run),
                verify_script_path=OverlayPath(experiment_verify_path),
                verify_script_digest=digest_bytes(experiment_verify),
                verify_script_size=len(experiment_verify),
                output_paths=(WorkspacePath("outputs/result.txt"),),
            ),
        ),
    )
    ree = Ree(subject=ReeSubject(definition=definition))
    ree = commit_receipt(
        ree,
        AcquireSourceReceipt(
            run_id=RunId("source-1"),
            started_at=_NOW,
            finished_at=_NOW,
            duration_ms=0,
            recorded_at=_NOW,
            origin_url="https://example.test/repo.git",
            source_type="git",
            snapshot_digest=digest_bytes(b"snapshot"),
        ),
    )
    store.write_ree(ree)
    monkeypatch.setattr(ReeLayout, "in_workbench", classmethod(lambda cls: layout))

    activation_result = handle_activation_test(
        run_id="activation-local",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )
    experiment_result = handle_run_experiment(
        RunExperimentArgs(experiment_name=name),
        run_id="experiment-local",
        log=lambda *args: None,
        is_canceled=lambda: False,
    )

    assert activation_result.status == "succeeded"
    assert experiment_result.status == "succeeded"
    persisted = store.read_ree().subject.receipts
    assert persisted.activation is not None
    assert persisted.activation.run_id == "activation-local"
    # The activation ran twice: alone, and around the experiment.
    assert (layout.workspace / "activation.out").read_text() == "enteredentered"
    # Alone, it hands over a command with no options: a tool it wraps (srun) would parse them as its own.
    assert (layout.workspace / "handed.out").read_text().splitlines()[0] == "true"
    experiment = persisted.experiments[name]
    assert experiment.run_id == "experiment-local"
    assert experiment.produced_output_digest is not None
    assert (layout.results_dir(name) / "outputs/result.txt").read_bytes() == b"result yes"
