import type { MemoryRow } from "@core/hbom/hardwareBomDraft";
import { MEMORY_TYPES } from "./hardwareBomColumns.constants";
import type { HardwareColumn, MemoryColumnsArgs } from "./hardwareBomColumns.types";

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
