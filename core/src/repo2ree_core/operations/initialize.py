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
    CheckWorkingEnvironmentDefinition,
    ExperimentEnvironmentDefinition,
    LaunchDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
)
from repo2ree_ree.reserved_paths import (
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT,
    RESERVED_LAUNCH_SCRIPT,
)


@dataclass(frozen=True)
class InitializationResult:
    status: Literal["initialised", "already_initialised"]
    snapshot_id: str


def initialize_ree(layout: ReeLayout, *, name: str) -> InitializationResult:
    with open_history(layout) as history:
        store = ReeDirectory(layout)
        existing = store.manifest_exists()
        if not existing:
            store.ensure_dirs()
            store.ensure_reserved_overlay_scripts()
            build = store.overlay.absolute(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
            activate = store.overlay.absolute(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT)
            check = store.overlay.absolute(RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT)
            launch = store.overlay.absolute(RESERVED_LAUNCH_SCRIPT)
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
                            check_working_environment=CheckWorkingEnvironmentDefinition(
                                check_working_environment_script_digest=digest_file(check),
                                check_working_environment_script_size=check.stat().st_size,
                            ),
                            launch=LaunchDefinition(
                                launch_script_digest=digest_file(launch),
                                launch_script_size=launch.stat().st_size,
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
