"""Compose and run the workbench service process."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from repo2ree_protocol.log import configure_logging
from repo2ree_protocol.tracing import otlp_log_handler, setup_logs, setup_metrics, setup_tracing
from repo2ree_workbench.capabilities import observe_capabilities
from repo2ree_workbench.config import load_config
from repo2ree_workbench.connection import run_workbench
from repo2ree_workbench.executor_process import LocalExecutor
from repo2ree_workbench.service import WorkbenchService


def main(argv: Sequence[str] = ()) -> None:
    config = load_config(argv) if argv else load_config()
    logger_provider = setup_logs("repo2ree-workbench", endpoint=config.otlp_endpoint, instance_id=config.workbench_id)
    configure_logging(
        structured=config.otlp_endpoint is not None,
        otlp_handler=otlp_log_handler(logger_provider) if logger_provider is not None else None,
    )
    tracer_provider = setup_tracing(
        "repo2ree-workbench", endpoint=config.otlp_endpoint, console_fallback=True, instance_id=config.workbench_id
    )
    meter_provider = setup_metrics("repo2ree-workbench", endpoint=config.otlp_endpoint, instance_id=config.workbench_id)
    service = WorkbenchService(LocalExecutor(config.root, config.exec_path), bound=config.mode == "managed")
    capabilities = observe_capabilities(config.root, config.exec_path, config.substrate)
    try:
        asyncio.run(
            run_workbench(
                config.api_ws_url,
                service,
                config.workbench_id,
                mode=config.mode,
                allocation_id=config.allocation_id,
                enrollment_token=config.enrollment_token,
                substrate=config.substrate,
                capabilities=capabilities,
            )
        )
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()
