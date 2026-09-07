"""Compose and run the Docker compute provider process."""

from __future__ import annotations

import asyncio

from repo2ree_protocol.allocation import WorkbenchImage
from repo2ree_protocol.build import current_build
from repo2ree_protocol.log import configure_logging
from repo2ree_protocol.tracing import otlp_log_handler, setup_logs, setup_metrics, setup_tracing
from repo2ree_provider_docker.config import load_config
from repo2ree_provider_docker.connection import run_provider
from repo2ree_provider_docker.lifecycle import DockerIsolation
from repo2ree_provider_docker.provisioner import ProvisionerService


def main() -> None:
    config = load_config()
    logger_provider = setup_logs(
        "repo2ree-provider-docker", endpoint=config.otlp_endpoint, instance_id=config.provider_id
    )
    configure_logging(
        structured=config.otlp_endpoint is not None,
        otlp_handler=otlp_log_handler(logger_provider) if logger_provider is not None else None,
    )
    tracer_provider = setup_tracing(
        "repo2ree-provider-docker",
        endpoint=config.otlp_endpoint,
        console_fallback=True,
        instance_id=config.provider_id,
    )
    meter_provider = setup_metrics(
        "repo2ree-provider-docker", endpoint=config.otlp_endpoint, instance_id=config.provider_id
    )
    isolation = DockerIsolation(
        config.docker_mode,
        workbench_api_ws_url=config.workbench_api_ws_url,
        workbench_network=config.workbench_network,
        workbench_telemetry=config.workbench_telemetry,
        workbench_otlp_endpoint=config.workbench_otlp_endpoint,
    )
    provisioner = ProvisionerService(
        isolation,
        catalog={image.ref for image in config.images},
        accepts_custom_image=config.accepts_custom_image,
    )
    public_images = tuple(
        WorkbenchImage(ref=image.ref, id=image.id, label=image.label, description=image.description)
        for image in config.images
    )
    try:
        asyncio.run(
            run_provider(
                config.api_ws_url,
                provisioner,
                config.provider_id,
                location_id=config.location_id,
                location_label=config.location_label,
                images=public_images,
                accepts_custom_image=config.accepts_custom_image,
                build=current_build("repo2ree-provider-docker"),
            )
        )
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()
        if meter_provider is not None:
            meter_provider.shutdown()
        if logger_provider is not None:
            logger_provider.shutdown()
