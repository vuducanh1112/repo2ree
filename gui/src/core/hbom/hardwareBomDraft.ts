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

/** Rows the HBOM can represent: it is keyed by model, so a blank one cannot be. */
function named<TRow extends { model: string }>(rows: readonly TRow[] | undefined): TRow[] {
  return (rows ?? []).filter((row) => row.model.trim().length > 0);
}

/** Rows the author has added but not yet named — editing state, not HBOM state. */
function unnamed<TRow extends { model: string }>(rows: readonly TRow[] | undefined): TRow[] {
  return (rows ?? []).filter((row) => row.model.trim().length === 0);
}

/**
 * Project an HBOM onto the editable draft, carrying local editing state across.
 *
 * A just-added row has no model yet, and ``hbomFromDraft`` keys rows by model —
 * so such a row is invisible to the HBOM and would be erased by the next sync,
 * taking the author's half-finished input with it. Any sync can happen at any
 * moment (an unrelated intent save round-trips the whole document), so unnamed
 * rows are carried over rather than rebuilt. Ids for the synced rows come from
 * the previously *named* rows, which are the ones that line up by index.
 */
export function draftFromHBOM(hbom: Hbom, previous?: HardwareBomDraft): HardwareBomDraft {
  const previousCpus = named(previous?.cpus);
  const previousGpus = named(previous?.gpus);
  const previousMemory = named(previous?.memory);
  const previousStorage = named(previous?.storage);
  const previousNetwork = named(previous?.network);

  return {
    cpus: [
      ...Object.entries(hbom.cpus).map(([model, item], index) => ({
        id: previousCpus[index]?.id || `cpu-${index}`,
        model,
        ...item,
      })),
      ...unnamed(previous?.cpus),
    ],
    gpus: [
      ...Object.entries(hbom.gpus).map(([model, item], index) => ({
        id: previousGpus[index]?.id || `gpu-${index}`,
        model,
        ...item,
      })),
      ...unnamed(previous?.gpus),
    ],
    memory: [
      ...Object.entries(hbom.memory).map(([model, item], index) => ({
        id: previousMemory[index]?.id || `memory-${index}`,
        model,
        ...item,
      })),
      ...unnamed(previous?.memory),
    ],
    storage: [
      ...Object.entries(hbom.storage).map(([model, item], index) => ({
        id: previousStorage[index]?.id || `storage-${index}`,
        model,
        ...item,
      })),
      ...unnamed(previous?.storage),
    ],
    network: [
      ...Object.entries(hbom.network).map(([model, item], index) => ({
        id: previousNetwork[index]?.id || `network-${index}`,
        model,
        ...item,
      })),
      ...unnamed(previous?.network),
    ],
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
