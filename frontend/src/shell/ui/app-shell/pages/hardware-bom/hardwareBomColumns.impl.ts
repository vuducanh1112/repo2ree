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
    field: "cores_per_cpu",
    key: "cores",
    label: "Cores",
    width: "0.8fr",
    placeholder: "cores",
    min: 1,
  },
  {
    kind: "number",
    field: "threads_per_core",
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
    field: "memory_gb",
    key: "memory_gb",
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
    field: "capacity_gb",
    key: "capacity_gb",
    label: "Capacity GB",
    width: "1fr",
    placeholder: "capacity GB",
    min: 0,
  },
  {
    kind: "select",
    field: "memory_type",
    key: "memory_type",
    label: "Type",
    width: "1fr",
    options: MEMORY_TYPES,
  },
  {
    kind: "number",
    field: "speed_mt_s",
    key: "speed_mt_s",
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
    field: "capacity_gb",
    key: "capacity_gb",
    label: "Capacity GB",
    width: "1fr",
    placeholder: "capacity GB",
    min: 0,
  },
  {
    kind: "select",
    field: "storage_type",
    key: "storage_type",
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
    field: "bandwidth_gbps",
    key: "bandwidth_gbps",
    label: "Bandwidth Gbps",
    width: "1fr",
    placeholder: "bandwidth",
    min: 0,
  },
  {
    kind: "select",
    field: "network_type",
    key: "network_type",
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
  inp,
  selectInp,
  onFocusHardwareDescription,
  patchCpuRow,
}: CpuColumnsArgs): HardwareColumn<CPURow>[] {
  return buildColumns(cpuFields, patchCpuRow, {
    locked,
    inp,
    selectInp,
    onFocus: onFocusHardwareDescription,
  });
}

export function createGpuColumns({
  locked,
  inp,
  selectInp,
  patchGpuRow,
}: GpuColumnsArgs): HardwareColumn<GPURow>[] {
  return buildColumns(gpuFields, patchGpuRow, { locked, inp, selectInp });
}

export function createMemoryColumns({
  locked,
  inp,
  selectInp,
  patchMemoryRow,
}: MemoryColumnsArgs): HardwareColumn<MemoryRow>[] {
  return buildColumns(memoryFields, patchMemoryRow, { locked, inp, selectInp });
}

export function createStorageColumns({
  locked,
  inp,
  selectInp,
  patchStorageRow,
}: StorageColumnsArgs): HardwareColumn<StorageRow>[] {
  return buildColumns(storageFields, patchStorageRow, { locked, inp, selectInp });
}

export function createNetworkColumns({
  locked,
  inp,
  selectInp,
  patchNetworkRow,
}: NetworkColumnsArgs): HardwareColumn<NetworkRow>[] {
  return buildColumns(networkFields, patchNetworkRow, { locked, inp, selectInp });
}

export type { HardwareColumn } from "./hardwareBomColumns.types";
