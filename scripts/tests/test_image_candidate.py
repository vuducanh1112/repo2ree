import json
from pathlib import Path
from typing import Any

import pytest
from scripts.gates import publish_gate
from scripts.gates.receipts import PublishGateReceipt
from scripts.publish import image_archive_set, image_candidate

DIGEST_1 = "sha256:" + "1" * 64
DIGEST_2 = "sha256:" + "2" * 64
ARM_IDS = dict.fromkeys(image_candidate.IMAGES, "sha256:" + "a" * 64)
AMD_IDS = dict.fromkeys(image_candidate.IMAGES, "sha256:" + "b" * 64)


def test_candidate_receipt_round_trips_in_stable_order(tmp_path: Path) -> None:
    images = {
        (registry, image): DIGEST_1
        for registry in ("z.example/team", "a.example/team")
        for image in image_candidate.IMAGES
    }
    receipt = image_candidate.CandidateReceipt("revision-1", images, "linux/amd64")
    path = tmp_path / "receipt"
    path.write_text(image_candidate.serialize_receipt(receipt))

    assert image_candidate.parse_receipt(path) == receipt
    assert json.loads(path.read_text())["images"][0]["registry"] == "a.example/team"


def test_candidate_receipt_rejects_duplicate_rows(tmp_path: Path) -> None:
    row = {"registry": "registry/team", "image": image_candidate.IMAGES[0], "digest": DIGEST_1}
    path = tmp_path / "receipt"
    path.write_text(json.dumps({"revision": "revision-1", "images": [row, row]}))

    with pytest.raises(RuntimeError, match="duplicate image row"):
        image_candidate.parse_receipt(path)


