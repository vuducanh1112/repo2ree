import type React from "react";
import type {
  CPURow,
  GPURow,
  MemoryRow,
  NetworkRow,
  StorageRow,
} from "../../../../domain/hbom/hardwareBomDraft";

export interface HardwareColumn<RowT> {
  key: string;
  label: string;
  width: string;
  render: (row: RowT, index: number) => React.ReactNode;
}

interface ColumnBuilderBaseArgs {
  locked: boolean;
  inp: (locked: boolean, extra?: React.CSSProperties) => React.CSSProperties;
  selectInp: (locked: boolean, extra?: React.CSSProperties) => React.CSSProperties;
}

interface CpuColumnsArgs extends ColumnBuilderBaseArgs {
  onFocusHardwareDescription: () => void;
  patchCpuRow: (index: number, patch: Partial<CPURow>) => void;
}

interface GpuColumnsArgs extends ColumnBuilderBaseArgs {
  patchGpuRow: (index: number, patch: Partial<GPURow>) => void;
}

interface MemoryColumnsArgs extends ColumnBuilderBaseArgs {
  patchMemoryRow: (index: number, patch: Partial<MemoryRow>) => void;
}

interface StorageColumnsArgs extends ColumnBuilderBaseArgs {
  patchStorageRow: (index: number, patch: Partial<StorageRow>) => void;
}

interface NetworkColumnsArgs extends ColumnBuilderBaseArgs {
  patchNetworkRow: (index: number, patch: Partial<NetworkRow>) => void;
}

const MEMORY_TYPES = ["DDR3", "DDR4", "DDR5", "LPDDR4", "LPDDR5", "HBM2", "HBM2e", "HBM3"];
const STORAGE_TYPES = ["HDD", "SSD", "NVMe", "eMMC", "SD"];
const NETWORK_TYPES = ["ethernet", "infiniband", "wifi", "cellular"];

export function createCpuColumns({
  locked,
  inp,
  onFocusHardwareDescription,
  patchCpuRow,
}: CpuColumnsArgs): HardwareColumn<CPURow>[] {
  return [
    {
      key: "model",
      label: "Device Model",
      width: "1.7fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) => patchCpuRow(index, { model: event.target.value })}
          onFocus={onFocusHardwareDescription}
          placeholder="Intel Core i9-14900K"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) => patchCpuRow(index, { vendor: event.target.value })}
          placeholder="Intel"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) => patchCpuRow(index, { quantity: Number(event.target.value) })}
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "cores",
      label: "Cores",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.cores_per_cpu}
          onChange={(event) => patchCpuRow(index, { cores_per_cpu: Number(event.target.value) })}
          placeholder="cores"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "threads",
      label: "Threads/Core",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.threads_per_core}
          onChange={(event) => patchCpuRow(index, { threads_per_core: Number(event.target.value) })}
          placeholder="threads/core"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "architecture",
      label: "Architecture",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.architecture}
          onChange={(event) => patchCpuRow(index, { architecture: event.target.value })}
          placeholder="x86_64"
          style={inp(locked)}
        />
      ),
    },
  ];
}

export function createGpuColumns({
  locked,
  inp,
  patchGpuRow,
}: GpuColumnsArgs): HardwareColumn<GPURow>[] {
  return [
    {
      key: "model",
      label: "Device Model",
      width: "1.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) => patchGpuRow(index, { model: event.target.value })}
          placeholder="NVIDIA A100-SXM4-40GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) => patchGpuRow(index, { vendor: event.target.value })}
          placeholder="NVIDIA"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) => patchGpuRow(index, { quantity: Number(event.target.value) })}
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "memory_gb",
      label: "Memory GB",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.memory_gb}
          onChange={(event) => patchGpuRow(index, { memory_gb: Number(event.target.value) })}
          placeholder="memory GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "interface",
      label: "Interface",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.interface}
          onChange={(event) => patchGpuRow(index, { interface: event.target.value })}
          placeholder="PCIe 4.0 x16"
          style={inp(locked)}
        />
      ),
    },
  ];
}

