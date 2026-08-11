from __future__ import annotations

import pytest

from repo2ree_agent.runtimes.docker.reference import DockerWorkbenchHandle, decode_reference, encode_reference
from repo2ree_protocol.agent import WorkbenchRef


def test_reference_round_trip_keeps_docker_details_private() -> None:
    handle = DockerWorkbenchHandle(
        ree_id="ree-1",
        container_name="repo2ree-wb-ree-1",
        volume_name="repo2ree-ree-ree-1",
        exec_path="/nix/store/executor/bin/repo2ree-exec",
    )

    ref = encode_reference(handle)

    assert ref.runtime == "docker"
    assert "container_name" not in ref.model_dump()
    assert decode_reference(ref) == handle


def test_reference_rejects_wrong_runtime_and_malformed_token() -> None:
    with pytest.raises(ValueError, match="cannot handle"):
        decode_reference(WorkbenchRef(runtime="slurm", token="opaque"))  # noqa: S106
    with pytest.raises(ValueError, match="invalid Docker"):
        decode_reference(WorkbenchRef(runtime="docker", token="not-json"))  # noqa: S106
