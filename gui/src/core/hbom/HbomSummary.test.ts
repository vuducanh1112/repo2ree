/* biome-ignore-all lint/style/useNamingConvention: backend fixtures intentionally use wire field names */
import { describe, expect, it } from "vitest";
import { emptyHBOM, hbomHasAnyComponents, normalizeHBOM } from "./HbomSummary";

describe("HBOM normalization", () => {
  it("keeps legacy unstructured data as extra information", () => {
    expect(normalizeHBOM({ machine: "legacy", count: 2 })).toEqual({
      ...emptyHBOM(),
      extraInfo: { machine: "legacy", count: 2 },
    });
    expect(normalizeHBOM(null)).toEqual(emptyHBOM());
  });

  it("normalizes every structured component and applies safe defaults", () => {
    const hbom = normalizeHBOM({
      cpus: {
        "CPU X": {
          vendor: "Acme",
          quantity: 2,
          cores_per_cpu: 8,
          threads_per_core: 2,
          architecture: "x86",
          extra_info: { socket: "A" },
        },
        " ": {},
      },
      gpus: {
        "GPU X": {
          vendor: "Acme",
          quantity: Number.NaN,
          memory_bytes: 25769803776,
          interface: "PCIe",
          extra_info: [],
        },
      },
      memory: {
        DIMM: {
          vendor: "Acme",
          quantity: 4,
          capacity_bytes: 34359738368,
          memory_type: "DDR4",
          speed_mt_s: 3200,
        },
      },
      storage: {
        Disk: {
          vendor: "Acme",
          quantity: 2,
          capacity_bytes: 1099511627776,
          storage_type: "SSD",
          interface: "NVMe",
        },
      },
      network: {
        NIC: {
          vendor: "Acme",
          quantity: 1,
          bandwidth_mbps: 100000,
          network_type: "ethernet",
          interface: "PCIe",
        },
      },
      extra_info: { host: "lab" },
    });
    expect(hbom.cpus["CPU X"]).toMatchObject({ quantity: 2, coresPerCpu: 8, threadsPerCore: 2 });
    expect(hbom.gpus["GPU X"]).toMatchObject({ quantity: 1, memoryGb: 24, extraInfo: {} });
    expect(hbom.memory.DIMM).toMatchObject({ capacityGb: 32, speedMtS: 3200 });
    expect(hbom.storage.Disk).toMatchObject({ capacityGb: 1024, storageType: "SSD" });
    expect(hbom.network.NIC).toMatchObject({ bandwidthGbps: 100 });
    expect(hbomHasAnyComponents(hbom)).toBe(true);
    expect(hbomHasAnyComponents(emptyHBOM())).toBe(false);
  });
});
