"""Parse coverage for the dormant Renovate adapter.

``run_extract`` shells out to the (retired) renovate binary, but the parse path
it feeds — ``parse_renovate_stdout`` and its helpers — is pure and is the
reference corpus the module's docstring promises. These fixtures pin the
mapping from Renovate's ``--dry-run=extract`` payload onto the tool-agnostic
``DependencyInventory``; the invariants live in ``test_renovate_parse_properties``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from repo2ree_core.repo_profiler.sources.renovate import (
    _extract_json_payload,
    _is_container_dep,
    _package_files,
    parse_renovate_stdout,
)

_MARKER = "Extracted dependencies (repository=local)"


def _stdout(payload: Mapping[str, Any]) -> str:
    return f"INFO: {_MARKER} {json.dumps(payload)}\ntrailing log line\n"


class TestExtractJsonPayload:
    def test_marker_absent_is_none(self) -> None:
        assert _extract_json_payload("no marker here") is None

    def test_no_brace_after_marker_is_none(self) -> None:
        assert _extract_json_payload(f"{_MARKER} but no json") is None

    def test_invalid_json_is_none(self) -> None:
        assert _extract_json_payload(f"{_MARKER} {{not valid") is None

    def test_non_object_json_is_none(self) -> None:
        assert _extract_json_payload(f"{_MARKER} [1, 2, 3]") is None

    def test_extracts_object_and_ignores_trailing(self) -> None:
        payload = _extract_json_payload(_stdout({"a": 1}))
        assert payload == {"a": 1}


class TestPackageFiles:
    def test_nested_packagefiles_key(self) -> None:
        payload = {"packageFiles": {"pip": [{"packageFile": "req.txt"}]}}
        assert _package_files(payload) == {"pip": [{"packageFile": "req.txt"}]}

    def test_flat_layout(self) -> None:
        payload = {"npm": [{"packageFile": "package.json"}]}
        assert _package_files(payload) == payload

    def test_non_list_values_dropped(self) -> None:
        payload = {"pip": [{"x": 1}], "meta": "scalar"}
        assert _package_files(payload) == {"pip": [{"x": 1}]}

    def test_non_dict_is_empty(self) -> None:
        assert _package_files(None) == {}
        assert _package_files([1, 2]) == {}  # type: ignore[arg-type]


class TestIsContainerDep:
    def test_docker_datasource(self) -> None:
        assert _is_container_dep("pip", {"datasource": "docker"}) is True

    def test_dockerfile_manager(self) -> None:
        assert _is_container_dep("dockerfile", {}) is True
        assert _is_container_dep("docker-compose", {}) is True

    def test_plain_library(self) -> None:
        assert _is_container_dep("pip", {"datasource": "pypi"}) is False


class TestParseRenovateStdout:
    def test_missing_marker_is_none(self) -> None:
        assert parse_renovate_stdout("nothing to see") is None

    def test_library_dependency(self) -> None:
        payload = {
            "pip_requirements": [
                {
                    "packageFile": "requirements.txt",
                    "deps": [
                        {"depName": "flask", "currentValue": "3.0.0", "lockedVersion": "3.0.0"},
                    ],
                }
            ]
        }
        inventory = parse_renovate_stdout(_stdout(payload))
        assert inventory is not None
        (dep,) = inventory.dependencies
        assert dep.name == "flask"
        assert dep.kind == "library"
        assert dep.declared_version == "3.0.0"
        assert dep.locked_version == "3.0.0"
        assert dep.manifest_path == "requirements.txt"

    def test_container_dependency_drops_manifest_path(self) -> None:
        payload = {
            "dockerfile": [
                {
                    "packageFile": "Dockerfile",
                    "deps": [
                        {"depName": "python", "currentValue": "3.12", "currentDigest": "sha256:abc"},
                    ],
                }
            ]
        }
        inventory = parse_renovate_stdout(_stdout(payload))
        assert inventory is not None
        (dep,) = inventory.dependencies
        assert dep.kind == "container_image"
        assert dep.digest == "sha256:abc"
        assert dep.manifest_path is None  # the module's own invariant

    def test_packagename_fallback_and_unknown(self) -> None:
        payload = {
            "npm": [
                {
                    "packageFile": "package.json",
                    "deps": [{"packageName": "left-pad"}, {}],
                }
            ]
        }
        inventory = parse_renovate_stdout(_stdout(payload))
        assert inventory is not None
        assert [d.name for d in inventory.dependencies] == ["left-pad", "?"]

    def test_non_dict_entries_skipped(self) -> None:
        payload = {"pip": ["not-a-dict", {"packageFile": "a", "deps": ["x", {"depName": "ok"}]}]}
        inventory = parse_renovate_stdout(_stdout(payload))
        assert inventory is not None
        assert [d.name for d in inventory.dependencies] == ["ok"]
