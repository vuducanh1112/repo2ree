"""Concurrent access to the durable workbench registry."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from repo2ree_protocol.agent import DockerWorkbenchSpec, WorkbenchRef
from repo2ree_supervisor.registry import WorkbenchEntry, WorkbenchRegistry


def _entry(ree_id: str) -> WorkbenchEntry:
    return WorkbenchEntry(
        ree_id=ree_id,
        ref=WorkbenchRef(runtime="docker", token=f"workbench-{ree_id}"),
        spec=DockerWorkbenchSpec(base_image="image:test"),
        agent_id="agent-1",
    )


def _slow_reads(monkeypatch: pytest.MonkeyPatch, registry: WorkbenchRegistry) -> None:
    """Widen the read-before-write race without reaching inside the lock."""
    real_read = registry._read_unlocked

    def slow_read() -> dict[str, dict[str, object]]:
        data = real_read()
        time.sleep(0.05)
        return data

    monkeypatch.setattr(registry, "_read_unlocked", slow_read)


def test_concurrent_registrations_do_not_lose_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = WorkbenchRegistry(tmp_path / "registry.json")
    _slow_reads(monkeypatch, registry)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(registry.register, _entry("ree-a")),
            pool.submit(registry.register, _entry("ree-b")),
        ]
        for future in futures:
            future.result(timeout=2)

    assert {entry.ree_id for entry in registry.list_all()} == {"ree-a", "ree-b"}


def test_concurrent_register_and_unregister_do_not_resurrect_removed_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = WorkbenchRegistry(tmp_path / "registry.json")
    registry.register(_entry("ree-old"))
    _slow_reads(monkeypatch, registry)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(registry.unregister, "ree-old"),
            pool.submit(registry.register, _entry("ree-new")),
        ]
        for future in futures:
            future.result(timeout=2)

    assert {entry.ree_id for entry in registry.list_all()} == {"ree-new"}


def test_registry_reads_legacy_docker_record_as_opaque_reference(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "ree-old": {
                    "container_name": "repo2ree-wb-ree-old",
                    "volume_name": "repo2ree-ree-ree-old",
                    "image": "ubuntu:24.04",
                    "agent_id": "agent-1",
                    "exec_path": "repo2ree-exec",
                }
            }
        )
    )

    entry = WorkbenchRegistry(path).lookup("ree-old")

    assert entry is not None
    assert entry.ref.runtime == "docker"
    assert entry.spec == DockerWorkbenchSpec(base_image="ubuntu:24.04")
