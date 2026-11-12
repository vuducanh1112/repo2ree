"""Initialize an REE and retain its first Git snapshot before reporting success."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from repo2ree_core.bundle.repository_files import prepare_reproducer
from repo2ree_core.digests import digest_file
from repo2ree_core.persistence.capture_policy import write_capture_controls
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    CapturePolicy,
    ExperimentEnvironmentDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
)
from repo2ree_ree.workbench_environment import EnvironmentBackend


@dataclass(frozen=True)
class InitializationResult:
    status: Literal["initialised", "already_initialised"]
    snapshot_id: str


def initialize_ree(
    layout: ReeLayout, *, name: str, workbench_environment: EnvironmentBackend = "container"
) -> InitializationResult:
    """Preserve existing files on retry, including after a failed first capture.

    A pre-existing REE without history gets an explicitly named existing-state
    baseline: its contents cannot be assumed to be the original initial state.
    Git failure after writing ree.json leaves that initialized state in place.
    """
    with open_history(layout) as history:
        store = ReeDirectory(layout)
        existing = store.manifest_exists()
        if not existing:
            store.ensure_dirs()
            store.ensure_reserved_overlay_scripts(workbench_environment)
            build = store.overlay.absolute(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
            activate = store.overlay.absolute(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT)
            store.write_ree(
                Ree(
                    subject=ReeSubject(
                        capture=CapturePolicy(),
                        definition=ReeDefinition(
                            name=name,
                            experiment_environment=ExperimentEnvironmentDefinition(
                                build_experiment_environment_script_digest=digest_file(build),
                                build_experiment_environment_script_size=build.stat().st_size,
                            ),
                            activate_experiment_environment=ActivateExperimentEnvironmentDefinition(
                                activate_experiment_environment_script_digest=digest_file(activate),
                                activate_experiment_environment_script_size=activate.stat().st_size,
                            ),
                        ),
                    )
                )
            )
        if not existing:
            prepare_reproducer(layout, store.read_ree())
            write_capture_controls(layout, store.read_ree())
        snapshot = history.capture_initial(existing=existing)
    return InitializationResult("already_initialised" if existing else "initialised", snapshot)
