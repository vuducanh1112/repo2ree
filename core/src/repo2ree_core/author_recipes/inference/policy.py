from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InferencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_experiment_environment_kinds: set[str] = Field(default_factory=lambda: {"docker_archive", "venv_archive"})
    conda_base_image: str | None = None
    python_base_images: dict[str, str] = Field(default_factory=dict)
    node_base_images: dict[str, str] = Field(default_factory=dict)
    default_platform: str | None = None


def default_policy() -> InferencePolicy:
    return InferencePolicy()
