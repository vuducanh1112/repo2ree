from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from repo2ree_core.author_recipes.inference.naming import ree_name_slug

DOCKER_EXPERIMENT_ENVIRONMENT_ARTIFACT_SUFFIX = ".repo2ree/artifacts/runtime.tar"
VENV_EXPERIMENT_ENVIRONMENT_ARTIFACT_SUFFIX = ".repo2ree/artifacts/runtime-venv.tar.gz"


def sh_quote(value: str) -> str:
    return shlex.quote(value)


def sh_comment(value: str) -> str:
    return " ".join(value.splitlines()) if value else value


def experiment_environment_artifact_path(project_root: str, suffix: str) -> str:
    if project_root == ".":
        return suffix
    return str(PurePosixPath(project_root) / suffix)


def build_experiment_environment_artifact_path(
    declared_experiment_environment_path: str | None,
    project_root: str,
    default_suffix: str,
) -> str:
    declared = (declared_experiment_environment_path or "").strip()
    return declared or experiment_environment_artifact_path(project_root, default_suffix)


def experiment_environment_image_ref(ree_name: str) -> str:
    return f"ree-runtime:{ree_name_slug(ree_name)}"


def podman_image_ref(ree_name: str) -> str:
    return f"localhost/{experiment_environment_image_ref(ree_name)}"
