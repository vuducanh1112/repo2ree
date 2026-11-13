"""Which container engines a script run for an REE can use, probed where its scripts run.

The probe is a small POSIX shell script run through the REE's script runner, so it sees what a build script
would: the same PATH, user, image, mounts and engine socket. For each engine it asks the engine itself, not
the client's presence: ``docker version`` names the server that answers, which may be Podman behind a socket,
and ``podman info`` exercises its storage and rootless setup. It writes nothing.

A probe that cannot run says so (``failed``), which inference reads as unknown, never as absence.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import get_args

from repo2ree_core.execution.runners import ProbeResult, ScriptRunner, current_runner
from repo2ree_protocol.inference import ContainerEngine, ContainerEnginesProbe, EngineObservation

PROBE_SECONDS = 20.0

PROBE_SCRIPT = r"""
for engine in docker podman; do
  path=$(command -v "$engine" 2>/dev/null) || { printf '%s\tabsent\n' "$engine"; continue; }
  case $engine in
    docker)
      out=$(docker version --format '{{.Server.Platform.Name}}|{{.Server.Version}}' 2>&1)
      status=$? ;;
    podman)
      out=$(podman info --format 'Podman Engine|{{.Version.Version}}|{{.Host.Security.Rootless}}' 2>&1)
      status=$? ;;
  esac
  first=$(printf '%s\n' "$out" | tr '\t' ' ' | head -n 1)
  if [ "$status" -eq 0 ]; then
    printf '%s\tusable\t%s\t%s\n' "$engine" "$path" "$first"
  else
    printf '%s\tunreachable\t%s\t%s\n' "$engine" "$path" "$first"
  fi
done
"""

ENGINES: tuple[ContainerEngine, ...] = get_args(ContainerEngine)


def parse(stdout: str) -> dict[ContainerEngine, EngineObservation]:
    """The engines a probe reported, by name; lines it does not recognise are ignored."""
    seen: dict[ContainerEngine, EngineObservation] = {}
    for line in stdout.splitlines():
        engine, _, rest = line.partition("\t")
        state, _, rest = rest.partition("\t")
        path, _, answer = rest.partition("\t")
        name = next((known for known in ENGINES if known == engine), None)
        if name is None:
            continue
        if state == "absent":
            seen[name] = EngineObservation(engine=name, state="absent")
        elif state == "usable":
            server, _, rest = answer.partition("|")
            version, _, rootless = rest.partition("|")
            seen[name] = EngineObservation(
                engine=name,
                state="usable",
                client_path=path or None,
                server=server or None,
                version=version or None,
                rootless={"true": True, "false": False}.get(rootless),
            )
        elif state == "unreachable":
            seen[name] = EngineObservation(engine=name, state="unreachable", client_path=path or None, detail=answer)
    return seen


def observed(result: ProbeResult, seconds: float = PROBE_SECONDS) -> ContainerEnginesProbe:
    """What a finished probe says about the engines.

    An engine it reported keeps its state. When it ran out of time partway, the engines it did not reach
    are the ones that did not answer, so they are unreachable; when it printed nothing at all, nothing is
    known.
    """
    seen = parse(result.stdout)
    if not seen:
        why = f"no answer within {seconds:.0f}s" if result.returncode is None else f"exit {result.returncode}"
        first = next(iter(result.stderr.splitlines()), "")
        detail = f"{why}: {first}" if first else why
        return ContainerEnginesProbe(status="failed", detail=detail, runner=result.runner, image=result.image)
    engines = [
        seen.get(engine)
        or EngineObservation(engine=engine, state="unreachable", detail=f"no answer within {seconds:.0f}s")
        for engine in ENGINES
    ]
    return ContainerEnginesProbe(status="probed", engines=engines, runner=result.runner, image=result.image)


class RunnerEngineProbe:
    """Probes through the REE's script runner the first time it is asked, and answers the same after."""

    def __init__(
        self,
        workspace: Path,
        runner: Callable[[], ScriptRunner] = current_runner,
        seconds: float = PROBE_SECONDS,
    ) -> None:
        self._workspace = workspace
        self._runner = runner
        self._seconds = seconds
        self._seen: ContainerEnginesProbe | None = None

    def probe(self) -> ContainerEnginesProbe:
        if self._seen is None:
            self._seen = self._probe()
        return self._seen

    def _probe(self) -> ContainerEnginesProbe:
        if not self._workspace.is_dir():
            return ContainerEnginesProbe(status="failed", detail=f"no workspace at {self._workspace} to probe from")
        try:
            result = self._runner().probe(self._workspace, ["sh", "-c", PROBE_SCRIPT], seconds=self._seconds)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
            # The runner refused (an REE that declares no image where scripts run in containers), or the
            # engine could not start the probe: where the scripts would run is unknown, so are its engines.
            return ContainerEnginesProbe(status="failed", detail=str(error))
        return observed(result, self._seconds)
