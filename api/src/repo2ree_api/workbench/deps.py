"""Module-level workbench manager singleton for use across API routes."""

from __future__ import annotations

from repo2ree_api.settings import service_settings
from repo2ree_protocol.tracing import build_span_sink
from repo2ree_supervisor import WorkbenchManager
from repo2ree_supervisor.registry import WorkbenchRegistry

_registry = WorkbenchRegistry(service_settings.WORKBENCH_REGISTRY_FILE)
workbench_manager = WorkbenchManager(
    registry=_registry,
    workbench_image=service_settings.WORKBENCH_IMAGE,
    span_sink=build_span_sink(service_settings.OTLP_ENDPOINT, console_fallback=True),
    workbench_docker_mode=service_settings.WORKBENCH_DOCKER_MODE,
)
