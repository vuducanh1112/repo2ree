import { describe, expect, it } from "vitest";
import { emptyHBOM } from "./HbomSummary";
import { draftFromHBOM, hbomFromDraft, newCpuRow } from "./hardwareBomDraft";

describe("hardwareBomDraft", () => {
  it("round-trips model-keyed HBOM entries through draft conversion", () => {
    const hbom = emptyHBOM();
    hbom.cpus["Intel Xeon Gold 6348"] = {
      vendor: "Intel",
      quantity: 2,
      cores_per_cpu: 28,
      threads_per_core: 2,
      architecture: "x86_64",
      extra_info: { stepping: "B1" },
    };
    hbom.extra_info = { source: "manual" };

    const draft = draftFromHBOM(hbom);
    const rebuilt = hbomFromDraft(draft, hbom);

    expect(rebuilt).toEqual(hbom);
  });

  it("drops rows with empty model and normalizes invalid numeric values", () => {
    const hbom = emptyHBOM();
    const cpu = newCpuRow((prefix) => `${prefix}-test`);
    const draft = {
      cpus: [{ ...cpu, model: "  ", quantity: 0, cores_per_cpu: Number.NaN, threads_per_core: -1 }],
      gpus: [],
      memory: [],
      storage: [],
      network: [],
    };

    const rebuilt = hbomFromDraft(draft, hbom);
    expect(rebuilt.cpus).toEqual({});
  });

  it("preserves hbom extra_info when writing draft back to HBOM", () => {
    const hbom = emptyHBOM();
    hbom.extra_info = { note: "keep me" };
    const draft = draftFromHBOM(hbom);

    const rebuilt = hbomFromDraft(draft, hbom);
    expect(rebuilt.extra_info).toEqual({ note: "keep me" });
  });
});
