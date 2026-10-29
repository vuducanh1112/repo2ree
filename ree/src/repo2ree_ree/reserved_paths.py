from __future__ import annotations

from pathlib import PurePosixPath

RESERVED_SCRIPT_DIR = "ree-scripts"

RESERVED_BUILD_SCRIPT = f"{RESERVED_SCRIPT_DIR}/build_script.sh"
RESERVED_ACTIVATION_SCRIPT = f"{RESERVED_SCRIPT_DIR}/activation.sh"
RESERVED_ACTIVATION_VERIFY_SCRIPT = f"{RESERVED_SCRIPT_DIR}/activation.verify.sh"
RESERVED_EXPERIMENT_SCRIPT_DIR = f"{RESERVED_SCRIPT_DIR}/experiments"

RESERVED_OVERLAY_SCRIPTS = (
    RESERVED_BUILD_SCRIPT,
    RESERVED_ACTIVATION_SCRIPT,
)


def experiment_slug(name: str) -> str:
    return "-".join(str(name or "").split()) or "experiment"


def experiment_run_script_path(name: str) -> str:
    return f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{experiment_slug(name)}.sh"


def experiment_verify_script_path(name: str) -> str:
    return f"{RESERVED_EXPERIMENT_SCRIPT_DIR}/{experiment_slug(name)}.verify.sh"


def is_run_script(path: str) -> bool:
    normalized = PurePosixPath(path)
    if str(normalized) in (RESERVED_BUILD_SCRIPT, RESERVED_ACTIVATION_SCRIPT):
        return True
    return (
        str(normalized.parent) == RESERVED_EXPERIMENT_SCRIPT_DIR
        and normalized.suffix == ".sh"
        and not normalized.name.endswith(".verify.sh")
    )


WORKSPACE_CONTROL_PREFIXES = (".workspace", ".upload.")
