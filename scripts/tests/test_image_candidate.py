from pathlib import Path
from typing import Any

import pytest
from scripts.publish import image_candidate

DIGEST_1 = "sha256:" + "1" * 64
DIGEST_2 = "sha256:" + "2" * 64


def test_candidate_receipt_round_trips_in_stable_order(tmp_path: Path) -> None:
    images = {
        (registry, image): DIGEST_1
        for registry in ("z.example/team", "a.example/team")
        for image in image_candidate.IMAGES
    }
    receipt = image_candidate.CandidateReceipt("revision-1", images)
    path = tmp_path / "receipt"
    path.write_text(image_candidate.serialize_receipt(receipt))

    assert image_candidate.parse_receipt(path) == receipt
    assert path.read_text().splitlines()[1].startswith("image\ta.example/team")


def test_candidate_receipt_rejects_duplicate_rows(tmp_path: Path) -> None:
    row = f"image\tregistry/team\t{image_candidate.IMAGES[0]}\t{DIGEST_1}\n"
    path = tmp_path / "receipt"
    path.write_text(f"revision\trevision-1\n{row}{row}")

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


def test_push_archive_uses_stamped_revision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "IMAGE_CANDIDATE_REV").write_text("revision-1\n")
    pushed: list[tuple[str, list[str], None]] = []
    monkeypatch.setattr(
        image_candidate,
        "push_candidate",
        lambda revision, registries, gate: pushed.append((revision, registries, gate)),
    )

    assert image_candidate.push_archive(tmp_path, ["registry/team"]) == "revision-1"
    assert pushed == [("revision-1", ["registry/team"], None)]


def test_push_candidate_can_require_current_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_candidate, "capture", lambda *args: "current-revision")

    with pytest.raises(RuntimeError, match="must name the clean tree"):
        image_candidate.push_candidate("other-revision", ["registry/team"], None, require_current=True)
