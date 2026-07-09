"""Property-based checks for the HBOM profiler parsers.

The example tests in ``test_hbom_profilers.py`` pin the parse of realistic
fixtures; this file asserts the *invariants* that must hold for every input —
the parsers never raise on hostile bytes, and the topology/capacity post
conditions baked into the functions hold across randomized input rather than
just the hand-picked cases. Whole file is one kind, so the marker is applied at
module level.
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from repo2ree_core.hbom.cpu_profiler import _parse_cpuinfo_text
from repo2ree_core.hbom.gpu_profiler import _parse_lspci_output, _parse_nvidia_smi_csv
from repo2ree_core.hbom.profiler_utils import round_gib
from repo2ree_core.hbom.storage_profiler import _parse_lsblk_devices, _storage_type_for_device

pytestmark = pytest.mark.property


class TestRoundGib:
    @given(st.floats(min_value=-1e18, max_value=1e18, allow_nan=False, allow_infinity=False))
    def test_never_negative(self, value: float) -> None:
        """The in-function postcondition: a capacity is never negative."""
        assert round_gib(value) >= 0.0

    @given(st.integers(min_value=0, max_value=2**60), st.integers(min_value=0, max_value=2**60))
    def test_monotonic(self, a: int, b: int) -> None:
        """More bytes never rounds to a smaller GiB figure."""
        lo, hi = sorted((a, b))
        assert round_gib(lo) <= round_gib(hi)


class TestParseCpuinfo:
    # A field line as it appears in /proc/cpuinfo; blank lines separate blocks.
    _KEYS = st.sampled_from(["processor", "model name", "vendor_id", "physical id", "siblings", "cpu cores"])
    _LINE = st.builds(lambda k, v: f"{k}\t: {v}", _KEYS, st.text(max_size=12))
    _TEXT = st.text(alphabet=st.sampled_from(["\n", " ", "0", "1", "a", ":", "\t"]), max_size=200)

    @given(st.lists(st.one_of(_LINE, st.just("")), max_size=40))
    def test_structured_input_never_violates_postcondition(self, lines: list[str]) -> None:
        """Any assembly of plausible cpuinfo lines parses without raising.

        The counts postcondition lives in ``_parse_cpuinfo_text`` itself, so a
        clean return is the invariant; an empty result (no processor block) is
        allowed.
        """
        parsed = _parse_cpuinfo_text("\n".join(lines))
        if parsed:
            assert parsed["quantity"] >= 1
            assert parsed["cores_per_cpu"] >= 1
            assert parsed["threads_per_core"] >= 1

    @given(_TEXT)
    def test_arbitrary_text_does_not_raise(self, text: str) -> None:
        _parse_cpuinfo_text(text)

    @given(st.integers(min_value=1, max_value=20))
    def test_logical_cpus_counts_blocks(self, n: int) -> None:
        """logical_cpus equals the number of processor blocks seen."""
        text = "\n\n".join(f"processor\t: {i}\nmodel name\t: X" for i in range(n))
        assert _parse_cpuinfo_text(text)["logical_cpus"] == n


class TestStorageTypeForDevice:
    _VALID = {"HDD", "SSD", "NVMe", "eMMC", "SD"}

    @given(st.text(max_size=16), st.sampled_from(["0", "1", ""]), st.text(max_size=8), st.text(max_size=16))
    def test_always_returns_valid_type(self, name: str, rota: str, transport: str, model: str) -> None:
        kind, _interface = _storage_type_for_device(name, rota, transport, model)
        assert kind in self._VALID


class TestCommandParsersAreRobust:
    @given(st.text(max_size=200))
    def test_nvidia_never_raises(self, stdout: str) -> None:
        for definition in _parse_nvidia_smi_csv(stdout).values():
            assert definition.memory_gb >= 0.0
            assert definition.quantity >= 1

    @given(st.text(max_size=200))
    def test_lspci_never_raises(self, stdout: str) -> None:
        for definition in _parse_lspci_output(stdout).values():
            assert definition.quantity >= 1

    @given(st.text(max_size=200))
    def test_lsblk_never_raises_on_arbitrary_text(self, stdout: str) -> None:
        # Non-JSON and JSON-that-is-not-an-object alike degrade to empty.
        _parse_lsblk_devices(stdout)

    @given(
        st.lists(
            st.fixed_dictionaries(
                {
                    "name": st.text(min_size=1, max_size=8),
                    "model": st.text(max_size=8),
                    "size": st.integers(min_value=0, max_value=2**50),
                    "rota": st.sampled_from(["0", "1"]),
                    "type": st.sampled_from(["disk", "part", "rom"]),
                }
            ),
            max_size=6,
        )
    )
    def test_lsblk_definitions_are_valid(self, devices: list[dict[str, object]]) -> None:
        parsed = _parse_lsblk_devices(json.dumps({"blockdevices": devices}))
        for definition in parsed.values():
            assert definition.quantity >= 1
            assert definition.capacity_gb >= 0.0
