"""Initialize an REE and retain its first Git snapshot before reporting success."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from repo2ree_core.bundle.repository_files import prepare_reproducer
from repo2ree_core.digests import digest_file
from repo2ree_core.domain.ree.model import (
    BuildRuntimeDefinition,
    CapturePolicy,
    Ree,
    ReeDefinition,
    ReeSubject,
    TestActivationDefinition,
)
from repo2ree_core.persistence.capture_policy import write_capture_controls
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.history import open_history
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_core.reserved_paths import RESERVED_ACTIVATION_SCRIPT, RESERVED_BUILD_SCRIPT


@dataclass(frozen=True)
class InitializationResult:
    status: Literal["initialised", "already_initialised"]
    snapshot_id: str


def initialize_ree(layout: ReeLayout, *, name: str) -> InitializationResult:
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
            store.ensure_reserved_overlay_scripts()
            build = store.overlay.absolute(RESERVED_BUILD_SCRIPT)
            activation = store.overlay.absolute(RESERVED_ACTIVATION_SCRIPT)
            store.write_ree(
                Ree(
                    subject=ReeSubject(
                        capture=CapturePolicy(),
                        definition=ReeDefinition(
                            name=name,
                            build_runtime=BuildRuntimeDefinition(
                                build_runtime_script_digest=digest_file(build),
                                build_runtime_script_size=build.stat().st_size,
                            ),
                            test_activation=TestActivationDefinition(
                                run_script_digest=digest_file(activation),
                                run_script_size=activation.stat().st_size,
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
