"""Example-based coverage for the HBOM hardware profilers.

The profilers parse the output of ``/proc``/``/sys`` reads and of ``lsblk``,
``lspci`` and ``nvidia-smi``. The I/O is threaded through a path argument (the
``/proc``/``/sys`` readers) or funnelled through a pure parse helper (the
command readers), so the parsing is exercised against canned fixtures with no
real hardware. The invariant-style checks live in
``test_hbom_profilers_properties.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo2ree_core.analysis.hbom import gpu_profiler, storage_profiler
from repo2ree_core.analysis.hbom.cpu_profiler import _parse_cpuinfo_text, profile_cpus
from repo2ree_core.analysis.hbom.generate_hbom import generate_hbom
from repo2ree_core.analysis.hbom.gpu_profiler import _parse_lspci_output, _parse_nvidia_smi_csv, profile_gpus
from repo2ree_core.analysis.hbom.memory_profiler import profile_memory
from repo2ree_core.analysis.hbom.network_profiler import profile_network
from repo2ree_core.analysis.hbom.profiler_utils import (
    read_optional_int,
    read_optional_text,
    round_gib,
    run_command,
)
from repo2ree_core.analysis.hbom.storage_profiler import (
    _parse_lsblk_devices,
    _storage_type_for_device,
    profile_storage,
)
from repo2ree_core.domain.hbom import HBOM


def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["x"], returncode=returncode, stdout=stdout, stderr="")


# A two-socket, four-core, two-thread machine — enough distinct fields to drive
# every branch of the topology derivation.
_CPUINFO_TWO_SOCKET = """\
processor\t: 0
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Gold 6248
physical id\t: 0
siblings\t: 8
cpu cores\t: 4

processor\t: 1
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Gold 6248
physical id\t: 0
siblings\t: 8
cpu cores\t: 4

