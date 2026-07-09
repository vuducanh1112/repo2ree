from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from repo2ree_core.path_safety import validate_relative_path
from repo2ree_core.reserved_paths import RESERVED_ACTIVATION_SCRIPT

# Experiment names are used as a path segment when running an experiment
# (".../experiments/{name}:run"), so they must stay free of characters that
# break URL routing — chiefly "/" (and the "." / ".." path segments).
EXPERIMENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9 ._-]+$")


def validate_runnable_script_path(value: Any) -> str:
    """Normalize and validate a workspace-relative run-script path.

    Empty is allowed (an in-progress draft may not have authored its script
    yet); a non-empty path must be workspace-relative.
    """
    text = str(value or "").strip()
    if text == "":
        return ""
    validate_relative_path(text)
    return text


class ResourceEstimates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: str = ""
    memory: str = ""
    gpu: str = ""
    storage: str = ""
    network: str = ""


class Runnable(BaseModel):
    """The executable contract shared by experiments and activation.

    Something that owns a *run script* — a workspace-relative shell script that
    fully defines how it executes (e.g. its own ``docker run …``) — and an
    optional *verify script* that checks the run's results afterwards: it runs
    from the workspace root with the captured run evidence in its environment
    (see ``experiment/run.py``) and its exit code is the verdict (0 = pass).
    ``output_paths`` declares the workspace files the run (re)writes — a pure
    declaration used for drift exclusion and manifest disclosure, with no
    matcher semantics. Activation and experiments differ in identity and role,
    not in how they execute.
    """

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    run_script: str = ""
    verify_script: str = ""
    output_paths: list[str] = Field(default_factory=list)
    runtime_estimate: str = ""
    resource_estimates: ResourceEstimates = Field(default_factory=ResourceEstimates)

    @field_validator("run_script", "verify_script", mode="before")
    @classmethod
    def _validate_script(cls, value: Any) -> str:
        return validate_runnable_script_path(value)

    @field_validator("output_paths", mode="before")
    @classmethod
    def _validate_output_paths(cls, value: Any) -> list[str]:
        if value is None:
            return []
        paths: list[str] = []
        for entry in value:
            text = str(entry or "").strip()
            if text == "":
                continue
            validate_relative_path(text)
            paths.append(text)
        return paths


class Experiment(Runnable):
    """A named experiment attached to a REE draft. Zero or more per REE.

    A successful run always captures the experiment's declared ``output_paths``
    into the produced-results store (``results/<name>/``) for local provenance.
    Whether those baselines are packaged into the sealed bundle is a seal-time
    choice (``results_included``), not per-experiment authoring state — so there
    is no flag here.
    """

    name: str = ""

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if value == "":  # in-progress drafts may not have named the experiment yet
            return value
        if value in {".", ".."} or not EXPERIMENT_NAME_PATTERN.match(value):
            raise ValueError("experiment name may only contain letters, digits, spaces, '.', '_' and '-'")
        return value


class Activation(Runnable):
    """The REE's required activation — a singleton sibling of experiments.

    Activation proves the built runtime is inhabitable by running its own
    script. There is exactly one per REE, so it is unnamed. Its run script
    defaults to the reserved activation path.
    """

    run_script: str = RESERVED_ACTIVATION_SCRIPT
