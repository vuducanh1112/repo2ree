import type { NetworkRow } from "@core/hbom/hardwareBomDraft";
import { NETWORK_TYPES } from "./hardwareBomColumns.constants";
import type { HardwareColumn, NetworkColumnsArgs } from "./hardwareBomColumns.types";

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
