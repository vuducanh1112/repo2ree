"""Definitions for tests: every REE declares its four fixed scripts, so a test names only what it is about."""

from __future__ import annotations

from typing import Any

from repo2ree_authoring.templates import reserved_script_template
from repo2ree_core.persistence.directory import ReeDirectory
from repo2ree_core.persistence.layout import ReeLayout
from repo2ree_ree.digest import Digest, digest_bytes
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
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

PLACEHOLDER = Digest("sha256:" + "0" * 64)


def _default(path: str) -> tuple[Digest, int]:
    body = reserved_script_template(path).encode()
    return digest_bytes(body), len(body)


BUILD, _BUILD_SIZE = _default(RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT)
ACTIVATE, _ACTIVATE_SIZE = _default(RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT)
LAUNCH, _LAUNCH_SIZE = _default(RESERVED_LAUNCH_SCRIPT)
CHECK, _CHECK_SIZE = _default(RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT)


def fixed_declarations() -> dict[str, Any]:
    """The four declarations every REE has, each its script as every REE starts with it."""
    return {
        "experiment_environment": ExperimentEnvironmentDefinition(
            build_experiment_environment_script_digest=BUILD, build_experiment_environment_script_size=_BUILD_SIZE
        ),
        "activate_experiment_environment": ActivateExperimentEnvironmentDefinition(
            activate_experiment_environment_script_digest=ACTIVATE,
            activate_experiment_environment_script_size=_ACTIVATE_SIZE,
        ),
        "launch": LaunchDefinition(launch_script_digest=LAUNCH, launch_script_size=_LAUNCH_SIZE),
        "check_working_environment": CheckWorkingEnvironmentDefinition(
            check_working_environment_script_digest=CHECK, check_working_environment_script_size=_CHECK_SIZE
        ),
    }


def ree_definition(**fields: Any) -> ReeDefinition:
    """A definition with the fixed declarations filled in where ``fields`` does not give them."""
    return ReeDefinition(**(fixed_declarations() | fields))


def bare_ree(**fields: Any) -> Ree:
    """An REE that declares nothing beyond what every REE does."""
    return Ree(subject=ReeSubject(definition=ree_definition(**fields)))


def with_fixed_scripts(layout: ReeLayout, ree: Ree) -> Ree:
    """The REE, with each fixed script it declares as every REE starts with it written where it is not yet.

    A fixed script the test declared otherwise, or wrote itself, is left as the test has it.
    """
    store = ReeDirectory(layout)
    definition = ree.subject.definition
    declared = {
        RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT: (
            definition.experiment_environment.build_experiment_environment_script_digest,
            BUILD,
        ),
        RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT: (
            definition.activate_experiment_environment.activate_experiment_environment_script_digest,
            ACTIVATE,
        ),
        RESERVED_LAUNCH_SCRIPT: (definition.launch.launch_script_digest, LAUNCH),
        RESERVED_CHECK_WORKING_ENVIRONMENT_SCRIPT: (
            definition.check_working_environment.check_working_environment_script_digest,
            CHECK,
        ),
    }
    for path, (digest, default) in declared.items():
        if digest != default or store.overlay.is_file(path) or store.workspace.is_file(path):
            continue
        content = reserved_script_template(path)
        store.overlay.write_text(path, content)
        store.workspace.write_text(path, content)
    return ree
