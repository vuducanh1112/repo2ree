from pathlib import Path

import pytest

from repo2ree_testbed.stack import mirror


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Each network the mirror was started on ("" for a published port); it is running once started."""
    calls: list[str] = []
    monkeypatch.delenv("REPO2REE_REGISTRY_MIRROR", raising=False)
    monkeypatch.setattr(mirror, "_running", lambda: bool(calls))
    monkeypatch.setattr(mirror, "_start", calls.append)
    monkeypatch.setattr(mirror, "_join", lambda network: None)
    monkeypatch.setattr(mirror, "_wait_ready", lambda: None)
    return calls


def test_in_a_container_the_mirror_shares_its_network_and_is_named(
    monkeypatch: pytest.MonkeyPatch, started: list[str]
) -> None:
    monkeypatch.setattr(mirror, "own_container", lambda: "dev-1")
    monkeypatch.setattr(mirror, "first_network", lambda container: "dev_default")

    assert mirror.ensure() == "http://repo2ree-registry-mirror:5000"
    assert mirror.ensure() == "http://repo2ree-registry-mirror:5000"
    assert started == ["dev_default"]


def test_on_a_host_the_mirror_publishes_a_port_benches_reach_through_the_gateway(
    monkeypatch: pytest.MonkeyPatch, started: list[str]
) -> None:
    monkeypatch.setattr(mirror, "own_container", lambda: None)

    assert mirror.ensure() == f"http://host.docker.internal:{mirror.PUBLISHED_PORT}"
    assert started == [""]


@pytest.mark.parametrize(("override", "url"), [("off", ""), ("http://cache.lan:5000", "http://cache.lan:5000")])
def test_an_override_starts_nothing(
    monkeypatch: pytest.MonkeyPatch, started: list[str], override: str, url: str
) -> None:
    monkeypatch.setenv("REPO2REE_REGISTRY_MIRROR", override)

    assert mirror.ensure() == url
    assert started == []


def test_the_images_to_warm_are_the_digest_pinned_bases_of_the_examples(tmp_path: Path) -> None:
    digest = "sha256:" + "a" * 64
    (tmp_path / "one").mkdir()
    (tmp_path / "one/Dockerfile").write_text(f"# a comment\nFROM python:3.11-slim@{digest}\nRUN true\n")
    (tmp_path / "two").mkdir()
    (tmp_path / "two/Dockerfile").write_text(f"FROM docker.io/acme/tool@{digest}\nFROM unpinned:latest\n")

    assert mirror.pinned_images(tmp_path) == [("acme/tool", digest), ("library/python", digest)]
