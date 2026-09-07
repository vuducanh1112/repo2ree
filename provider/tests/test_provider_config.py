"""Environment-backed provider configuration.

The contract under test: an explicit ``PROVIDER_ID`` wins outright and never
touches the state dir, an absent one falls back to the persisted identity, and
every remaining knob has a working default so a bare ``repo2ree-provider-docker``
starts against a local control plane.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import repo2ree_provider_docker.config as config_module

_PROVIDER_ENV = (
    "PROVIDER_ID",
    "PROVIDER_STATE_DIR",
    "PROVIDER_API_WS_URL",
    "PROVIDER_WORKBENCH_API_WS_URL",
    "PROVIDER_DOCKER_MODE",
    "PROVIDER_WORKBENCH_DOCKER_NETWORK",
    "PROVIDER_ACCEPTS_CUSTOM_IMAGE",
    "WORKBENCH_IMAGE_CATALOG",
    "OTLP_ENDPOINT",
    "PROVIDER_WORKBENCH_TELEMETRY",
    "PROVIDER_WORKBENCH_OTLP_ENDPOINT",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)


def test_load_config_prefers_explicit_provider_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("PROVIDER_API_WS_URL", "wss://api.example/provider/connect")
    monkeypatch.setenv("PROVIDER_WORKBENCH_API_WS_URL", "wss://api.example/workbench/connect")
    monkeypatch.setenv("PROVIDER_DOCKER_MODE", "host-socket")
    monkeypatch.setenv("PROVIDER_WORKBENCH_DOCKER_NETWORK", "repo2ree-lab")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://collector:4318")

    def refuse_identity(path: Path) -> str:
        raise AssertionError("an explicit provider id must not touch the state dir")

    monkeypatch.setattr(config_module, "load_or_create_provider_id", refuse_identity)

    config = config_module.load_config()

    assert config.provider_id == "docker-provider-explicit"
    assert config.api_ws_url == "wss://api.example/provider/connect"
    assert config.workbench_api_ws_url == "wss://api.example/workbench/connect"
    assert config.docker_mode == "host-socket"
    assert config.workbench_network == "repo2ree-lab"
    assert config.otlp_endpoint == "http://collector:4318"


def test_load_config_persists_identity_when_not_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVIDER_STATE_DIR", str(tmp_path))
    paths: list[Path] = []

    def load_identity(path: Path) -> str:
        paths.append(path)
        return "persisted-provider"

    monkeypatch.setattr(config_module, "load_or_create_provider_id", load_identity)

    config = config_module.load_config()

    assert config.provider_id == "persisted-provider"
    assert paths == [tmp_path]
    # The two connections are separate endpoints on the same control plane: the
    # provider dials one itself and hands the other to each workbench it starts.
    assert config.api_ws_url == "ws://localhost:8000/provider/connect"
    assert config.workbench_api_ws_url == "ws://localhost:8000/workbench/connect"
    assert config.docker_mode == "dind"
    assert config.workbench_network == ""
    assert config.otlp_endpoint is None


def test_blank_otlp_endpoint_reads_as_no_collector(monkeypatch: pytest.MonkeyPatch) -> None:
    # Compose passes `OTLP_ENDPOINT: ${OTLP_ENDPOINT:-}`, so an unset host var
    # arrives as an empty string rather than as an absent one.
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("OTLP_ENDPOINT", "")

    assert config_module.load_config().otlp_endpoint is None


# ------------------------------------------------
# The curated catalog
# ------------------------------------------------


def test_a_catalog_entry_needs_only_a_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("WORKBENCH_IMAGE_CATALOG", json.dumps([{"ref": "docker:29-dind"}]))

    (image,) = config_module.load_config().images

    # The ref identifies the entry, so it doubles as the id and the label; a
    # deployment publishing one image should not have to name it three times.
    assert (image.ref, image.id, image.label) == ("docker:29-dind", "docker:29-dind", "docker:29-dind")
    assert image.description == ""


def test_the_catalog_replaces_the_default_wholesale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv(
        "WORKBENCH_IMAGE_CATALOG",
        json.dumps(
            [
                {"id": "standard", "ref": "registry.example/bench:1", "label": "Standard", "description": "Docker."},
                {"id": "python", "ref": "docker.io/library/python:3.11-slim", "label": "Python"},
            ]
        ),
    )

    images = config_module.load_config().images

    assert [image.id for image in images] == ["standard", "python"]
    assert config_module._DEFAULT_IMAGE not in {image.ref for image in images}


def test_an_unset_catalog_still_offers_one_image(monkeypatch: pytest.MonkeyPatch) -> None:
    # A bare `repo2ree-provider-docker` has to be usable, so the default is a
    # catalog of one rather than an empty picker.
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")

    config = config_module.load_config()

    assert [image.ref for image in config.images] == [config_module._DEFAULT_IMAGE]


def test_duplicate_ids_are_a_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    # Two entries under one id makes the picker ambiguous; failing here beats
    # resolving it arbitrarily at provision time.
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv(
        "WORKBENCH_IMAGE_CATALOG",
        json.dumps([{"id": "standard", "ref": "a:1"}, {"id": "standard", "ref": "b:2"}]),
    )

    with pytest.raises(ValueError, match="unique"):
        config_module.load_config()


def test_an_entry_without_a_ref_is_a_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("WORKBENCH_IMAGE_CATALOG", json.dumps([{"id": "standard", "ref": ""}]))

    with pytest.raises(ValueError, match="needs a ref"):
        config_module.load_config()


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", True), ("false", False), ("0", False), ("no", False), ("true", True), ("1", True)],
)
def test_custom_images_are_accepted_unless_the_deployment_says_otherwise(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: bool
) -> None:
    # The curated set is a recommendation by default; a deployment that wants it
    # to be a jail has to say so.
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("PROVIDER_ACCEPTS_CUSTOM_IMAGE", value)

    assert config_module.load_config().accepts_custom_image is expected


def test_a_misspelled_boolean_is_a_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("PROVIDER_ACCEPTS_CUSTOM_IMAGE", "ture")

    with pytest.raises(ValueError, match="boolean"):
        config_module.load_config()


def test_benches_relay_their_own_spans_unless_told_otherwise() -> None:
    config = config_module.load_config()

    # The provider's own OTLP_ENDPOINT says nothing about what a bench can
    # reach, so the default never assumes a bench shares its egress.
    assert config.workbench_telemetry == "relay"
    assert config.workbench_otlp_endpoint is None


def test_bench_telemetry_is_configured_on_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_WORKBENCH_TELEMETRY", "Direct")
    monkeypatch.setenv("PROVIDER_WORKBENCH_OTLP_ENDPOINT", "http://collector.internal:4318")

    config = config_module.load_config()

    assert config.workbench_telemetry == "direct"
    assert config.workbench_otlp_endpoint == "http://collector.internal:4318"


def test_direct_bench_telemetry_requires_a_reachable_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVIDER_ID", "docker-provider-explicit")
    monkeypatch.setenv("PROVIDER_WORKBENCH_TELEMETRY", "direct")

    with pytest.raises(ValueError, match="PROVIDER_WORKBENCH_OTLP_ENDPOINT is required"):
        config_module.load_config()
