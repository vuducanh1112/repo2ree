"""Module-level workbench manager singleton for use across API routes."""

from __future__ import annotations

from repo2ree_api.settings import service_settings
from repo2ree_supervisor import WorkbenchManager
from repo2ree_supervisor.registry import WorkbenchRegistry

_registry = WorkbenchRegistry(service_settings.WORKBENCH_REGISTRY_FILE)
workbench_manager = WorkbenchManager(
    registry=_registry,
    workbench_image=service_settings.WORKBENCH_IMAGE,
)