export function createMemoryColumns({
  locked,
  inp,
  selectInp,
  patchMemoryRow,
}: MemoryColumnsArgs): HardwareColumn<MemoryRow>[] {
  return [
    {
      key: "model",
      label: "Device Model",
      width: "1.7fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) => patchMemoryRow(index, { model: event.target.value })}
          placeholder="DDR5 ECC 32GB DIMM"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) => patchMemoryRow(index, { vendor: event.target.value })}
          placeholder="Samsung"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) => patchMemoryRow(index, { quantity: Number(event.target.value) })}
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "capacity_gb",
      label: "Capacity GB",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.capacity_gb}
          onChange={(event) => patchMemoryRow(index, { capacity_gb: Number(event.target.value) })}
          placeholder="capacity GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "memory_type",
      label: "Type",
      width: "1fr",
      render: (row, index) => (
        <select
          disabled={locked}
          value={row.memory_type}
          onChange={(event) => patchMemoryRow(index, { memory_type: event.target.value })}
          style={selectInp(locked)}
        >
          {MEMORY_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "speed_mt_s",
      label: "Speed MT/s",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.speed_mt_s}
          onChange={(event) => patchMemoryRow(index, { speed_mt_s: Number(event.target.value) })}
          placeholder="speed MT/s"
          style={inp(locked)}
        />
      ),
    },
  ];
}

export function createStorageColumns({
  locked,
  inp,
  selectInp,
  patchStorageRow,
}: StorageColumnsArgs): HardwareColumn<StorageRow>[] {
  return [
    {
      key: "model",
      label: "Device Model",
      width: "1.7fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) => patchStorageRow(index, { model: event.target.value })}
          placeholder="Samsung PM9A3"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) => patchStorageRow(index, { vendor: event.target.value })}
          placeholder="Samsung"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) => patchStorageRow(index, { quantity: Number(event.target.value) })}
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "capacity_gb",
      label: "Capacity GB",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.capacity_gb}
          onChange={(event) => patchStorageRow(index, { capacity_gb: Number(event.target.value) })}
          placeholder="capacity GB"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "storage_type",
      label: "Type",
      width: "1fr",
      render: (row, index) => (
        <select
          disabled={locked}
          value={row.storage_type}
          onChange={(event) => patchStorageRow(index, { storage_type: event.target.value })}
          style={selectInp(locked)}
        >
          {STORAGE_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "interface",
      label: "Interface",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.interface}
          onChange={(event) => patchStorageRow(index, { interface: event.target.value })}
          placeholder="PCIe 4.0 x4"
          style={inp(locked)}
        />
      ),
    },
  ];
}

export function createNetworkColumns({
  locked,
  inp,
  selectInp,
  patchNetworkRow,
}: NetworkColumnsArgs): HardwareColumn<NetworkRow>[] {
  return [
    {
      key: "model",
      label: "Device Model",
      width: "1.6fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.model}
          onChange={(event) => patchNetworkRow(index, { model: event.target.value })}
          placeholder="ConnectX-6"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "vendor",
      label: "Vendor",
      width: "1.1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.vendor}
          onChange={(event) => patchNetworkRow(index, { vendor: event.target.value })}
          placeholder="NVIDIA"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "quantity",
      label: "Qty",
      width: "0.8fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={1}
          value={row.quantity}
          onChange={(event) => patchNetworkRow(index, { quantity: Number(event.target.value) })}
          placeholder="qty"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "bandwidth_gbps",
      label: "Bandwidth Gbps",
      width: "1fr",
      render: (row, index) => (
        <input
          disabled={locked}
          type="number"
          min={0}
          value={row.bandwidth_gbps}
          onChange={(event) =>
            patchNetworkRow(index, { bandwidth_gbps: Number(event.target.value) })
          }
          placeholder="bandwidth"
          style={inp(locked)}
        />
      ),
    },
    {
      key: "network_type",
      label: "Type",
      width: "1fr",
      render: (row, index) => (
        <select
          disabled={locked}
          value={row.network_type}
          onChange={(event) => patchNetworkRow(index, { network_type: event.target.value })}
          style={selectInp(locked)}
        >
          {NETWORK_TYPES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "interface",
      label: "Interface",
      width: "1.2fr",
      render: (row, index) => (
        <input
          disabled={locked}
          value={row.interface}
          onChange={(event) => patchNetworkRow(index, { interface: event.target.value })}
          placeholder="PCIe 4.0 x8"
          style={inp(locked)}
        />
      ),
    },
  ];
}
