from __future__ import annotations

from pathlib import PurePosixPath

RESERVED_SCRIPT_DIR = "ree-scripts"

RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT = f"{RESERVED_SCRIPT_DIR}/build_experiment_environment.sh"
RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT = f"{RESERVED_SCRIPT_DIR}/activate_experiment_environment.sh"
RESERVED_EXPERIMENT_SCRIPT_DIR = f"{RESERVED_SCRIPT_DIR}/experiments"

RESERVED_OVERLAY_SCRIPTS = (
    RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
    RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
)


def experiment_slug(name: str) -> str:
    return "-".join(str(name or "").split()) or "experiment"


def experiment_run_script_path(name: str) -> str:
    return f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{experiment_slug(name)}.sh"


def experiment_verify_script_path(name: str) -> str:
    return f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{experiment_slug(name)}.verify.sh"


def is_overlay_path(path: str) -> bool:
    """Whether ``path`` may be in an REE's overlay: one of its scripts, and nothing else."""
    normalized = PurePosixPath(path)
    if str(normalized) in (
        RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
        RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    ):
        return True
    name = normalized.name
    return (
        str(normalized.parent) == RESERVED_EXPERIMENT_SCRIPT_DIR
        and name.endswith(".sh")
        and name not in (".sh", ".verify.sh")
    )


def is_run_script(path: str) -> bool:
    normalized = PurePosixPath(path)
    if str(normalized) in (
        RESERVED_BUILD_EXPERIMENT_ENVIRONMENT_SCRIPT,
        RESERVED_ACTIVATE_EXPERIMENT_ENVIRONMENT_SCRIPT,
    ):
        return True
    return (
        str(normalized.parent) == RESERVED_EXPERIMENT_SCRIPT_DIR
        and normalized.suffix == ".sh"
        and not normalized.name.endswith(".verify.sh")
    )


WORKSPACE_CONTROL_PREFIXES = (".workspace", ".upload.")
