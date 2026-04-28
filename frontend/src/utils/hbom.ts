import type {
  CPUDefinition,
  GPUDefinition,
  HBOM,
  MemoryDefinition,
  NetworkDefinition,
  StorageDefinition,
} from "../types";

export function emptyHBOM(): HBOM {
  return {
    cpus: {},
    gpus: {},
    memory: {},
    storage: {},
    network: {},
    extra_info: {},
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
            cores_per_cpu: asNumber(item.cores_per_cpu, 1),
            threads_per_core: asNumber(item.threads_per_core, 1),
            architecture: String(item.architecture ?? ""),
            extra_info: asRecord(item.extra_info),
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
            memory_gb: asNumber(item.memory_gb, 0),
            interface: String(item.interface ?? ""),
            extra_info: asRecord(item.extra_info),
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
            capacity_gb: asNumber(item.capacity_gb, 0),
            memory_type: String(item.memory_type ?? "DDR5"),
            speed_mt_s: asNumber(item.speed_mt_s, 1),
            extra_info: asRecord(item.extra_info),
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
            capacity_gb: asNumber(item.capacity_gb, 0),
            storage_type: String(item.storage_type ?? "NVMe"),
            interface: String(item.interface ?? ""),
            extra_info: asRecord(item.extra_info),
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
            bandwidth_gbps: asNumber(item.bandwidth_gbps, 0),
            network_type: String(item.network_type ?? "ethernet"),
            interface: String(item.interface ?? ""),
            extra_info: asRecord(item.extra_info),
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
      extra_info: record,
    };
  }
  return {
    cpus: normalizeCPUMap(record.cpus),
    gpus: normalizeGPUMap(record.gpus),
    memory: normalizeMemoryMap(record.memory),
    storage: normalizeStorageMap(record.storage),
    network: normalizeNetworkMap(record.network),
    extra_info: asRecord(record.extra_info),
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

export function hbomSummaryLines(hbom: HBOM): string[] {
  const lines: string[] = [];
  for (const [model, cpu] of Object.entries(hbom.cpus)) {
    lines.push(`CPU: ${model} x${cpu.quantity}`);
  }
  for (const [model, gpu] of Object.entries(hbom.gpus)) {
    lines.push(`GPU: ${model} x${gpu.quantity}`);
  }
  for (const [model, memory] of Object.entries(hbom.memory)) {
    lines.push(`Memory: ${model} x${memory.quantity}`);
  }
  for (const [model, storage] of Object.entries(hbom.storage)) {
    lines.push(`Storage: ${model} x${storage.quantity}`);
  }
  for (const [model, network] of Object.entries(hbom.network)) {
    lines.push(`Network: ${model} x${network.quantity}`);
  }
  return lines;
}
