"""Route workbench operations to the runtime named by a spec or reference."""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from repo2ree_agent.runtimes.base import WorkbenchRuntime
from repo2ree_protocol.agent import AgentFrame, WorkbenchRef, WorkbenchSpec


class WorkbenchService:
    """The runtime-neutral compute-side workbench service."""

    def __init__(self, runtimes: Mapping[str, WorkbenchRuntime]):
        self._runtimes = dict(runtimes)

    def _runtime(self, name: str) -> WorkbenchRuntime:
        try:
            return self._runtimes[name]
        except KeyError as exc:
            raise ValueError(f"unsupported workbench runtime {name!r}") from exc

    def provision(self, ree_id: str, spec: WorkbenchSpec) -> Iterator[AgentFrame]:
        return self._runtime(spec.runtime).provision(ree_id, spec)

    def reprovision(self, ref: WorkbenchRef, spec: WorkbenchSpec) -> Iterator[AgentFrame]:
        if ref.runtime != spec.runtime:
            raise ValueError(f"cannot reprovision {ref.runtime!r} workbench with {spec.runtime!r} spec")
        return self._runtime(ref.runtime).reprovision(ref, spec)

    def remove(self, ref: WorkbenchRef) -> None:
        self._runtime(ref.runtime).remove(ref)

    def is_running(self, ref: WorkbenchRef) -> bool:
        return self._runtime(ref.runtime).is_running(ref)

    def exec_action(self, ref: WorkbenchRef, cmd_json: str, run_id: str, env: dict[str, str]) -> Iterator[AgentFrame]:
        return self._runtime(ref.runtime).exec_action(ref, cmd_json, run_id, env)

    def exec_simple(self, ref: WorkbenchRef, argv: list[str], timeout: int = 60) -> None:
        self._runtime(ref.runtime).exec_simple(ref, argv, timeout)

    def exec_query_stream(self, ref: WorkbenchRef, argv: list[str], timeout: int = 30) -> Iterator[bytes]:
        return self._runtime(ref.runtime).exec_query_stream(ref, argv, timeout)

    def cancel_run(self, ref: WorkbenchRef, run_id: str) -> None:
        self._runtime(ref.runtime).cancel_run(ref, run_id)

    def copy_in(self, ref: WorkbenchRef, source_path: str, workbench_path: str) -> None:
        self._runtime(ref.runtime).copy_in(ref, source_path, workbench_path)
