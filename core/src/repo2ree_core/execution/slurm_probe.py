from __future__ import annotations

import subprocess
from pathlib import Path

from repo2ree_core.execution.working_environment import ProbeResult, probe
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
    lines = result.stdout.splitlines()
    head = lines[0].split("\t") if lines else []
    state = head[0] if head else ""
    if state == "absent":
        return SlurmProbe(status="probed", state="absent")
    if state in ("usable", "unreachable") and len(head) >= 2:
        detail = head[2] if len(head) > 2 else ""
        if state == "unreachable":
            return SlurmProbe(status="probed", state="unreachable", srun_path=head[1], detail=detail)
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
        )
    why = f"no answer within {seconds:.0f}s" if result.returncode is None else f"exit {result.returncode}"
    first = next(iter(result.stderr.splitlines()), "")
    return SlurmProbe(status="failed", detail=f"{why}: {first}" if first else why)


class RunnerSlurmProbe:
    def __init__(
        self,
        workspace: Path,
        seconds: float = PROBE_SECONDS,
    ) -> None:
        self._workspace = workspace
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
            result = probe(self._workspace, ["sh", "-c", PROBE_SCRIPT], seconds=self._seconds)
        except (
            RuntimeError,
            OSError,
            ValueError,
            subprocess.SubprocessError,
        ) as error:
            return SlurmProbe(status="failed", detail=str(error))
        return observed(result, self._seconds)
