"""Compose and run the workbench agent process."""

from __future__ import annotations

import asyncio

from repo2ree_agent.config import load_config
from repo2ree_agent.control.connection import run_agent
from repo2ree_agent.runtimes.docker import DockerRuntime
from repo2ree_agent.service import WorkbenchService
from repo2ree_protocol.log import configure_logging
from repo2ree_protocol.tracing import otlp_log_handler, setup_logs, setup_metrics, setup_tracing


def main() -> None:
    config = load_config()
    logger_provider = setup_logs("repo2ree-agent", endpoint=config.otlp_endpoint, instance_id=config.agent_id)
    configure_logging(
        structured=config.otlp_endpoint is not None,
        otlp_handler=otlp_log_handler(logger_provider) if logger_provider is not None else None,
    )
    tracer_provider = setup_tracing(
        "repo2ree-agent", endpoint=config.otlp_endpoint, console_fallback=True, instance_id=config.agent_id
    )
    meter_provider = setup_metrics("repo2ree-agent", endpoint=config.otlp_endpoint, instance_id=config.agent_id)
    runtime = DockerRuntime(config.docker.mode)
    service = WorkbenchService({runtime.runtime_name: runtime})
    try:
        asyncio.run(
            run_agent(
                config.api_ws_url,
                service,
                config.agent_id,
                docker_mode=config.docker.mode,
            )
        )
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()
