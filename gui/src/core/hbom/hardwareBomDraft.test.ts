import { describe, expect, it } from "vitest";
import { emptyHBOM } from "./HbomSummary";
import {
  draftFromHBOM,
  hbomFromDraft,
  hbomSyncKey,
  newCpuRow,
  newGpuRow,
  newMemoryRow,
  newNetworkRow,
  newStorageRow,
} from "./hardwareBomDraft";

describe("hardwareBomDraft", () => {
  it("round-trips model-keyed HBOM entries through draft conversion", () => {
    const hbom = emptyHBOM();
    hbom.cpus["Intel Xeon Gold 6348"] = {
      vendor: "Intel",
      quantity: 2,
      coresPerCpu: 28,
      threadsPerCore: 2,
      architecture: "x86_64",
      extraInfo: { stepping: "B1" },
    };
    hbom.extraInfo = { source: "manual" };

    const draft = draftFromHBOM(hbom);
    const rebuilt = hbomFromDraft(draft, hbom);

    expect(rebuilt).toEqual(hbom);
  });

  it("drops rows with empty model and normalizes invalid numeric values", () => {
    const hbom = emptyHBOM();
    const cpu = newCpuRow((prefix) => `${prefix}-test`);
    const draft = {
      cpus: [{ ...cpu, model: "  ", quantity: 0, coresPerCpu: Number.NaN, threadsPerCore: -1 }],
      gpus: [],
      memory: [],
      storage: [],
      network: [],
    };

    const rebuilt = hbomFromDraft(draft, hbom);
    expect(rebuilt.cpus).toEqual({});
  });

  it("carries an unnamed row across a sync so a fresh row survives an unrelated save", () => {
    const hbom = emptyHBOM();
    hbom.cpus["Intel Xeon Gold 6348"] = {
      vendor: "Intel",
      quantity: 1,
      coresPerCpu: 28,
      threadsPerCore: 2,
      architecture: "x86_64",
      extraInfo: {},
    };
    const previous = draftFromHBOM(hbom);
    // The author clicks "Add CPU" and has not typed a model yet.
    previous.cpus.push(newCpuRow(() => "cpu-fresh"));

    // Any document refetch re-projects the (unchanged) HBOM onto the draft.
    const synced = draftFromHBOM(hbom, previous);

    expect(synced.cpus.map((row) => row.id)).toEqual([previous.cpus[0].id, "cpu-fresh"]);
    expect(synced.cpus[1].model).toBe("");
  });

  it("keeps synced row ids stable when an unnamed row is present", () => {
    const hbom = emptyHBOM();
    hbom.gpus["NVIDIA A100"] = {
      vendor: "NVIDIA",
      quantity: 1,
      memoryGb: 80,
      interface: "PCIe",
      extraInfo: {},
    };
    const previous = draftFromHBOM(hbom);
    previous.gpus.unshift(newGpuRow(() => "gpu-fresh"));

    const synced = draftFromHBOM(hbom, previous);

    // The named row keeps its id even though an unnamed row sits before it, so
    // React does not remount the input the author is typing into.
    expect(synced.gpus.map((row) => row.id)).toEqual(["gpu-0", "gpu-fresh"]);
  });

  it("preserves hbom extraInfo when writing draft back to HBOM", () => {
    const hbom = emptyHBOM();
    hbom.extraInfo = { note: "keep me" };
    const draft = draftFromHBOM(hbom);

    const rebuilt = hbomFromDraft(draft, hbom);
    expect(rebuilt.extraInfo).toEqual({ note: "keep me" });
  });

  it("creates editable defaults for every hardware category", () => {
    const id = (prefix: string) => `${prefix}-new`;
    expect(newCpuRow(id)).toMatchObject({ id: "cpu-new", quantity: 1, coresPerCpu: 1 });
    expect(newGpuRow(id)).toMatchObject({ id: "gpu-new", quantity: 1, memoryGb: 0 });
    expect(newMemoryRow(id)).toMatchObject({
      id: "memory-new",
      capacityGb: 0,
      memoryType: "DDR5",
    });
    expect(newStorageRow(id)).toMatchObject({
      id: "storage-new",
      capacityGb: 0,
      storageType: "NVMe",
    });
    expect(newNetworkRow(id)).toMatchObject({
      id: "network-new",
      bandwidthGbps: 0,
      networkType: "ethernet",
    });
  });

  it("projects every category with stable ids and carries each unnamed draft row", () => {
    const hbom = emptyHBOM();
    hbom.cpus.cpu = {
      vendor: "v",
      quantity: 1,
      coresPerCpu: 2,
      threadsPerCore: 1,
      architecture: "x",
      extraInfo: {},
    };
    hbom.gpus.gpu = {
      vendor: "v",
      quantity: 1,
      memoryGb: 2,
      interface: "i",
      extraInfo: {},
    };
    hbom.memory.ram = {
      vendor: "v",
      quantity: 1,
      capacityGb: 2,
      memoryType: "DDR5",
      speedMtS: 3,
      extraInfo: {},
    };
    hbom.storage.disk = {
      vendor: "v",
      quantity: 1,
      capacityGb: 2,
      storageType: "NVMe",
      interface: "i",
      extraInfo: {},
    };
    hbom.network.nic = {
      vendor: "v",
      quantity: 1,
      bandwidthGbps: 2,
      networkType: "ethernet",
      interface: "i",
      extraInfo: {},
    };
    const previous = draftFromHBOM(hbom);
    previous.cpus.push(newCpuRow(() => "cpu-blank"));
    previous.gpus.push(newGpuRow(() => "gpu-blank"));
    previous.memory.push(newMemoryRow(() => "memory-blank"));
    previous.storage.push(newStorageRow(() => "storage-blank"));
    previous.network.push(newNetworkRow(() => "network-blank"));

    const synced = draftFromHBOM(hbom, previous);
    expect(synced.cpus.map(({ id }) => id)).toEqual(["cpu-0", "cpu-blank"]);
    expect(synced.gpus.map(({ id }) => id)).toEqual(["gpu-0", "gpu-blank"]);
    expect(synced.memory.map(({ id }) => id)).toEqual(["memory-0", "memory-blank"]);
    expect(synced.storage.map(({ id }) => id)).toEqual(["storage-0", "storage-blank"]);
    expect(synced.network.map(({ id }) => id)).toEqual(["network-0", "network-blank"]);
  });

  it("normalizes numeric fields while preserving valid values in every category", () => {
    const id = (prefix: string) => prefix;
    const draft = draftFromHBOM(emptyHBOM());
    draft.cpus = [
      {
        ...newCpuRow(id),
        model: " CPU ",
        vendor: " Vendor ",
        quantity: 1.9,
        coresPerCpu: 0,
        threadsPerCore: Number.POSITIVE_INFINITY,
      },
    ];
    draft.gpus = [
      { ...newGpuRow(id), model: " GPU ", quantity: -1, memoryGb: 12.5, interface: " PCIe " },
    ];
    draft.memory = [
      { ...newMemoryRow(id), model: " RAM ", capacityGb: Number.NaN, speedMtS: 6400.8 },
    ];
    draft.storage = [{ ...newStorageRow(id), model: " Disk ", quantity: 2, capacityGb: -4 }];
    draft.network = [{ ...newNetworkRow(id), model: " NIC ", quantity: 2.7, bandwidthGbps: 100 }];

    expect(hbomFromDraft(draft, emptyHBOM())).toMatchObject({
      cpus: { CPU: { vendor: "Vendor", quantity: 1, coresPerCpu: 1, threadsPerCore: 1 } },
      gpus: { GPU: { quantity: 1, memoryGb: 12.5, interface: "PCIe" } },
      memory: { RAM: { capacityGb: 0, speedMtS: 6400 } },
      storage: { Disk: { quantity: 2, capacityGb: 0 } },
      network: { NIC: { quantity: 2, bandwidthGbps: 100 } },
    });
  });

  it("drops unnamed rows in every category and serializes a stable sync key", () => {
    const draft = {
      cpus: [newCpuRow(() => "cpu")],
      gpus: [newGpuRow(() => "gpu")],
      memory: [newMemoryRow(() => "memory")],
      storage: [newStorageRow(() => "storage")],
      network: [newNetworkRow(() => "network")],
    };
    const rebuilt = hbomFromDraft(draft, emptyHBOM());
    expect(rebuilt).toEqual(emptyHBOM());
    expect(hbomSyncKey(rebuilt)).toBe(JSON.stringify(emptyHBOM()));
  });
});
