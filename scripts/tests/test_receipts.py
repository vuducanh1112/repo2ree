import subprocess
from pathlib import Path

import pytest
from scripts.gates import receipts
from scripts.gates.receipts import AssuranceGateReceipt, CommitGateReceipt, Coverage, ReceiptError

ROOT = Path(__file__).parents[2]


def commit_receipt() -> CommitGateReceipt:
    return CommitGateReceipt(revision=None, tree="tree-1", written=receipts.now())


def test_a_receipt_round_trips_under_receipts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0))
    path = receipts.path(tmp_path, "commit-gate")
    written = commit_receipt()
    receipts.write(path, written)

    assert path == tmp_path / ".receipts/commit-gate.json"
    assert receipts.read(CommitGateReceipt, path) == written
    assert receipts.read(CommitGateReceipt, tmp_path / "absent.json") is None


def test_a_receipt_git_would_track_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1))
    path = receipts.path(tmp_path, "commit-gate")

    with pytest.raises(ReceiptError, match="git does not ignore it"):
        receipts.write(path, commit_receipt())
    assert not path.exists()


def test_another_gates_receipt_is_not_read_as_this_one(tmp_path: Path) -> None:
    path = tmp_path / "assurance-gate.json"
    coverage = Coverage(declared=1, reached=1, unreached=())
    assurance = AssuranceGateReceipt(
        revision="r", tree="t", written=receipts.now(), runs=(), tests=(), coverage=coverage
    )
    path.write_text(assurance.model_dump_json())

    assert receipts.read(AssuranceGateReceipt, path) == assurance
    with pytest.raises(ReceiptError, match="not a receipt this gate wrote"):
        receipts.read(CommitGateReceipt, path)


def test_the_receipts_directory_is_ignored_except_its_rules() -> None:
    ignored = subprocess.run(["git", "check-ignore", "-q", ".receipts/commit-gate.json"], cwd=ROOT, check=False)
    rules = subprocess.run(["git", "check-ignore", "-q", ".receipts/.gitignore"], cwd=ROOT, check=False)
    assert (ignored.returncode, rules.returncode) == (0, 1)
