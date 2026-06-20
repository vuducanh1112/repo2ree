import type { GPURow } from "@core/hbom/hardwareBomDraft";
import type { GpuColumnsArgs, HardwareColumn } from "./hardwareBomColumns.types";

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
