import type {
  CPURow,
  GPURow,
  MemoryRow,
  NetworkRow,
  StorageRow,
} from "@core/hbom/hardwareBomDraft";
import { MEMORY_TYPES, NETWORK_TYPES, STORAGE_TYPES } from "./hardwareBomColumns.constants";
import { buildColumns, type FieldSpec } from "./hardwareBomColumns.fields";
import type {
  CpuColumnsArgs,
  GpuColumnsArgs,
  HardwareColumn,
  MemoryColumnsArgs,
  NetworkColumnsArgs,
  StorageColumnsArgs,
} from "./hardwareBomColumns.types";

const cpuFields: FieldSpec<CPURow>[] = [
  {
    kind: "text",
    field: "model",
    key: "model",
    label: "Device Model",
    width: "1.7fr",
    placeholder: "Intel Core i9-14900K",
    focusOnEdit: true,
  },
  {
    kind: "text",
    field: "vendor",
    key: "vendor",
    label: "Vendor",
    width: "1.2fr",
    placeholder: "Intel",
  },
  {
    kind: "number",
    field: "quantity",
    key: "quantity",
    label: "Qty",
    width: "0.8fr",
    placeholder: "qty",
    min: 1,
  },
  {
    kind: "number",
    field: "coresPerCpu",
    key: "cores",
    label: "Cores",
    width: "0.8fr",
    placeholder: "cores",
    min: 1,
  },
  {
    kind: "number",
    field: "threadsPerCore",
    key: "threads",
    label: "Threads/Core",
    width: "1fr",
    placeholder: "threads/core",
    min: 1,
  },
  {
    kind: "text",
    field: "architecture",
    key: "architecture",
    label: "Architecture",
    width: "1fr",
    placeholder: "x86_64",
  },
];

const gpuFields: FieldSpec<GPURow>[] = [
  {
    kind: "text",
    field: "model",
    key: "model",
    label: "Device Model",
    width: "1.8fr",
    placeholder: "NVIDIA A100-SXM4-40GB",
  },
  {
    kind: "text",
    field: "vendor",
    key: "vendor",
    label: "Vendor",
    width: "1.2fr",
    placeholder: "NVIDIA",
  },
  {
    kind: "number",
    field: "quantity",
    key: "quantity",
    label: "Qty",
    width: "0.8fr",
    placeholder: "qty",
    min: 1,
  },
  {
    kind: "number",
    field: "memoryGb",
    key: "memoryGb",
    label: "Memory GB",
    width: "1fr",
    placeholder: "memory GB",
    min: 0,
  },
  {
    kind: "text",
    field: "interface",
    key: "interface",
    label: "Interface",
    width: "1.2fr",
    placeholder: "PCIe 4.0 x16",
  },
];

const memoryFields: FieldSpec<MemoryRow>[] = [
  {
    kind: "text",
    field: "model",
    key: "model",
    label: "Device Model",
    width: "1.7fr",
    placeholder: "DDR5 ECC 32GB DIMM",
  },
  {
    kind: "text",
    field: "vendor",
    key: "vendor",
    label: "Vendor",
    width: "1.1fr",
    placeholder: "Samsung",
  },
  {
    kind: "number",
    field: "quantity",
    key: "quantity",
    label: "Qty",
    width: "0.8fr",
    placeholder: "qty",
    min: 1,
  },
  {
    kind: "number",
    field: "capacityGb",
    key: "capacityGb",
    label: "Capacity GB",
    width: "1fr",
    placeholder: "capacity GB",
    min: 0,
  },
  {
    kind: "select",
    field: "memoryType",
    key: "memoryType",
    label: "Type",
    width: "1fr",
    options: MEMORY_TYPES,
  },
  {
    kind: "number",
    field: "speedMtS",
    key: "speedMtS",
    label: "Speed MT/s",
    width: "1fr",
    placeholder: "speed MT/s",
    min: 1,
  },
];

const storageFields: FieldSpec<StorageRow>[] = [
  {
    kind: "text",
    field: "model",
    key: "model",
    label: "Device Model",
    width: "1.7fr",
    placeholder: "Samsung PM9A3",
  },
  {
    kind: "text",
    field: "vendor",
    key: "vendor",
    label: "Vendor",
    width: "1.1fr",
    placeholder: "Samsung",
  },
  {
    kind: "number",
    field: "quantity",
    key: "quantity",
    label: "Qty",
    width: "0.8fr",
    placeholder: "qty",
    min: 1,
  },
  {
    kind: "number",
    field: "capacityGb",
    key: "capacityGb",
    label: "Capacity GB",
    width: "1fr",
    placeholder: "capacity GB",
    min: 0,
  },
  {
    kind: "select",
    field: "storageType",
    key: "storageType",
    label: "Type",
    width: "1fr",
    options: STORAGE_TYPES,
  },
  {
    kind: "text",
    field: "interface",
    key: "interface",
    label: "Interface",
    width: "1.2fr",
    placeholder: "PCIe 4.0 x4",
  },
];

const networkFields: FieldSpec<NetworkRow>[] = [
  {
    kind: "text",
    field: "model",
    key: "model",
    label: "Device Model",
    width: "1.6fr",
    placeholder: "ConnectX-6",
  },
  {
    kind: "text",
    field: "vendor",
    key: "vendor",
    label: "Vendor",
    width: "1.1fr",
    placeholder: "NVIDIA",
  },
  {
    kind: "number",
    field: "quantity",
    key: "quantity",
    label: "Qty",
    width: "0.8fr",
    placeholder: "qty",
    min: 1,
  },
  {
    kind: "number",
    field: "bandwidthGbps",
    key: "bandwidthGbps",
    label: "Bandwidth Gbps",
    width: "1fr",
    placeholder: "bandwidth",
    min: 0,
  },
  {
    kind: "select",
    field: "networkType",
    key: "networkType",
    label: "Type",
    width: "1fr",
    options: NETWORK_TYPES,
  },
  {
    kind: "text",
    field: "interface",
    key: "interface",
    label: "Interface",
    width: "1.2fr",
    placeholder: "PCIe 4.0 x8",
  },
];

export function createCpuColumns({
  locked,
  onFocusHardwareDescription,
  patchCpuRow,
}: CpuColumnsArgs): HardwareColumn<CPURow>[] {
  return buildColumns(cpuFields, patchCpuRow, {
    locked,
    onFocus: onFocusHardwareDescription,
  });
}

export function createGpuColumns({
  locked,
  patchGpuRow,
}: GpuColumnsArgs): HardwareColumn<GPURow>[] {
  return buildColumns(gpuFields, patchGpuRow, { locked });
}

export function createMemoryColumns({
  locked,
  patchMemoryRow,
}: MemoryColumnsArgs): HardwareColumn<MemoryRow>[] {
  return buildColumns(memoryFields, patchMemoryRow, { locked });
}

export function createStorageColumns({
  locked,
  patchStorageRow,
}: StorageColumnsArgs): HardwareColumn<StorageRow>[] {
  return buildColumns(storageFields, patchStorageRow, { locked });
}

export function createNetworkColumns({
  locked,
  patchNetworkRow,
}: NetworkColumnsArgs): HardwareColumn<NetworkRow>[] {
  return buildColumns(networkFields, patchNetworkRow, { locked });
}

export type { HardwareColumn } from "./hardwareBomColumns.types";