def test_resolve_rejects_registry_disagreement(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(reference: str) -> str:
        return DIGEST_1 if reference.startswith("one/") else DIGEST_2

    monkeypatch.setattr(image_candidate, "resolve_digest", resolve)

    with pytest.raises(RuntimeError, match="registries disagree"):
        image_candidate.resolve_candidate("revision-1", ["one", "two"])


def test_image_environment_is_digest_pinned() -> None:
    registry = "registry.example/team"
    receipt: Any = image_candidate.CandidateReceipt(
        "revision-1", {(registry, image): DIGEST_1 for image in image_candidate.IMAGES}
    )

    environment = image_candidate.image_environment(receipt, registry)

    assert set(environment) == set(image_candidate.STACK_VARIABLES.values())
    assert all(value.endswith(f"@{DIGEST_1}") for value in environment.values())


def test_push_candidate_can_require_current_revision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(image_candidate, "capture", lambda *args: "current-revision")

    with pytest.raises(RuntimeError, match="must name the clean tree"):
        image_candidate.push_candidate(
            "other-revision", ["registry/team"], tmp_path, tmp_path, ["linux/arm64"], require_current=True
        )


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[tuple[str, ...]]:
    """An arm64 pushing host whose publish gate certified ARM_IDS for revision-1; the docker calls it makes."""
    calls: list[tuple[str, ...]] = []
    receipt = PublishGateReceipt(
        revision="revision-1",
        tree="tree-1",
        written=__import__("datetime").datetime.now(),
        images=ARM_IDS,
        platform="linux/arm64",
    )
    monkeypatch.setattr(publish_gate, "platform", lambda: "linux/arm64")
    monkeypatch.setattr(publish_gate, "verify_receipt", lambda path, revision: None)
    monkeypatch.setattr(publish_gate, "read_receipt", lambda path: receipt)
    monkeypatch.setattr(image_candidate, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(image_candidate, "resolve_digest", lambda reference: "sha256:" + str(len(calls)).zfill(64))
    monkeypatch.setattr(image_archive_set, "load", lambda archive_set: calls.append(("load", archive_set.platform)))
    return calls


def amd64_archives(root: Path, *, revision: str = "revision-1", tree: str = "tree-1") -> Path:
    directory = root / "linux-amd64"
    directory.mkdir(parents=True)
    for image in image_candidate.IMAGES:
        (directory / image_archive_set.archive_name(image)).write_bytes(image.encode())
    image_archive_set.seal(directory, revision=revision, tree=tree, platform="linux/amd64", images=AMD_IDS)
    return root


def test_each_platform_goes_up_by_its_certified_ids_and_the_candidate_is_one_index_over_them(
    host: list[tuple[str, ...]], tmp_path: Path
) -> None:
    archives = amd64_archives(tmp_path / "images")

    image_candidate.push_candidate("revision-1", ["registry/team"], tmp_path, archives, ["linux/amd64", "linux/arm64"])

    assert ("load", "linux/amd64") in host
    tags = [call for call in host if call[:2] == ("docker", "tag")]
    # Never a mutable local tag: the image IDs each platform's publish gate certified.
    assert {call[2] for call in tags} == {ARM_IDS["repo2ree-gui"], AMD_IDS["repo2ree-gui"]}
    assert {call[3] for call in tags if "repo2ree-gui" in call[3]} == {
        "registry/team/repo2ree-gui:revision-1-linux-arm64",
        "registry/team/repo2ree-gui:revision-1-linux-amd64",
    }
    [gui_index] = [
        call for call in host if call[:3] == ("docker", "buildx", "imagetools") and "repo2ree-gui:" in call[5]
    ]
    assert gui_index[4:6] == ("-t", "registry/team/repo2ree-gui:revision-1")
    assert len(gui_index[6:]) == 2  # one source per platform, each by digest
    assert all("@sha256:" in source for source in gui_index[6:])


def test_a_missing_platform_pushes_nothing(host: list[tuple[str, ...]], tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no certified images for linux/amd64"):
        image_candidate.push_candidate(
            "revision-1", ["registry/team"], tmp_path, tmp_path / "none", ["linux/amd64", "linux/arm64"]
        )
    assert host == []


def test_archives_of_another_tree_are_refused(host: list[tuple[str, ...]], tmp_path: Path) -> None:
    archives = amd64_archives(tmp_path / "images", tree="older-tree")

    with pytest.raises(RuntimeError, match="archive them again"):
        image_candidate.push_candidate("revision-1", ["registry/team"], tmp_path, archives, ["linux/amd64"])
    assert host == []


def validation(state: Path, platform: str, digest: str = DIGEST_1) -> None:
    receipt = image_candidate.CandidateReceipt(
        "revision-1", {("registry/team", image): digest for image in image_candidate.IMAGES}, platform
    )
    path = image_candidate.validation_path(state, "revision-1", platform)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(image_candidate.serialize_receipt(receipt))


def test_promotion_needs_every_platform_in_the_index_validated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(image_candidate, "resolve_digest", lambda reference: DIGEST_1)
    monkeypatch.setattr(image_candidate, "index_platforms", lambda reference: {"linux/amd64", "linux/arm64"})
    validation(tmp_path, "linux/arm64")

    with pytest.raises(RuntimeError, match="not validated on linux/amd64"):
        image_candidate.verify_candidate("revision-1", tmp_path)

    validation(tmp_path, "linux/amd64")
    assert (
        image_candidate.verify_candidate("revision-1", tmp_path).images[("registry/team", "repo2ree-gui")] == DIGEST_1
    )


def test_validations_that_saw_different_digests_are_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    validation(tmp_path, "linux/arm64", DIGEST_1)
    validation(tmp_path, "linux/amd64", DIGEST_2)

    with pytest.raises(RuntimeError, match="saw different digests"):
        image_candidate.verify_candidate("revision-1", tmp_path)


def test_promotion_moves_edge_to_the_index_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(image_candidate, "resolve_digest", lambda reference: DIGEST_1)
    monkeypatch.setattr(image_candidate, "index_platforms", lambda reference: {"linux/arm64"})
    monkeypatch.setattr(image_candidate, "run", lambda *args: calls.append(args))
    validation(tmp_path, "linux/arm64")

    image_candidate.promote_candidate("revision-1", tmp_path)

    gui = [call for call in calls if any(part.endswith("repo2ree-gui:edge") for part in call)]
    assert gui == [
        (
            "docker",
            "buildx",
            "imagetools",
            "create",
            "-t",
            "registry/team/repo2ree-gui:edge",
            f"registry/team/repo2ree-gui@{DIGEST_1}",
        )
    ]
