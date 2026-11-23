from __future__ import annotations

from typing import Any

from repo2ree_ree.digest import Digest
from repo2ree_ree.model import (
    ActivateExperimentEnvironmentDefinition,
    CheckWorkingEnvironmentDefinition,
    ExperimentEnvironmentDefinition,
    LaunchDefinition,
    Ree,
    ReeDefinition,
    ReeSubject,
)

PLACEHOLDER = Digest("sha256:" + "0" * 64)


def ree_definition(**fields: Any) -> ReeDefinition:
    fixed = {
        "experiment_environment": ExperimentEnvironmentDefinition(
            build_experiment_environment_script_digest=PLACEHOLDER, build_experiment_environment_script_size=1
        ),
        "activate_experiment_environment": ActivateExperimentEnvironmentDefinition(
            activate_experiment_environment_script_digest=PLACEHOLDER, activate_experiment_environment_script_size=1
        ),
        "launch": LaunchDefinition(launch_script_digest=PLACEHOLDER, launch_script_size=1),
        "check_working_environment": CheckWorkingEnvironmentDefinition(
            check_working_environment_script_digest=PLACEHOLDER, check_working_environment_script_size=1
        ),
    }
    return ReeDefinition(**(fixed | fields))


def bare_ree(**fields: Any) -> Ree:
    return Ree(subject=ReeSubject(definition=ree_definition(**fields)))
