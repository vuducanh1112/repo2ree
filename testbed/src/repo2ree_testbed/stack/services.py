"""The processes of a source stack and the environment each is started with."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from repo2ree_testbed.stack.docker import first_network, own_container

type Mode = Literal["provider", "external"]
type DockerMode = Literal["dind", "host-socket"]


@dataclass(frozen=True)
class Deployment:
    tier: str
    compute_locations: int
    mode: Mode
    docker_mode: DockerMode
    state_root: Path
    exec_bundle: Path
    tools_bundle: Path


@dataclass(frozen=True)
class Service:
    label: str
    package: str
    module: str
    environment: dict[str, str]


def backend_environment(control_state: Path, token: str, coverage_file: Path, telemetry: Path | None) -> dict[str, str]:
    environment = {
        "UPLOAD_STAGING_DIR": str(control_state / "upload-staging"),
        "ALLOCATION_STORE_FILE": str(control_state / "allocations.json"),
        "REE_INDEX_FILE": str(control_state / "ree-index.json"),
        "RUN_REGISTRY_DIR": str(control_state / "runs"),
        "BEHAVIOUR_JOURNAL_DIR": str(control_state / "journal"),
        "BEHAVIOUR_FINAL_SHUTDOWN": "true",
        "EXTERNAL_WORKBENCH_TOKEN": token,
        "COVERAGE_FILE": str(coverage_file),
    }
    if telemetry is not None:
        environment["TRACE_FILE"] = str(telemetry / "api.ndjson")
    return environment


def workbench_host() -> tuple[str, str]:
    """How a bench reaches this process: (host, the Docker network it must join, or "")."""
    container = own_container()
    network = first_network(container) if container else ""
    return (container, network) if container and network else ("host.docker.internal", "")


def locations(
    deployment: Deployment, api_url: str, control_state: Path, token: str, registry_mirror: str = ""
) -> list[Service]:
    host, network = workbench_host()
    ws = "ws:" + api_url.removeprefix("http:")
    port = api_url.rsplit(":", 1)[1]
    services = []
    for index in range(1, deployment.compute_locations + 1):
        if deployment.mode == "provider":
            service = Service(
                "Docker provider",
                "repo2ree-provider-docker",
                "repo2ree_provider_docker",
                {
                    "PROVIDER_API_WS_URL": f"{ws}/provider/connect",
                    "PROVIDER_WORKBENCH_API_WS_URL": f"ws://{host}:{port}/workbench/connect",
                    "PROVIDER_WORKBENCH_DOCKER_NETWORK": network,
                    "PROVIDER_DOCKER_MODE": deployment.docker_mode,
                    "PROVIDER_WORKBENCH_REGISTRY_MIRROR": registry_mirror,
                    "PROVIDER_LOCATION_ID": f"lab-{index}",
                    "PROVIDER_LOCATION_LABEL": f"Lab {index}",
                    "PROVIDER_STATE_DIR": str(control_state / f"provider-{index}"),
                    "REPO2REE_EXEC_BUNDLE": str(deployment.exec_bundle),
                    "REPO2REE_TOOLS_BUNDLE": str(deployment.tools_bundle),
                    "REPO2REE_RESOURCE_OWNER": token,
                },
            )
        else:
            state = control_state / f"workbench-{index}"
            service = Service(
                "external workbench",
                "repo2ree-workbench",
                "repo2ree_workbench",
                {
                    "WORKBENCH_API_WS_URL": f"{ws}/workbench/connect",
                    "WORKBENCH_MODE": "external",
                    "WORKBENCH_AUTH_TOKEN": token,
                    "WORKBENCH_LOCATION_ID": f"lab-{index}",
                    "WORKBENCH_ROOT": str(state / "root"),
                    "WORKBENCH_STATE_DIR": str(state),
                    "REPO2REE_EXEC_PATH": "repo2ree-exec",
                },
            )
        services.append(service)
    return services
