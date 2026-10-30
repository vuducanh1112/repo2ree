import json
from pathlib import Path

import pytest

from repo2ree_repoview.overview import receipt
from repo2ree_repoview.repository import Head, Provenance


def head(tree: str) -> Head:
    provenance = Provenance(revision="r" * 40, tree=tree, dirty=False, working_tree_sha256=None, generated="now")
    return Head(provenance=provenance, index_tree=tree, subject="s", branch="b", committed="c")


def publish_receipt(directory: Path, platform: str, tree: str) -> None:
    document = {"gate": "publish-gate", "revision": "a" * 40, "tree": tree, "platform": platform, "images": {}}
    (directory / f"publish-gate-{platform.replace('/', '-')}.json").write_text(json.dumps(document))


def test_each_platforms_publish_receipt_is_its_own_card(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(receipt, "RECEIPTS", tmp_path)
    publish_receipt(tmp_path, "linux/amd64", "tree-1")
    publish_receipt(tmp_path, "linux/arm64", "older-tree")

    published = [state for state in receipt.receipt_states(head("tree-1"), None) if state.name.startswith("Publish")]

    assert [(state.name, state.state) for state in published] == [
        ("Publish gate (linux/amd64)", "current"),
        ("Publish gate (linux/arm64)", "stale"),
    ]


def test_no_publish_receipt_reads_as_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(receipt, "RECEIPTS", tmp_path)

    states = receipt.receipt_states(head("tree-1"), None)

    assert [(state.name, state.state) for state in states if state.name.startswith("Publish")] == [
        ("Publish gate", "missing")
    ]
