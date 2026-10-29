from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

DeviceModel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class CPUDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(
        default="",
        description="CPU manufacturer, for example Intel or AMD.",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of identical CPU packages installed in the machine.",
    )
    cores_per_cpu: int = Field(
        default=1,
        ge=1,
        description="Number of physical CPU cores provided by one CPU package.",
    )
    threads_per_core: int = Field(
        default=1,
        ge=1,
        description="Hardware threads exposed by each physical CPU core.",
    )
    architecture: str = Field(
        default="",
        description="Instruction set architecture, for example x86_64 or arm64.",
    )
    extra_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional CPU metadata that does not fit the structured CPU schema.",
    )


class GPUDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(
        default="",
        description="GPU manufacturer, for example NVIDIA or AMD.",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of identical GPUs installed in the machine.",
    )
    memory_gb: float = Field(
        default=0,
        ge=0,
        description="On-board memory capacity of one GPU in gibibytes/gigabytes as recorded.",
    )
    interface: str = Field(
        default="",
        description="Host interconnect used by the GPU, for example PCIe 4.0 x16 or SXM4.",
    )
    extra_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional GPU metadata that does not fit the structured GPU schema.",
    )


class MemoryDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(
        default="",
        description="Memory module manufacturer, for example Samsung or Micron.",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of identical memory modules installed in the machine.",
    )
    capacity_gb: float = Field(
        default=0,
        ge=0,
        description="Capacity of one memory module in gibibytes/gigabytes as recorded.",
    )
    memory_type: Literal["DDR3", "DDR4", "DDR5", "LPDDR4", "LPDDR5", "HBM2", "HBM2e", "HBM3"] = Field(
        default="DDR5", description="Memory technology used by the module."
    )
    speed_mt_s: int = Field(
        default=0,
        ge=0,
        description="Rated transfer speed of one memory module in MT/s.",
    )
    extra_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional memory metadata that does not fit the structured memory schema.",
    )


class StorageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(
        default="",
        description="Storage device manufacturer, for example Samsung or Seagate.",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of identical storage devices installed in the machine.",
    )
    capacity_gb: float = Field(
        default=0,
        ge=0,
        description="Capacity of one storage device in gibibytes/gigabytes as recorded.",
    )
    storage_type: Literal["HDD", "SSD", "NVMe", "eMMC", "SD"] = Field(
        default="NVMe", description="Storage technology used by the device."
    )
    interface: str = Field(
        default="",
        description="Physical or logical interface, for example SATA III, U.2, or PCIe 5.0 x4.",
    )
    extra_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional storage metadata that does not fit the structured storage schema.",
    )


class NetworkDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor: str = Field(
        default="",
        description="Network interface manufacturer, for example Intel, Broadcom, or Mellanox.",
    )
    quantity: int = Field(
        default=1,
        ge=1,
        description="Number of identical network interfaces installed in the machine.",
    )
    bandwidth_gbps: float = Field(
        default=0,
        ge=0,
        description="Nominal bandwidth of one interface in gigabits per second.",
    )
    network_type: Literal["ethernet", "infiniband", "wifi", "cellular"] = Field(
        default="ethernet",
        description="Network technology implemented by the interface.",
    )
    interface: str = Field(
        default="",
        description="Connector or bus used by the interface, for example PCIe 4.0 x8 or M.2 E-key.",
    )
    extra_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional network metadata that does not fit the structured network schema.",
    )


class HBOM(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpus: dict[DeviceModel, CPUDefinition] = Field(default_factory=dict)
    gpus: dict[DeviceModel, GPUDefinition] = Field(default_factory=dict)
    memory: dict[DeviceModel, MemoryDefinition] = Field(default_factory=dict)
    storage: dict[DeviceModel, StorageDefinition] = Field(default_factory=dict)
    network: dict[DeviceModel, NetworkDefinition] = Field(default_factory=dict)
    extra_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional machine-level metadata that does not fit the structured HBOM schema.",
    )

    @model_validator(mode="after")
    def validate_component_keys(self) -> HBOM:
        for field_name in ("cpus", "gpus", "memory", "storage", "network"):
            components = getattr(self, field_name)
            for model_name in components:
                if not model_name.strip():
                    raise ValueError(f"{field_name} contains an empty model key")
        return self
