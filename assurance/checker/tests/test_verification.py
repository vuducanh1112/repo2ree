"""The verification artifact carries everything a view needs, so views never verify again."""

from __future__ import annotations

from pathlib import Path

from test_check import REE, Recorder, complete_command, git, journal

from repo2ree_assurance_checker.check import check, judge_occurrences, replay
from repo2ree_assurance_checker.cli import main
from repo2ree_assurance_checker.evidence import Evidence
from repo2ree_assurance_checker.files import load_spec
from repo2ree_assurance_checker.verification import ARTIFACT, Verification, VerifiedModel, read_verification, verify

SPEC = load_spec()


def evidence() -> Evidence:
    recorder = Recorder()
    complete_command(recorder)
    return Evidence(sources=(journal(), git(REE)), events=tuple(recorder.events))


def test_the_artifact_reads_back_as_the_model_it_verified() -> None:
    judged = evidence()
    verification = Verification.model_validate_json(verify(SPEC, judged).model_dump_json())
    model, _, _ = replay(SPEC, judged)
    verified = VerifiedModel.of(verification)

    assert verification.result == check(SPEC, judged)
    assert list(verification.judgements) == judge_occurrences(model)
    for entity, by_key in model.instances.items():
        for key, instance in by_key.items():
            read = verified.instances[entity][key]
            assert (read.partition, read.current) == (instance.partition, instance.current)
            assert [(r.source_state, r.state, r.event) for r in read.reached] == [
                (item.source_state, item.state, item.event) for item in instance.reached
            ]
    exchange = verified.exchanges["dispatch"]["a1"]
    assert exchange.request == model.exchanges["dispatch"]["a1"].request
    assert exchange.outcome == model.exchanges["dispatch"]["a1"].outcome


def test_the_check_command_writes_the_artifact_beside_its_reports(tmp_path: Path) -> None:
    journals = tmp_path / "journal"
    journals.mkdir()
    assert main(["check", "--journal", str(journals), "-o", str(tmp_path / "out")]) == 2  # Nothing triggered.
    written = read_verification(tmp_path / "out" / ARTIFACT)
    assert written.result.verdict == "inconclusive"
    assert written.dossier is None
