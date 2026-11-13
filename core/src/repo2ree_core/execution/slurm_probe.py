"""Whether a script run for an REE can launch Slurm job steps, probed where its scripts run.

The probe is a small POSIX shell script run through the REE's script runner, so it sees what a launch script
would: the same PATH, user and cluster configuration. It asks the controller itself (``sinfo``), not only
whether ``srun`` is on PATH, and reports its partitions with their time limits. It writes nothing.

A probe that cannot run says so (``failed``), which inference reads as unknown, never as absence.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from repo2ree_core.execution.runners import ProbeResult, ScriptRunner, current_runner
from repo2ree_protocol.inference import SlurmPartition, SlurmProbe

PROBE_SECONDS = 20.0

PROBE_SCRIPT = r"""
path=$(command -v srun 2>/dev/null) || { printf 'absent\n'; exit 0; }
version=$(srun --version 2>&1 | head -n 1 | tr '\t' ' ')
if partitions=$(sinfo --noheader --format '%P|%l' 2>&1); then
  printf 'usable\t%s\t%s\n' "$path" "$version"
  printf '%s\n' "$partitions" | while IFS= read -r line; do printf 'partition\t%s\n' "$line"; done
else
  printf 'unreachable\t%s\t%s\n' "$path" "$(printf '%s\n' "$partitions" | head -n 1 | tr '\t' ' ')"
fi
"""


def _partition(line: str) -> SlurmPartition | None:
    name, _, limit = line.partition("|")
    name = name.strip()
    if not name:
        return None
    default = name.endswith("*")
    return SlurmPartition(name=name.rstrip("*"), default=default, time_limit=limit.strip() or None)


def observed(result: ProbeResult, seconds: float = PROBE_SECONDS) -> SlurmProbe:
    """What a finished probe says about Slurm; one that printed nothing it recognises knows nothing."""
    runner, image = result.runner, result.image
    lines = result.stdout.splitlines()
    head = lines[0].split("\t") if lines else []
    state = head[0] if head else ""
    if state == "absent":
        return SlurmProbe(status="probed", state="absent", runner=runner, image=image)
    if state in ("usable", "unreachable") and len(head) >= 2:
        detail = head[2] if len(head) > 2 else ""
        if state == "unreachable":
            return SlurmProbe(
                status="probed", state="unreachable", srun_path=head[1], detail=detail, runner=runner, image=image
            )
        partitions = [
            found
            for line in lines[1:]
            if line.startswith("partition\t") and (found := _partition(line.removeprefix("partition\t")))
        ]
        return SlurmProbe(
            status="probed",
            state="usable",
            srun_path=head[1],
            version=detail or None,
            partitions=partitions,
            runner=runner,
            image=image,
        )
    why = f"no answer within {seconds:.0f}s" if result.returncode is None else f"exit {result.returncode}"
    first = next(iter(result.stderr.splitlines()), "")
    return SlurmProbe(status="failed", detail=f"{why}: {first}" if first else why, runner=runner, image=image)


class RunnerSlurmProbe:
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
        self._seen: SlurmProbe | None = None

    def probe(self) -> SlurmProbe:
        if self._seen is None:
            self._seen = self._probe()
        return self._seen

    def _probe(self) -> SlurmProbe:
        if not self._workspace.is_dir():
            return SlurmProbe(status="failed", detail=f"no workspace at {self._workspace} to probe from")
        try:
            result = self._runner().probe(self._workspace, ["sh", "-c", PROBE_SCRIPT], seconds=self._seconds)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
            return SlurmProbe(status="failed", detail=str(error))
        return observed(result, self._seconds)
