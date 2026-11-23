from __future__ import annotations

import asyncio
from collections.abc import Sequence

from repo2ree_protocol.build import current_build
from repo2ree_telemetry.bootstrap import TracerProvider, otlp_log_handler, setup_logs, setup_metrics, setup_tracing
from repo2ree_telemetry.log import configure_logging
from repo2ree_telemetry.relay import setup_relayed_span_export
from repo2ree_workbench.cli_process import LocalCli
from repo2ree_workbench.config import load_config
from repo2ree_workbench.connection import SpanRelay, run_workbench
from repo2ree_workbench.journal import store_journal
from repo2ree_workbench.service import WorkbenchService
from repo2ree_workbench.tools import tool_environment


def main(argv: Sequence[str] = ()) -> None:
    config = load_config(argv) if argv else load_config()
    logger_provider = setup_logs("repo2ree-workbench", endpoint=config.otlp_endpoint, instance_id=config.workbench_id)
    configure_logging(
        structured=config.otlp_endpoint is not None,
        otlp_handler=otlp_log_handler(logger_provider) if logger_provider is not None else None,
    )
    span_relay = SpanRelay() if config.telemetry == "relay" else None
    tracer_provider: TracerProvider | None
    if span_relay is not None:
        tracer_provider = setup_relayed_span_export(
            "repo2ree-workbench", span_relay.send, instance_id=config.workbench_id
        )
    else:
        tracer_provider = setup_tracing(
            "repo2ree-workbench",
            endpoint=config.otlp_endpoint,
            console_fallback=config.telemetry == "local",
            instance_id=config.workbench_id,
        )
    meter_provider = setup_metrics("repo2ree-workbench", endpoint=config.otlp_endpoint, instance_id=config.workbench_id)
    executor = LocalCli(config.store_root, config.cli_path, environment=tool_environment(config.tools_bundle))
    machine = executor.machine()
    service = WorkbenchService(executor, store_id=config.store_id, slots=config.slots)
    try:
        with store_journal(config.store_root, config.store_id):
            service.executions.reconcile()
            asyncio.run(
                run_workbench(
                    config.api_ws_url,
                    service,
                    config.workbench_id,
                    enrollment_token=config.enrollment_token,
                    span_relay=span_relay,
                    build=current_build("repo2ree-workbench"),
                    executor_build=executor.build_info(),
                    machine=machine,
                )
            )
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()
