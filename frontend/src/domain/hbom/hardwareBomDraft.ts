import type {
  CPUDefinition,
  GPUDefinition,
  HBOM,
  MemoryDefinition,
  NetworkDefinition,
  StorageDefinition,
} from "../ree/ReeSpec";
import { emptyHBOM } from "./HbomSummary";

export type CPURow = CPUDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};
export type GPURow = GPUDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};
export type MemoryRow = MemoryDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};
export type StorageRow = StorageDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};
export type NetworkRow = NetworkDefinition & {
  id: string;
  model: string;
  extra_info: Record<string, unknown>;
};

export interface HardwareBomDraft {
  cpus: CPURow[];
  gpus: GPURow[];
  memory: MemoryRow[];
  storage: StorageRow[];
  network: NetworkRow[];
}

type GenerateRowId = (prefix: string) => string;

export function newCpuRow(generateId: GenerateRowId): CPURow {
  return {
    id: generateId("cpu"),
    model: "",
    vendor: "",
    quantity: 1,
    cores_per_cpu: 1,
    threads_per_core: 1,
    architecture: "",
    extra_info: {},
  };
}

export function newGpuRow(generateId: GenerateRowId): GPURow {
  return {
    id: generateId("gpu"),
    model: "",
    vendor: "",
    quantity: 1,
    memory_gb: 0,
    interface: "",
    extra_info: {},
  };
}

export function newMemoryRow(generateId: GenerateRowId): MemoryRow {
  return {
    id: generateId("memory"),
    model: "",
    vendor: "",
    quantity: 1,
    capacity_gb: 0,
    memory_type: "DDR5",
    speed_mt_s: 1,
    extra_info: {},
  };
}

export function newStorageRow(generateId: GenerateRowId): StorageRow {
  return {
    id: generateId("storage"),
    model: "",
    vendor: "",
    quantity: 1,
    capacity_gb: 0,
    storage_type: "NVMe",
    interface: "",
    extra_info: {},
  };
}

export function newNetworkRow(generateId: GenerateRowId): NetworkRow {
  return {
    id: generateId("network"),
    model: "",
    vendor: "",
    quantity: 1,
    bandwidth_gbps: 0,
    network_type: "ethernet",
    interface: "",
    extra_info: {},
  };
}

export function draftFromHBOM(hbom: HBOM, previous?: HardwareBomDraft): HardwareBomDraft {
  return {
    cpus: Object.entries(hbom.cpus).map(([model, item], index) => ({
      id: previous?.cpus[index]?.id || `cpu-${index}`,
      model,
      ...item,
    })),
    gpus: Object.entries(hbom.gpus).map(([model, item], index) => ({
      id: previous?.gpus[index]?.id || `gpu-${index}`,
      model,
      ...item,
    })),
    memory: Object.entries(hbom.memory).map(([model, item], index) => ({
      id: previous?.memory[index]?.id || `memory-${index}`,
      model,
      ...item,
    })),
    storage: Object.entries(hbom.storage).map(([model, item], index) => ({
      id: previous?.storage[index]?.id || `storage-${index}`,
      model,
      ...item,
    })),
    network: Object.entries(hbom.network).map(([model, item], index) => ({
      id: previous?.network[index]?.id || `network-${index}`,
      model,
      ...item,
    })),
  };
}

function parsePositiveInt(value: number): number | null {
  return Number.isFinite(value) && value >= 1 ? Math.floor(value) : null;
}

function parsePositiveNumber(value: number): number | null {
  return Number.isFinite(value) && value > 0 ? value : null;
}

export function hbomFromDraft(draft: HardwareBomDraft, previousHBOM: HBOM): HBOM {
  const nextHBOM = emptyHBOM();
  nextHBOM.extra_info = previousHBOM.extra_info || {};

  for (const row of draft.cpus) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.cpus[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        cores_per_cpu: parsePositiveInt(row.cores_per_cpu) ?? 1,
        threads_per_core: parsePositiveInt(row.threads_per_core) ?? 1,
        architecture: row.architecture.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.gpus) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.gpus[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        memory_gb: parsePositiveNumber(row.memory_gb) ?? 0,
        interface: row.interface.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.memory) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.memory[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        capacity_gb: parsePositiveNumber(row.capacity_gb) ?? 0,
        memory_type: row.memory_type,
        speed_mt_s: parsePositiveInt(row.speed_mt_s) ?? 0,
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.storage) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.storage[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        capacity_gb: parsePositiveNumber(row.capacity_gb) ?? 0,
        storage_type: row.storage_type,
        interface: row.interface.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  for (const row of draft.network) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.network[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        bandwidth_gbps: parsePositiveNumber(row.bandwidth_gbps) ?? 0,
        network_type: row.network_type,
        interface: row.interface.trim(),
        extra_info: row.extra_info,
      };
    }
  }

  return nextHBOM;
}

export function hbomSyncKey(hbom: HBOM): string {
  return JSON.stringify(hbom);
}
