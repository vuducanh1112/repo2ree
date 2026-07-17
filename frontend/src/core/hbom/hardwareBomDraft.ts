import type {
  CPUDefinition,
  GPUDefinition,
  Hbom,
  MemoryDefinition,
  NetworkDefinition,
  StorageDefinition,
} from "../ree/ReeSpec";
import { emptyHBOM } from "./HbomSummary";

export type CPURow = CPUDefinition & {
  id: string;
  model: string;
  extraInfo: Record<string, unknown>;
};
export type GPURow = GPUDefinition & {
  id: string;
  model: string;
  extraInfo: Record<string, unknown>;
};
export type MemoryRow = MemoryDefinition & {
  id: string;
  model: string;
  extraInfo: Record<string, unknown>;
};
export type StorageRow = StorageDefinition & {
  id: string;
  model: string;
  extraInfo: Record<string, unknown>;
};
export type NetworkRow = NetworkDefinition & {
  id: string;
  model: string;
  extraInfo: Record<string, unknown>;
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
    coresPerCpu: 1,
    threadsPerCore: 1,
    architecture: "",
    extraInfo: {},
  };
}

export function newGpuRow(generateId: GenerateRowId): GPURow {
  return {
    id: generateId("gpu"),
    model: "",
    vendor: "",
    quantity: 1,
    memoryGb: 0,
    interface: "",
    extraInfo: {},
  };
}

export function newMemoryRow(generateId: GenerateRowId): MemoryRow {
  return {
    id: generateId("memory"),
    model: "",
    vendor: "",
    quantity: 1,
    capacityGb: 0,
    memoryType: "DDR5",
    speedMtS: 1,
    extraInfo: {},
  };
}

export function newStorageRow(generateId: GenerateRowId): StorageRow {
  return {
    id: generateId("storage"),
    model: "",
    vendor: "",
    quantity: 1,
    capacityGb: 0,
    storageType: "NVMe",
    interface: "",
    extraInfo: {},
  };
}

export function newNetworkRow(generateId: GenerateRowId): NetworkRow {
  return {
    id: generateId("network"),
    model: "",
    vendor: "",
    quantity: 1,
    bandwidthGbps: 0,
    networkType: "ethernet",
    interface: "",
    extraInfo: {},
  };
}

export function draftFromHBOM(hbom: Hbom, previous?: HardwareBomDraft): HardwareBomDraft {
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

export function hbomFromDraft(draft: HardwareBomDraft, previousHBOM: Hbom): Hbom {
  const nextHBOM = emptyHBOM();
  nextHBOM.extraInfo = previousHBOM.extraInfo || {};

  for (const row of draft.cpus) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.cpus[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        coresPerCpu: parsePositiveInt(row.coresPerCpu) ?? 1,
        threadsPerCore: parsePositiveInt(row.threadsPerCore) ?? 1,
        architecture: row.architecture.trim(),
        extraInfo: row.extraInfo,
      };
    }
  }

  for (const row of draft.gpus) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.gpus[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        memoryGb: parsePositiveNumber(row.memoryGb) ?? 0,
        interface: row.interface.trim(),
        extraInfo: row.extraInfo,
      };
    }
  }

  for (const row of draft.memory) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.memory[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        capacityGb: parsePositiveNumber(row.capacityGb) ?? 0,
        memoryType: row.memoryType,
        speedMtS: parsePositiveInt(row.speedMtS) ?? 0,
        extraInfo: row.extraInfo,
      };
    }
  }

  for (const row of draft.storage) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.storage[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        capacityGb: parsePositiveNumber(row.capacityGb) ?? 0,
        storageType: row.storageType,
        interface: row.interface.trim(),
        extraInfo: row.extraInfo,
      };
    }
  }

  for (const row of draft.network) {
    const model = row.model.trim();
    if (model) {
      nextHBOM.network[model] = {
        vendor: row.vendor.trim(),
        quantity: parsePositiveInt(row.quantity) ?? 1,
        bandwidthGbps: parsePositiveNumber(row.bandwidthGbps) ?? 0,
        networkType: row.networkType,
        interface: row.interface.trim(),
        extraInfo: row.extraInfo,
      };
    }
  }

  return nextHBOM;
}

export function hbomSyncKey(hbom: Hbom): string {
  return JSON.stringify(hbom);
}
