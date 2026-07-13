import type {
  CPUDefinition,
  GPUDefinition,
  HBOM,
  MemoryDefinition,
  NetworkDefinition,
  StorageDefinition,
} from "../ree/ReeSpec";

export function emptyHBOM(): HBOM {
  return {
    cpus: {},
    gpus: {},
    memory: {},
    storage: {},
    network: {},
    extraInfo: {},
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function normalizeCPUMap(raw: unknown): Record<string, CPUDefinition> {
  const record = asRecord(raw);
  return Object.fromEntries(
    Object.entries(record)
      .filter(([model]) => model.trim())
      .map(([model, value]) => {
        const item = asRecord(value);
        return [
          model,
          {
            vendor: String(item.vendor ?? ""),
            quantity: asNumber(item.quantity, 1),
            coresPerCpu: asNumber(item.cores_per_cpu, 1),
            threadsPerCore: asNumber(item.threads_per_core, 1),
            architecture: String(item.architecture ?? ""),
            extraInfo: asRecord(item.extra_info),
          },
        ];
      }),
  );
}

function normalizeGPUMap(raw: unknown): Record<string, GPUDefinition> {
  const record = asRecord(raw);
  return Object.fromEntries(
    Object.entries(record)
      .filter(([model]) => model.trim())
      .map(([model, value]) => {
        const item = asRecord(value);
        return [
          model,
          {
            vendor: String(item.vendor ?? ""),
            quantity: asNumber(item.quantity, 1),
            memoryGb: asNumber(item.memory_gb, 0),
            interface: String(item.interface ?? ""),
            extraInfo: asRecord(item.extra_info),
          },
        ];
      }),
  );
}

function normalizeMemoryMap(raw: unknown): Record<string, MemoryDefinition> {
  const record = asRecord(raw);
  return Object.fromEntries(
    Object.entries(record)
      .filter(([model]) => model.trim())
      .map(([model, value]) => {
        const item = asRecord(value);
        return [
          model,
          {
            vendor: String(item.vendor ?? ""),
            quantity: asNumber(item.quantity, 1),
            capacityGb: asNumber(item.capacity_gb, 0),
            memoryType: String(item.memory_type ?? "DDR5"),
            speedMtS: asNumber(item.speed_mt_s, 1),
            extraInfo: asRecord(item.extra_info),
          },
        ];
      }),
  );
}

function normalizeStorageMap(raw: unknown): Record<string, StorageDefinition> {
  const record = asRecord(raw);
  return Object.fromEntries(
    Object.entries(record)
      .filter(([model]) => model.trim())
      .map(([model, value]) => {
        const item = asRecord(value);
        return [
          model,
          {
            vendor: String(item.vendor ?? ""),
            quantity: asNumber(item.quantity, 1),
            capacityGb: asNumber(item.capacity_gb, 0),
            storageType: String(item.storage_type ?? "NVMe"),
            interface: String(item.interface ?? ""),
            extraInfo: asRecord(item.extra_info),
          },
        ];
      }),
  );
}

function normalizeNetworkMap(raw: unknown): Record<string, NetworkDefinition> {
  const record = asRecord(raw);
  return Object.fromEntries(
    Object.entries(record)
      .filter(([model]) => model.trim())
      .map(([model, value]) => {
        const item = asRecord(value);
        return [
          model,
          {
            vendor: String(item.vendor ?? ""),
            quantity: asNumber(item.quantity, 1),
            bandwidthGbps: asNumber(item.bandwidth_gbps, 0),
            networkType: String(item.network_type ?? "ethernet"),
            interface: String(item.interface ?? ""),
            extraInfo: asRecord(item.extra_info),
          },
        ];
      }),
  );
}

export function normalizeHBOM(raw: unknown): HBOM {
  const record = asRecord(raw);
  const hasStructuredKeys = ["cpus", "gpus", "memory", "storage", "network", "extra_info"].some(
    (key) => key in record,
  );
  if (!hasStructuredKeys) {
    return {
      ...emptyHBOM(),
      extraInfo: record,
    };
  }
  return {
    cpus: normalizeCPUMap(record.cpus),
    gpus: normalizeGPUMap(record.gpus),
    memory: normalizeMemoryMap(record.memory),
    storage: normalizeStorageMap(record.storage),
    network: normalizeNetworkMap(record.network),
    extraInfo: asRecord(record.extra_info),
  };
}

export function hbomHasAnyComponents(hbom: HBOM): boolean {
  return (
    Object.keys(hbom.cpus).length +
      Object.keys(hbom.gpus).length +
      Object.keys(hbom.memory).length +
      Object.keys(hbom.storage).length +
      Object.keys(hbom.network).length >
    0
  );
}
