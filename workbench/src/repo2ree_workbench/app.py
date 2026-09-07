"""Compose and run the workbench service process."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from repo2ree_protocol.build import current_build
from repo2ree_protocol.log import configure_logging
from repo2ree_protocol.tracing import (
    TracerProvider,
    otlp_log_handler,
    setup_logs,
    setup_metrics,
    setup_relayed_span_export,
    setup_tracing,
)
from repo2ree_workbench.config import load_config
from repo2ree_workbench.connection import SpanRelay, run_workbench
from repo2ree_workbench.executor_process import LocalExecutor
from repo2ree_workbench.service import WorkbenchService


def main(argv: Sequence[str] = ()) -> None:
    config = load_config(argv) if argv else load_config()
    logger_provider = setup_logs("repo2ree-workbench", endpoint=config.otlp_endpoint, instance_id=config.workbench_id)
    configure_logging(
        structured=config.otlp_endpoint is not None,
        otlp_handler=otlp_log_handler(logger_provider) if logger_provider is not None else None,
    )
    # Spans go over the control-plane socket when there is no collector this
    # bench can reach — see WorkbenchConfig.telemetry for how that is decided.
    # Logs and metrics stay direct-export and are simply a no-op without an
    # endpoint; relaying those is a separate change.
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
    executor = LocalExecutor(config.root, config.exec_path)
    service = WorkbenchService(executor)
    try:
        asyncio.run(
            run_workbench(
                config.api_ws_url,
                service,
                config.workbench_id,
                mode=config.mode,
                allocation_id=config.allocation_id,
                enrollment_token=config.enrollment_token,
                location_id=config.location_id,
                image=config.image,
                span_relay=span_relay,
                build=current_build("repo2ree-workbench"),
                executor_build=executor.build_info(),
            )
        )
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()
