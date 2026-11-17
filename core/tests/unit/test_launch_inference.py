"""A launch is proposed where Slurm answers, for confirmation, and nothing is inferred where it does not."""

from __future__ import annotations

from pathlib import Path

import pytest
from ree_definitions import ree_definition

from repo2ree_core.author_recipes.inference import TargetInferenceResult, infer_scripts
from repo2ree_core.author_recipes.inference.machine import MachineInputs
from repo2ree_core.author_recipes.inference.renderers.slurm_launch import limit_minutes
from repo2ree_core.execution.slurm_probe import observed
from repo2ree_core.execution.working_environment import ProbeResult
from repo2ree_protocol.command import ScriptTargetSelectorArg
from repo2ree_protocol.inference import SlurmObservation, SlurmPartition, SlurmProbe
from repo2ree_ree.reserved_paths import RESERVED_LAUNCH_SCRIPT

LAUNCH = ScriptTargetSelectorArg(kind="launch")
RULE = "slurm-job-step-launch"


class FixedSlurm:
    def __init__(self, probe: SlurmProbe) -> None:
        self._probe = probe

    def probe(self) -> SlurmProbe:
        return self._probe


def _usable(*partitions: SlurmPartition) -> SlurmProbe:
    return SlurmProbe(status="probed", state="usable", srun_path="/usr/bin/srun", partitions=list(partitions))


def _infer(root: Path, probe: SlurmProbe) -> TargetInferenceResult:
    (root / "main.py").write_text("print(1)\n")
    report = infer_scripts(
        root, [LAUNCH], definition=ree_definition(name="Demo"), machine=MachineInputs(slurm=FixedSlurm(probe))
    )
    (result,) = report.results
    return result


def _body(result: TargetInferenceResult) -> str:
    body = result.candidates[0].body
    assert body is not None
    return body


def test_where_slurm_answers_a_launch_is_proposed_for_confirmation(tmp_path: Path) -> None:
    result = _infer(tmp_path, _usable(SlurmPartition(name="batch", default=True, time_limit="2-00:00:00")))
    assert result.target.path == RESERVED_LAUNCH_SCRIPT
    assert result.status == "needs_input"
    assert [candidate.inference_rule for candidate in result.candidates] == [RULE]
    assert "launch_needs_unset" in {warning.code for warning in result.warnings}
    body = _body(result)
    assert "exec srun --nodes=1 --ntasks=1" in body
    assert '${REE_LAUNCH_OPTIONS:-} "$@"' in body
    assert "TIME_LIMIT=00:30:00" in body
    (step,) = [step for step in result.decision.steps if step.node_id == "slurm"]
    assert isinstance(step.observed, SlurmObservation)
    assert step.observed.probe.partitions[0].name == "batch"


def test_a_launch_keeps_within_the_default_partitions_time_limit(tmp_path: Path) -> None:
    body = _body(_infer(tmp_path, _usable(SlurmPartition(name="short", default=True, time_limit="10:00"))))
    assert "TIME_LIMIT=00:10:00" in body


@pytest.mark.parametrize(
    "probe",
    [
        SlurmProbe(status="probed", state="absent"),
        SlurmProbe(status="probed", state="unreachable", srun_path="/usr/bin/srun", detail="unable to contact"),
    ],
)
def test_where_slurm_cannot_launch_nothing_is_inferred_and_scripts_run_directly(
    tmp_path: Path, probe: SlurmProbe
) -> None:
    result = _infer(tmp_path, probe)
    assert result.status == "not_inferred"
    assert result.candidates == []
    assert "slurm_unavailable" in {warning.code for warning in result.warnings}


def test_a_probe_that_could_not_run_proposes_the_launch_rather_than_ruling_it_out(tmp_path: Path) -> None:
    result = _infer(tmp_path, SlurmProbe(status="failed", detail="exit 127"))
    assert result.status == "needs_input"
    assert "slurm_not_probed" in {warning.code for warning in result.warnings}


@pytest.mark.parametrize(
    ("limit", "minutes"),
    [
        ("30", 30),
        ("30:00", 30),
        ("1:30:00", 90),
        ("1-00", 1440),
        ("1-02:30", 1590),
        ("2-00:00:00", 2880),
        ("infinite", None),
        (None, None),
    ],
)
def test_a_slurm_time_limit_is_read_in_minutes(limit: str | None, minutes: int | None) -> None:
    assert limit_minutes(limit) == minutes


def _result(stdout: str, returncode: int | None = 0, stderr: str = "") -> ProbeResult:
    return ProbeResult(returncode=returncode, stdout=stdout, stderr=stderr)


def test_the_probe_reads_the_controller_and_its_partitions() -> None:
    probe = observed(
        _result("usable\t/usr/bin/srun\tslurm 23.11.4\npartition\tbatch*|1-00:00:00\npartition\tgpu|infinite\n")
    )
    assert probe.state == "usable"
    assert probe.version == "slurm 23.11.4"
    assert probe.partitions == [
        SlurmPartition(name="batch", default=True, time_limit="1-00:00:00"),
        SlurmPartition(name="gpu", default=False, time_limit="infinite"),
    ]


def test_the_probe_tells_absence_from_a_controller_that_does_not_answer_from_knowing_nothing() -> None:
    assert observed(_result("absent\n")).state == "absent"
    unreachable = observed(_result("unreachable\t/usr/bin/srun\tunable to contact slurm controller\n"))
    assert unreachable.state == "unreachable"
    assert unreachable.detail == "unable to contact slurm controller"
    nothing = observed(_result("", returncode=None, stderr="timed out"))
    assert nothing.status == "failed"
    assert nothing.state is None
