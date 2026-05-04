import type { StorageRow } from "../../../../domain/hbom/hardwareBomDraft";
import { STORAGE_TYPES } from "./hardwareBomColumns.constants";
import type { HardwareColumn, StorageColumnsArgs } from "./hardwareBomColumns.types";

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
