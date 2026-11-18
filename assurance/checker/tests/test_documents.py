"""Each commit of the REE document judged alone: its receipts' standings by their basis, and its digests."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_spec import documents

from repo2ree_assurance_checker.check import check
from repo2ree_assurance_checker.check.documents import (
    canonical,
    canonical_digest,
    check_documents,
    paths_digest,
    standings,
    witness,
)
from repo2ree_assurance_checker.evidence import CommittedFile, Evidence, Snapshot, Source
from repo2ree_assurance_checker.files import ROOT, load_spec
from repo2ree_assurance_checker.sources import load_evidence
from repo2ree_assurance_checker.spec import AggregateSpec, DocumentRules

FIXTURES = ROOT / "contracts" / "ree" / "fixtures"
GIT = os.environ.get("REPO2REE_TOOL_GIT") or shutil.which("git")
REE = "ree-1"


def ree() -> AggregateSpec:
    return load_spec().aggregates["Ree"]


def committed(files: dict[str, str]) -> dict[str, CommittedFile]:
    return {
        path: CommittedFile(
            digest=f"sha256:{hashlib.sha256(content.encode()).hexdigest()}",
            size=len(content.encode()),
            storage="git",
        )
        for path, content in files.items()
    }


def digest_of(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"


# ---------------------------------------------------------------------------- the format's digests


def test_the_digest_of_declared_outputs_is_the_one_the_format_pins() -> None:
    for case in json.loads((FIXTURES / "digests.json").read_text())["paths"]:
        files = committed({f"results/one/{path}": content for path, content in case["files"].items()})
        assert paths_digest(files, "results/one/", case["paths"]) == case["digest"], case["name"]


def test_the_canonical_encoding_is_the_one_the_format_pins() -> None:
    fixture = json.loads((FIXTURES / "canonical.json").read_text())
    for case in fixture["digests"]:
        assert canonical(case["value"]) == case["canonical"], case["name"]
        assert digest_of(case["canonical"]) == case["digest"], case["name"]
    for case in fixture["refused"]:
        with pytest.raises(ValueError):
            canonical(case["value"])


def test_every_sealed_fixture_s_seal_is_the_canonical_digest_of_its_subject() -> None:
    for path in sorted((FIXTURES / "sealed").glob("*.json")):
        document = json.loads(path.read_text())
        assert (
            canonical_digest("org.repo2ree.ree-subject", "subject", document["subject"])
            == document["seal"]["ree_digest"]
        ), path.name


# ---------------------------------------------------------------------------- standings by the basis


SCRIPTS = {
    "overlay/ree-scripts/build_experiment_environment.sh": "build\n",
    "overlay/ree-scripts/activate_experiment_environment.sh": "activate\n",
    "overlay/ree-scripts/launch.sh": 'exec "$@"\n',
    "overlay/ree-scripts/check_working_environment.sh": "true\n",
    "overlay/ree-scripts/experiments/one.sh": "run\n",
    "overlay/ree-scripts/experiments/one.verify.sh": "verify\n",
}


def authored(scripts: dict[str, str] | None = None) -> tuple[dict[str, Any], dict[str, CommittedFile]]:
    """A draft whose every receipt is current: the source acquired, built, activated, one experiment run."""
    scripts = scripts or SCRIPTS
    files = committed(scripts)

    def script(name: str) -> str:
        return files[f"overlay/ree-scripts/{name}"].digest

    environment, snapshot = "sha256:" + "e" * 64, "sha256:" + "s" * 64
    subject = {
        "definition": {
            "name": "demo",
            "source": {"source_type": "tarball"},
            "experiment_environment": {
                "artifact_path": "runtime.tar",
                "build_experiment_environment_script_path": "ree-scripts/build_experiment_environment.sh",
                "build_experiment_environment_script_digest": script("build_experiment_environment.sh"),
            },
            "activate_experiment_environment": {
                "activate_experiment_environment_script_path": "ree-scripts/activate_experiment_environment.sh",
                "activate_experiment_environment_script_digest": script("activate_experiment_environment.sh"),
            },
            "launch": {"launch_script_path": "ree-scripts/launch.sh", "launch_script_digest": script("launch.sh")},
            "check_working_environment": {
                "check_working_environment_script_path": "ree-scripts/check_working_environment.sh",
                "check_working_environment_script_digest": script("check_working_environment.sh"),
            },
            "experiments": [
                {
                    "name": "one",
                    "run_script_path": "ree-scripts/experiments/one.sh",
                    "run_script_digest": script("experiments/one.sh"),
                    "verify_script_path": "ree-scripts/experiments/one.verify.sh",
                    "verify_script_digest": script("experiments/one.verify.sh"),
                    "output_paths": ["result.txt"],
                }
            ],
        },
        "receipts": {
            "acquire_source": {"source_type": "tarball", "snapshot_digest": snapshot},
            "evaluate_reproducibility": {
                "snapshot_digest": snapshot,
                "overlay_digest": "sha256:" + "o" * 64,
                "report_digest": "sha256:" + "r" * 64,
            },
            "check_working_environment": {
                "check_working_environment_script_digest": script("check_working_environment.sh"),
                "launch_script_digest": script("launch.sh"),
            },
            "build_experiment_environment": {
                "snapshot_digest": snapshot,
                "build_experiment_environment_script_digest": script("build_experiment_environment.sh"),
                "artifact_path": "runtime.tar",
                "launch_script_digest": script("launch.sh"),
                "produced_artifact_digest": environment,
            },
            "activate_experiment_environment": {
                "snapshot_digest": snapshot,
                "experiment_environment_digest": environment,
                "activate_experiment_environment_script_digest": script("activate_experiment_environment.sh"),
                "launch_script_digest": script("launch.sh"),
            },
            "experiments": {
                "one": {
                    "experiment_name": "one",
                    "snapshot_digest": snapshot,
                    "experiment_environment_digest": environment,
                    "activate_experiment_environment_script_digest": script("activate_experiment_environment.sh"),
                    "run_script_digest": script("experiments/one.sh"),
                    "verify_script_digest": script("experiments/one.verify.sh"),
                    "launch_script_digest": script("launch.sh"),
                }
            },
        },
    }
    return {"subject": subject}, files


def snapshot(
    document: dict[str, Any],
    files: dict[str, CommittedFile],
    position: int = 1300,
    *,
    cause: str = "operation",
    operation: str | None = "run_experiment",
    recorded: dict[str, str] | None = None,
) -> Snapshot:
    return Snapshot(
        source="git:ree",
        position=position,
        subject="Ree",
        partition=REE,
        locator=f"git:ree@c{position // 1000}",
        cause=cause,  # type: ignore[arg-type]
        operation=operation,
        attempt_id=f"a{position // 1000}",
        document=document,
        files=files,
        recorded=recorded,
    )


def test_every_receipt_is_current_while_its_basis_agrees() -> None:
    document, files = authored()
    assert standings(ree(), snapshot(document, files)) == {
        "acquire_source": "current",
        "evaluate_reproducibility": "current",
        "observe_hardware": "not_applicable",
        "check_working_environment": "current",
        "build_experiment_environment": "current",
        "generate_sbom": "missing",
        "cross_check_sbom": "missing",
        "activate_experiment_environment": "current",
        "run_experiment:one": "current",
    }


def test_rewriting_a_script_stales_what_rests_on_it_but_never_the_evaluation_of_the_source() -> None:
    document, _files = authored()
    rewritten = committed(SCRIPTS | {"overlay/ree-scripts/launch.sh": 'srun "$@"\n'})
    document["subject"]["definition"]["launch"]["launch_script_digest"] = rewritten[
        "overlay/ree-scripts/launch.sh"
    ].digest
    found = standings(ree(), snapshot(document, rewritten))
    assert {step for step, standing in found.items() if standing == "stale"} == {
        "check_working_environment",
        "build_experiment_environment",
        "activate_experiment_environment",
        "run_experiment:one",
    }
    assert found["acquire_source"] == found["evaluate_reproducibility"] == "current"


def test_a_new_environment_stales_everything_run_in_the_old_one() -> None:
    document, files = authored()
    document["subject"]["receipts"]["build_experiment_environment"]["produced_artifact_digest"] = "sha256:" + "f" * 64
    found = standings(ree(), snapshot(document, files))
    assert found["build_experiment_environment"] == "current"
    assert found["activate_experiment_environment"] == "stale"
    assert found["run_experiment:one"] == "stale"


def test_a_receipt_whose_subject_is_no_longer_declared_is_orphaned_and_an_undeclared_item_is_gone() -> None:
    document, files = authored()
    document["subject"]["definition"]["experiment_environment"].pop("artifact_path")
    document["subject"]["definition"]["experiments"] = []
    del document["subject"]["receipts"]["experiments"]["one"]
    found = standings(ree(), snapshot(document, files))
    assert found["build_experiment_environment"] == "stale"
    assert "run_experiment:one" not in found


def test_an_observation_stands_without_a_declaration() -> None:
    document, files = authored()
    document["subject"]["receipts"]["observe_hardware"] = {"observer_version": "1"}
    assert standings(ree(), snapshot(document, files))["observe_hardware"] == "current"


def test_receipts_standings_are_witnessed_once_as_they_change() -> None:
    document, files = authored()
    later = copy.deepcopy(document)
    later["subject"]["receipts"]["build_experiment_environment"]["produced_artifact_digest"] = "sha256:" + "f" * 64
    evidence = Evidence(
        sources=(git_source(),),
        events=(),
        snapshots=(
            snapshot(document, files, 1300, cause="created", operation=None),
            snapshot(later, files, 2300, operation="build_experiment_environment"),
        ),
    )
    witnessed = witness(load_spec(), evidence)
    moved = [(e.facts["step"], e.source_state, e.target_state, e.facts["cause"]) for e in witnessed.events]
    assert ("run_experiment:one", None, "current", "baseline") in moved
    assert ("run_experiment:one", "current", "stale", "operation") in moved
    assert ("acquire_source", "current", "current", "operation") not in moved
    assert witness(load_spec(), witnessed) is witnessed


def git_source() -> Source:
    return Source(
        id="git:ree",
        kind="git",
        process="core",
        rank=0,
        hosts=frozenset({"core"}),
        complete=True,
        closed=False,
        partitions=frozenset({REE}),
    )


def test_snapshots_are_never_written_out_with_the_evidence() -> None:
    document, files = authored()
    evidence = Evidence(sources=(git_source(),), events=(), snapshots=(snapshot(document, files),))
    assert "snapshots" not in json.loads(evidence.model_dump_json())


# ---------------------------------------------------------------------------- the document rules


def findings(*snapshots: Snapshot) -> dict[str, list[str]]:
    evidence = Evidence(sources=(git_source(),), events=(), snapshots=snapshots)
    return {
        result.rule.removeprefix("document:"): [f"{f.subject.split()[-1]}: {f.reason}" for f in result.findings]
        for result in check_documents(load_spec(), evidence)
    }


def test_what_core_recorded_of_a_receipt_is_held_to_its_basis() -> None:
    document, files = authored()
    agreed = standings(ree(), snapshot(document, files))
    assert not findings(snapshot(document, files, recorded=agreed))["standings-are-the-receipts-basis"]
    claimed = agreed | {"evaluate_reproducibility": "stale"}
    claimed.pop("check_working_environment")
    assert findings(snapshot(document, files, recorded=claimed))["standings-are-the-receipts-basis"] == [
        "check_working_environment: core recorded no standing; its basis gives current",
        "evaluate_reproducibility: core recorded stale, but its basis gives current",
    ]


def test_a_script_is_the_file_its_digest_names() -> None:
    document, files = authored()
    assert not findings(snapshot(document, files))["scripts-are-their-digests"]
    tampered = files | committed({"overlay/ree-scripts/launch.sh": "rm -rf /\n"})
    assert findings(snapshot(document, tampered))["scripts-are-their-digests"] == [
        (
            f"definition.launch.launch_script_digest: records {files['overlay/ree-scripts/launch.sh'].digest}, "
            f"but overlay/ree-scripts/launch.sh is {tampered['overlay/ree-scripts/launch.sh'].digest}"
        )
    ]
    missing = {path: file for path, file in files.items() if not path.endswith("one.verify.sh")}
    assert findings(snapshot(document, missing))["scripts-are-their-digests"] == [
        (
            "definition.experiments[one].verify_script_digest: records the digest of "
            "overlay/ree-scripts/experiments/one.verify.sh, which the commit does not hold"
        )
    ]


def test_evidence_a_commit_does_not_carry_is_not_judged_and_evidence_it_carries_is() -> None:
    document, files = authored()
    evidence = Evidence(sources=(git_source(),), events=(), snapshots=(snapshot(document, files),))
    carried = next(
        r for r in check_documents(load_spec(), evidence) if r.rule == "document:carried-evidence-is-its-digests"
    )
    assert carried.triggered == 0
    wrong = files | committed({"snapshot.tar.gz": "another source"})
    assert findings(snapshot(document, wrong))["carried-evidence-is-its-digests"] == [
        (
            f"receipts.acquire_source.snapshot_digest: records {'sha256:' + 's' * 64}, "
            f"but snapshot.tar.gz is {wrong['snapshot.tar.gz'].digest}"
        )
    ]


def sealed(document: dict[str, Any], files: dict[str, CommittedFile]) -> dict[str, Any]:
    subject = copy.deepcopy(document["subject"])
    subject["contents"] = {
        "entries": [{"path": path, "digest": file.digest, "size": file.size} for path, file in sorted(files.items())]
    }
    return {
        "subject": subject,
        "seal": {"ree_digest": canonical_digest("org.repo2ree.ree-subject", "subject", subject)},
    }


def test_a_seal_is_the_digest_of_the_subject_and_its_contents_are_the_commit() -> None:
    document, files = authored()
    files = files | committed({"results/one/result.txt": "42\n"})
    document["subject"]["receipts"]["experiments"]["one"]["produced_output_digest"] = paths_digest(
        files, "results/one/", ["result.txt"]
    )
    good = sealed(document, files)
    clean = findings(snapshot(good, files | committed({"ree.json": "{}"})))
    for rule in ("the-seal-is-the-subject", "contents-are-the-bundle", "sealed-results-are-what-ran"):
        assert not clean[rule], rule
    edited = copy.deepcopy(good)
    edited["subject"]["definition"]["name"] = "renamed"
    assert findings(snapshot(edited, files))["the-seal-is-the-subject"][0].startswith("seal.ree_digest: records")
    extra = files | committed({"notes.txt": "unlisted"})
    assert findings(snapshot(good, extra))["contents-are-the-bundle"] == [
        "notes.txt: is held by the commit, but the inventory does not list it"
    ]
    other = files | committed({"results/one/result.txt": "41\n"})
    assert findings(snapshot(good, other))["sealed-results-are-what-ran"][0].startswith(
        "receipts.experiments[one].produced_output_digest: records"
    )


def test_a_draft_is_held_to_no_seal() -> None:
    document, files = authored()
    evidence = Evidence(sources=(git_source(),), events=(), snapshots=(snapshot(document, files),))
    for result in check_documents(load_spec(), evidence):
        if result.rule in {"document:the-seal-is-the-subject", "document:contents-are-the-bundle"}:
            assert result.triggered == 0


# ---------------------------------------------------------------------------- the specification of them


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ({"id": "x", "pattern": "standing", "summary": "", "kind": "file"}, "names nothing more"),
        ({"id": "x", "pattern": "digest", "summary": ""}, "says what kind"),
        ({"id": "x", "pattern": "digest", "summary": "", "kind": "inventory"}, "names the inventory"),
        (
            {"id": "x", "pattern": "digest", "summary": "", "kind": "paths", "pairs": [{"digest": "a", "path": "b"}]},
            "takes PathsPairs",
        ),
        (
            {"id": "x", "pattern": "digest", "summary": "", "kind": "file", "pairs": [{"digest": "a"}]},
            "by a field or by a path",
        ),
    ],
)
def test_incoherent_document_rules_are_rejected(rule: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        DocumentRules.model_validate({"aggregate": "Ree", "rule": [rule]})


def test_document_rules_belong_to_an_aggregate_whose_receipts_all_stand_on_a_basis() -> None:
    docs = documents()
    docs.rules[0]["aggregate"] = "Nothing"
    with pytest.raises(ValidationError, match="which is no aggregate"):
        docs.parse()
    docs = documents()
    docs.aggregates[0]["receipts"]["generate_sbom"].pop("basis")
    docs.aggregates[0]["receipts"]["generate_sbom"]["made_from"] = ["build_experiment_environment"]
    with pytest.raises(ValidationError, match="have no basis to stand on"):
        docs.parse()


# ---------------------------------------------------------------------------- a sealed REE, read from Git


@pytest.mark.skipif(GIT is None, reason="needs git")
def test_the_sealed_example_holds_every_digest_it_records(tmp_path: Path) -> None:
    assert GIT is not None
    with zipfile.ZipFile(ROOT / "examples" / "rees" / "ree-hello-world.zip") as archive:
        archive.extractall(tmp_path)
    result = check(load_spec(), load_evidence(repositories=[tmp_path / "ree"], git_executable=GIT))
    rules = {rule.rule: rule for rule in result.rules}
    # What core recorded of the standings is the product's: the example is held to that where it is authored.
    for name in (
        "scripts-are-their-digests",
        "carried-evidence-is-its-digests",
        "the-seal-is-the-subject",
        "contents-are-the-bundle",
        "sealed-results-are-what-ran",
    ):
        assert rules[f"document:{name}"].verdict == "passed", name
        assert rules[f"document:{name}"].triggered, name
    assert rules["document:the-seal-is-the-subject"].triggered == 1
    assert rules["machine:Receipt"].verdict == "passed"
