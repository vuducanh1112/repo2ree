from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repo2ree_testbed.stack.docker import first_network, own_container
from repo2ree_testbed.stack.environments import Environment


@dataclass(frozen=True)
class Deployment:
    tier: str
    compute_locations: int
    state_root: Path
    cli_bundle: Path
    tools_bundle: Path
    environment: Environment | None = None
    control_plane: bool = True
    sigstore: Path | None = None
    machines: int = 1


@dataclass(frozen=True)
class Service:
    label: str
    package: str
    module: str
    environment: dict[str, str]
    arguments: tuple[str, ...] = ()


def backend_environment(control_state: Path, token: str, coverage_file: Path, telemetry: Path | None) -> dict[str, str]:
    environment = {
        "UPLOAD_STAGING_DIR": str(control_state / "upload-staging"),
        "CONTROL_STATE_DIR": str(control_state),
        "REE_INDEX_FILE": str(control_state / "ree-index.json"),
        "RUN_REGISTRY_DIR": str(control_state / "runs"),
        "BEHAVIOUR_JOURNAL_DIR": str(control_state / "journal"),
        "BEHAVIOUR_FINAL_SHUTDOWN": "true",
        "COVERAGE_FILE": str(coverage_file),
    }
    if telemetry is not None:
        environment["TRACE_FILE"] = str(telemetry / "api.ndjson")
    return environment


def workbench_host() -> tuple[str, str]:
    container = own_container()
    network = first_network(container) if container else ""
    return (container, network) if container and network else ("host.docker.internal", "")


def store_id(index: int) -> str:
    return f"lab-{index}"


def locations(
    deployment: Deployment, api_url: str, control_state: Path, token: str, store_tokens: dict[int, str]
) -> list[Service]:
    ws = "ws:" + api_url.removeprefix("http:")
    services = []
    for index in range(1, deployment.compute_locations + 1):
        state = control_state / f"workbench-{index}"
        service = Service(
            "store workbench",
            "repo2ree-workbench",
            "repo2ree_workbench",
            {
                "WORKBENCH_API_WS_URL": f"{ws}/workbench/connect",
                "WORKBENCH_AUTH_TOKEN": store_tokens.get(index, ""),
                "WORKBENCH_STORE": f"{store_id(index)}={state / 'store'}",
                "WORKBENCH_SLOTS": "2",
                "WORKBENCH_TOOLS_BUNDLE": str(deployment.tools_bundle),
                "WORKBENCH_STATE_DIR": str(state),
                "REPO2REE_CLI_PATH": "ree",
            },
            (),
        )
        services.append(service)
    return services
