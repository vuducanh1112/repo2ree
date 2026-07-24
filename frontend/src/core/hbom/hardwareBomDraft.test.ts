import { describe, expect, it } from "vitest";
import { emptyHBOM } from "./HbomSummary";
import { draftFromHBOM, hbomFromDraft, newCpuRow, newGpuRow } from "./hardwareBomDraft";

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
});