processor\t: 2
vendor_id\t: GenuineIntel
model name\t: Intel(R) Xeon(R) Gold 6248
physical id\t: 1
siblings\t: 8
cpu cores\t: 4
"""


class TestRoundGib:
    def test_converts_bytes_to_gib(self) -> None:
        assert round_gib(1024**3) == 1.0
        assert round_gib(3 * 1024**3) == 3.0

    def test_non_positive_is_zero(self) -> None:
        assert round_gib(0) == 0.0
        assert round_gib(-5) == 0.0

    def test_rounds_to_two_places(self) -> None:
        assert round_gib(1536 * 1024**2) == 1.5


class TestReadHelpers:
    def test_read_optional_text_missing(self, tmp_path: Path) -> None:
        assert read_optional_text(tmp_path / "nope") == ""

    def test_read_optional_text_strips(self, tmp_path: Path) -> None:
        target = tmp_path / "v"
        target.write_text("  hello \n")
        assert read_optional_text(target) == "hello"

    def test_read_optional_int_parses(self, tmp_path: Path) -> None:
        target = tmp_path / "speed"
        target.write_text("10000\n")
        assert read_optional_int(target) == 10000

    def test_read_optional_int_missing_is_none(self, tmp_path: Path) -> None:
        assert read_optional_int(tmp_path / "nope") is None

    def test_read_optional_int_nonnumeric_is_none(self, tmp_path: Path) -> None:
        target = tmp_path / "speed"
        target.write_text("unknown")
        assert read_optional_int(target) is None

    def test_run_command_missing_binary(self) -> None:
        assert run_command("definitely-not-a-real-binary-xyz") is None

    def test_run_command_runs(self) -> None:
        completed = run_command("echo", "hi")
        assert completed is not None
        assert completed.stdout.strip() == "hi"


class TestParseCpuinfo:
    def test_two_socket_topology(self) -> None:
        parsed = _parse_cpuinfo_text(_CPUINFO_TWO_SOCKET)
        assert parsed["vendor"] == "GenuineIntel"
        assert parsed["model_name"] == "Intel(R) Xeon(R) Gold 6248"
        assert parsed["quantity"] == 2  # two distinct physical ids
        assert parsed["cores_per_cpu"] == 4
        assert parsed["threads_per_core"] == 2  # 8 siblings / 4 cores
        assert parsed["logical_cpus"] == 3  # three processor blocks

    def test_empty_text_is_empty(self) -> None:
        assert _parse_cpuinfo_text("") == {}

    def test_single_core_defaults(self) -> None:
        parsed = _parse_cpuinfo_text("processor\t: 0\nmodel name\t: Tiny\n")
        assert parsed["quantity"] == 1
        assert parsed["cores_per_cpu"] == 1
        assert parsed["threads_per_core"] == 1
        assert parsed["logical_cpus"] == 1

    def test_malformed_counts_fall_back_to_one(self) -> None:
        text = "processor\t: 0\ncpu cores\t: not-a-number\nsiblings\t: also-bad\n"
        parsed = _parse_cpuinfo_text(text)
        assert parsed["cores_per_cpu"] == 1
        assert parsed["threads_per_core"] == 1

    def test_profile_cpus_from_file(self, tmp_path: Path) -> None:
        cpuinfo = tmp_path / "cpuinfo"
        cpuinfo.write_text(_CPUINFO_TWO_SOCKET)
        cpus = profile_cpus(cpuinfo)
        assert "Intel(R) Xeon(R) Gold 6248" in cpus
        definition = cpus["Intel(R) Xeon(R) Gold 6248"]
        assert definition.quantity == 2
        assert definition.cores_per_cpu == 4
        assert definition.threads_per_core == 2
        assert definition.extra_info["logical_cpus"] == 3

    def test_profile_cpus_missing_file_uses_platform(self, tmp_path: Path) -> None:
        # No /proc/cpuinfo: still yields exactly one entry keyed by a platform
        # fallback, with valid ge=1 counts.
        cpus = profile_cpus(tmp_path / "absent")
        assert len(cpus) == 1
        (definition,) = cpus.values()
        assert definition.quantity >= 1


class TestProfileMemory:
    def test_reads_memtotal(self, tmp_path: Path) -> None:
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemTotal:       16384000 kB\nMemFree: 100 kB\n")
        memory = profile_memory(meminfo)
        definition = memory["Installed Memory"]
        # 16384000 KiB = 15.62 GiB.
        assert definition.capacity_gb == round_gib(16384000 * 1024)
        assert definition.extra_info["aggregate"] is True

    def test_missing_file_is_zero_capacity(self, tmp_path: Path) -> None:
        memory = profile_memory(tmp_path / "absent")
        assert memory["Installed Memory"].capacity_gb == 0.0

    def test_malformed_memtotal_is_zero(self, tmp_path: Path) -> None:
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemTotal:       notanumber kB\n")
        assert profile_memory(meminfo)["Installed Memory"].capacity_gb == 0.0


class TestStorageTypeForDevice:
    def test_nvme_by_name(self) -> None:
        assert _storage_type_for_device("nvme0n1", "0", "", "")[0] == "NVMe"

    def test_nvme_by_transport(self) -> None:
        assert _storage_type_for_device("sda", "0", "nvme", "")[0] == "NVMe"

    def test_emmc(self) -> None:
        assert _storage_type_for_device("mmcblk0", "0", "", "")[0] == "eMMC"

    def test_sd_card(self) -> None:
        assert _storage_type_for_device("mmcblk0", "0", "", "SD Card")[0] == "SD"

    def test_rotational_is_hdd(self) -> None:
        kind, interface = _storage_type_for_device("sda", "1", "sata", "")
        assert kind == "HDD"
        assert interface == "SATA"

    def test_non_rotational_is_ssd(self) -> None:
        assert _storage_type_for_device("sda", "0", "sata", "")[0] == "SSD"


class TestParseLsblkDevices:
    def test_single_disk(self) -> None:
        stdout = """
        {"blockdevices": [
          {"name": "nvme0n1", "model": "Samsung 990", "vendor": "Samsung",
           "size": 1000204886016, "rota": "0", "tran": "nvme", "type": "disk"}
        ]}
        """
        devices = _parse_lsblk_devices(stdout)
        assert "Samsung 990" in devices
        definition = devices["Samsung 990"]
        assert definition.storage_type == "NVMe"
        assert definition.vendor == "Samsung"
        assert definition.capacity_gb == round_gib(1000204886016)

    def test_partitions_are_skipped(self) -> None:
        stdout = """
        {"blockdevices": [
          {"name": "sda1", "model": "", "size": 100, "rota": "0", "type": "part"}
        ]}
        """
        assert _parse_lsblk_devices(stdout) == {}

    def test_identical_disks_are_counted(self) -> None:
        def disk(name: str) -> str:
            return (
                f'{{"name": "{name}", "model": "Acme SSD", "vendor": "Acme", '
                '"size": 512110190592, "rota": "0", "tran": "sata", "type": "disk"}'
            )

        stdout = f'{{"blockdevices": [{disk("sda")}, {disk("sdb")}]}}'
        devices = _parse_lsblk_devices(stdout)
        assert len(devices) == 1
        assert devices["Acme SSD"].quantity == 2

    def test_same_model_different_size_splits_key(self) -> None:
        stdout = """
        {"blockdevices": [
          {"name": "sda", "model": "Acme", "size": 512110190592, "rota": "0", "type": "disk"},
          {"name": "sdb", "model": "Acme", "size": 1000204886016, "rota": "0", "type": "disk"}
        ]}
        """
        devices = _parse_lsblk_devices(stdout)
        assert len(devices) == 2
        assert "Acme" in devices
        assert "Acme (sdb)" in devices

    def test_invalid_json_is_empty(self) -> None:
        assert _parse_lsblk_devices("not json") == {}


class TestParseNvidiaSmi:
    def test_single_gpu(self) -> None:
        stdout = "NVIDIA A100-SXM4-40GB, 40960, 535.104.05, 00000000:07:00.0\n"
        gpus = _parse_nvidia_smi_csv(stdout)
        definition = gpus["NVIDIA A100-SXM4-40GB"]
        assert definition.vendor == "NVIDIA"
        assert definition.memory_gb == round(40960 / 1024, 2)
        assert definition.extra_info["driver_version"] == "535.104.05"

    def test_identical_gpus_counted(self) -> None:
        line = "NVIDIA A100, 40960, 535.104.05, 00000000:07:00.0\n"
        gpus = _parse_nvidia_smi_csv(line * 4)
        assert gpus["NVIDIA A100"].quantity == 4

    def test_short_line_skipped(self) -> None:
        assert _parse_nvidia_smi_csv("only, two\n") == {}

    def test_bad_memory_is_zero(self) -> None:
        gpus = _parse_nvidia_smi_csv("NVIDIA X, N/A, 1.0, bus\n")
        assert gpus["NVIDIA X"].memory_gb == 0.0


class TestParseLspci:
    def test_vga_controller(self) -> None:
        stdout = (
            "00:02.0 VGA compatible controller: Intel Corporation UHD Graphics 630\n"
            "01:00.0 3D controller: NVIDIA Corporation GA100\n"
            "00:1f.0 ISA bridge: Intel Corporation something\n"
        )
        gpus = _parse_lspci_output(stdout)
        assert len(gpus) == 2
        intel = next(d for name, d in gpus.items() if "Intel" in name)
        assert intel.vendor == "Intel"

    def test_amd_long_vendor_normalised(self) -> None:
        stdout = "03:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi\n"
        gpus = _parse_lspci_output(stdout)
        (definition,) = gpus.values()
        assert definition.vendor == "AMD"

    def test_identical_gpus_counted(self) -> None:
        line = "01:00.0 3D controller: NVIDIA Corporation GA100\n"
        gpus = _parse_lspci_output(line * 3)
        (definition,) = gpus.values()
        assert definition.quantity == 3

    def test_non_gpu_lines_ignored(self) -> None:
        assert _parse_lspci_output("00:00.0 Host bridge: Intel\n") == {}


class TestProfileGpusDispatch:
    def test_prefers_nvidia_smi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str] | None:
            if args[0] == "nvidia-smi":
                return _completed("NVIDIA H100, 81920, 550.54, 00000000:07:00.0\n")
            raise AssertionError("lspci should not be consulted when nvidia-smi answers")

        monkeypatch.setattr(gpu_profiler, "run_command", fake)
        gpus = profile_gpus()
        assert "NVIDIA H100" in gpus

    def test_falls_back_to_lspci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str] | None:
            if args[0] == "nvidia-smi":
                return None  # binary absent
            return _completed("01:00.0 VGA compatible controller: Intel Corporation UHD 630\n")

        monkeypatch.setattr(gpu_profiler, "run_command", fake)
        gpus = profile_gpus()
        assert any("Intel" in name for name in gpus)

    def test_no_tools_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(gpu_profiler, "run_command", lambda *_a, **_k: None)
        assert profile_gpus() == {}

    def test_lspci_nonzero_return_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake(*args: str, **_kwargs: object) -> subprocess.CompletedProcess[str] | None:
            if args[0] == "nvidia-smi":
                return None
            return _completed("", returncode=1)

        monkeypatch.setattr(gpu_profiler, "run_command", fake)
        assert profile_gpus() == {}


class TestProfileStorageDispatch:
    def test_parses_command_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stdout = (
            '{"blockdevices": [{"name": "nvme0n1", "model": "WD SN770", '
            '"size": 500107862016, "rota": "0", "tran": "nvme", "type": "disk"}]}'
        )
        monkeypatch.setattr(storage_profiler, "run_command", lambda *_a, **_k: _completed(stdout))
        assert "WD SN770" in profile_storage()

    def test_missing_lsblk_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(storage_profiler, "run_command", lambda *_a, **_k: None)
        assert profile_storage() == {}

    def test_empty_output_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(storage_profiler, "run_command", lambda *_a, **_k: _completed("   "))
        assert profile_storage() == {}


class TestGenerateHbom:
    def test_smoke_returns_valid_hbom(self) -> None:
        # Runs the real profilers against the host; the exact hardware varies,
        # but the aggregate must always validate and carry the platform banner.
        hbom = generate_hbom()
        assert isinstance(hbom, HBOM)
        assert "platform_system" in hbom.extra_info
        # CPU profiling always yields at least the platform fallback entry.
        assert len(hbom.cpus) >= 1


class TestProfileNetwork:
    def _make_iface(self, net_root: Path, name: str, *, speed: str | None = None, wireless: bool = False) -> Path:
        iface = net_root / name
        (iface / "device").mkdir(parents=True)
        if speed is not None:
            (iface / "speed").write_text(speed)
        (iface / "type").write_text("1")
        if wireless:
            (iface / "wireless").mkdir()
        return iface

    def test_missing_root_is_empty(self, tmp_path: Path) -> None:
        assert profile_network(tmp_path / "absent") == {}

    def test_ethernet_with_speed(self, tmp_path: Path) -> None:
        net_root = tmp_path / "net"
        net_root.mkdir()
        iface = self._make_iface(net_root, "eth0", speed="10000")
        # A driver symlink resolves to its module name.
        driver = tmp_path / "drivers" / "ixgbe"
        driver.mkdir(parents=True)
        (iface / "device" / "driver").symlink_to(driver)

        network = profile_network(net_root)
        assert "ixgbe" in network
        definition = network["ixgbe"]
        assert definition.network_type == "ethernet"
        assert definition.bandwidth_gbps == 10.0
        assert definition.extra_info["speed_mbps"] == 10000

    def test_loopback_skipped(self, tmp_path: Path) -> None:
        net_root = tmp_path / "net"
        net_root.mkdir()
        self._make_iface(net_root, "lo")
        assert profile_network(net_root) == {}

    def test_wifi_classified(self, tmp_path: Path) -> None:
        net_root = tmp_path / "net"
        net_root.mkdir()
        self._make_iface(net_root, "wlan0", wireless=True)
        network = profile_network(net_root)
        (definition,) = network.values()
        assert definition.network_type == "wifi"
