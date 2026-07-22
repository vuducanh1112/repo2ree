"""Deployment policy for script inference.

Supported runtime strategies are a *deployment* fact, not repository detection.
Phase 1's build strategies both work from the repository's own declared
technology — a repository Dockerfile drives ``docker build``; a requirements.txt
drives a ``pip``/venv build — so neither consults a policy-supplied base image,
and the default policy is intentionally minimal.

The base-image maps remain on the model as latent deployment config for future
strategies that genuinely synthesize a runtime substrate; nothing in Phase 1
reads them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class InferencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_runtime_kinds: set[str] = Field(default_factory=lambda: {"docker_archive", "venv_archive"})
    conda_base_image: str | None = None
    python_base_images: dict[str, str] = Field(default_factory=dict)
    node_base_images: dict[str, str] = Field(default_factory=dict)
    default_platform: str | None = None


def default_policy() -> InferencePolicy:
    """The built-in policy. Phase 1 strategies need no configured base images."""
    return InferencePolicy()
