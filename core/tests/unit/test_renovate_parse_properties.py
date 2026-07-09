"""Property-based checks for the Renovate parse path.

The example fixtures in ``test_renovate_parse.py`` pin the mapping; this file
defends the invariants that must hold for every payload — the parser never
raises on a hostile Renovate payload, and the ``container_image`` deps never
carry a ``manifest_path`` (the assertion baked into ``_inventory_from_payload``).
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_core.repo_profiler.sources.renovate import (
    _inventory_from_payload,
    parse_renovate_stdout,
)

pytestmark = pytest.mark.property

_MARKER = "Extracted dependencies (repository=local)"

# A dependency object as Renovate might emit it — every field optional, values
# occasionally the wrong type, to exercise the defensive ``.get`` reads.
_DEP = st.fixed_dictionaries(
    {},
    optional={
        "depName": st.text(max_size=12),
        "packageName": st.text(max_size=12),
        "currentValue": st.one_of(st.none(), st.text(max_size=8)),
        "lockedVersion": st.one_of(st.none(), st.text(max_size=8)),
        "currentDigest": st.one_of(st.none(), st.text(max_size=8)),
        "datasource": st.sampled_from(["docker", "pypi", "npm", "golang"]),
    },
)

_PACKAGE_FILE = st.fixed_dictionaries(
    {},
    optional={
        "packageFile": st.one_of(st.none(), st.text(max_size=12)),
        "deps": st.lists(st.one_of(_DEP, st.text(max_size=4)), max_size=5),
    },
)

_MANAGERS = st.sampled_from(["pip", "npm", "dockerfile", "docker-compose", "gomod"])

_PAYLOAD = st.dictionaries(_MANAGERS, st.lists(st.one_of(_PACKAGE_FILE, st.integers()), max_size=4), max_size=4)


class TestInventoryFromPayload:
    @given(_PAYLOAD)
    def test_container_deps_never_carry_manifest_path(self, payload: dict[str, object]) -> None:
        """The module's own postcondition holds for every generated payload."""
        inventory = _inventory_from_payload(payload)
        for dep in inventory.dependencies:
            if dep.kind == "container_image":
                assert dep.manifest_path is None

    @given(_PAYLOAD)
    def test_every_dep_has_a_name(self, payload: dict[str, object]) -> None:
        inventory = _inventory_from_payload(payload)
        assert all(dep.name for dep in inventory.dependencies)


class TestParseRenovateStdout:
    @given(st.text(max_size=200))
    def test_arbitrary_stdout_never_raises(self, stdout: str) -> None:
        parse_renovate_stdout(stdout)

    @given(_PAYLOAD)
    def test_marked_payload_round_trips(self, payload: dict[str, object]) -> None:
        stdout = f"INFO {_MARKER} {json.dumps(payload)}\n"
        inventory = parse_renovate_stdout(stdout)
        assert inventory is not None
        for dep in inventory.dependencies:
            if dep.kind == "container_image":
                assert dep.manifest_path is None
