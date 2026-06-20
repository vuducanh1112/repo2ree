import type { CPURow } from "@core/hbom/hardwareBomDraft";
import type { CpuColumnsArgs, HardwareColumn } from "./hardwareBomColumns.types";

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
