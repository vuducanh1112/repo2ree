import json
from pathlib import Path
from typing import Any

import pytest
from scripts.gates import assurance_gate, receipts, tiers
from scripts.gates.receipts import ReceiptError, TierReceipt

TREE = "t" * 40
SHOWCASE = tiers.Tier("showcase", "test-showcase", {"compute_locations": 2}, judged=False, skips=False)
INTEGRATION = tiers.Tier("integration", "test-backend-integration", {}, judged=False, skips=True)


def record(**changes: Any) -> dict[str, Any]:
    document = {
        "tier": "showcase",
        "tree": TREE,
        "selected": [],
        "parameters": {"compute_locations": 2, "mode": "provider"},
        "platform": "linux/amd64",
        "machine": "vm",
        "tests": [{"name": "a", "outcome": "passed"}, {"name": "b", "outcome": "passed"}],
    }
    return {**document, **changes}


def test_the_policy_names_a_place_for_every_tier_a_gate_needs() -> None:
    policy = tiers.load_policy()
    assert policy.gates["publish-gate"].tiers["showcase"] == "here"
    assert policy.gates["showcase-gate"].tiers == {"showcase": "each"}
    assert policy.tiers["showcase"].judged


def test_a_gate_naming_an_unknown_place_is_refused(tmp_path: Path) -> None:
    policy = tmp_path / "policy.toml"
    policy.write_text('[tiers.a]\nrecipe = "a"\n[gates.g]\ntiers = { a = "somewhere" }\n')
    with pytest.raises(ValueError, match="unknown tier or place"):
        tiers.load_policy(policy)


def test_a_whole_clean_run_on_the_policys_deployment_qualifies(tmp_path: Path) -> None:
    assert tiers.run_problems(tmp_path, record(), SHOWCASE, TREE) == []


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"tree": ""}, "dirty tree"),
        ({"tree": "o" * 40}, "not HEAD's"),
        ({"selected": ["test_x"]}, "ran only the tests matching test_x"),
        ({"parameters": {"compute_locations": 1}}, "compute_locations=1"),
        ({"tests": [{"name": "a", "outcome": "failed"}]}, "a did not pass"),
        ({"tests": [{"name": "a", "outcome": "skipped"}]}, "a was skipped"),
        ({"tests": []}, "records no test"),
        ({"tier": "integration"}, "not showcase"),
    ],
)
def test_a_run_that_falls_short_names_why(tmp_path: Path, changes: dict[str, Any], problem: str) -> None:
    problems = tiers.run_problems(tmp_path, record(**changes), SHOWCASE, TREE)
    assert any(problem in found for found in problems), problems


def test_a_tier_whose_policy_allows_skips_certifies_a_run_with_one(tmp_path: Path) -> None:
    tests = [{"name": "a", "outcome": "passed"}, {"name": "needs-docker", "outcome": "skipped"}]
    assert tiers.run_problems(tmp_path, record(tier="integration", tests=tests), INTEGRATION, TREE) == []


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checkout at TREE whose receipts land under tmp_path."""
    monkeypatch.setattr(tiers, "ROOT", tmp_path)
    monkeypatch.setattr(assurance_gate, "clean_head", lambda: ("r" * 40, TREE, []))
    monkeypatch.setattr(receipts, "write", lambda path, receipt: _write(path, receipt))
    return tmp_path


def _write(path: Path, receipt: receipts.Receipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt.to_document()))


def test_a_certified_run_leaves_a_receipt_for_its_tree_and_platform(repository: Path) -> None:
    run = repository / "test-artifacts/e2e/showcase-1"
    run.mkdir(parents=True)
    (run / "run.json").write_text(json.dumps(record()))

    receipt = tiers.certify(SHOWCASE, run)

    path = receipts.tier_path(repository, "showcase", TREE, "linux/amd64")
    assert receipts.read(TierReceipt, path) == receipt
    assert (receipt.tests, receipt.skipped, receipt.machine, receipt.run) == (
        2,
        0,
        "vm",
        "test-artifacts/e2e/showcase-1",
    )


def test_a_run_that_does_not_qualify_leaves_no_receipt(repository: Path) -> None:
    run = repository / "showcase-1"
    run.mkdir()
    (run / "run.json").write_text(json.dumps(record(tree="")))

    with pytest.raises(ReceiptError, match="dirty tree"):
        tiers.certify(SHOWCASE, run)
    assert not (repository / receipts.DIRECTORY).exists()


def test_a_gate_is_met_by_a_receipt_per_platform_it_asks_for(repository: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tiers, "platform", lambda: "linux/arm64")
    gate = tiers.GatePolicy("g", (), {"showcase": "each", "integration": "any", "gui-screenshots": "here"})
    for tier, where in (
        ("showcase", "linux/amd64"),
        ("integration", "linux/amd64"),
        ("gui-screenshots", "linux/arm64"),
    ):
        receipt = TierReceipt(
            revision="r",
            tree=TREE,
            written=receipts.now(),
            tier=tier,
            platform=where,
            machine="m",
            run="x",
            tests=1,
            skipped=0,
            judged=False,
        )
        _write(receipts.tier_path(repository, tier, TREE, where), receipt)

    unmet = tiers.unmet(gate, ["linux/amd64", "linux/arm64"], TREE)

    assert unmet == [tiers.Need("showcase", "linux/arm64")]
    assert tiers.unmet(gate, ["linux/amd64"], TREE) == []
    assert tiers.unmet(gate, ["linux/amd64"], "o" * 40) == tiers.needs(gate, ["linux/amd64"])
