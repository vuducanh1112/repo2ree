import { describe, expect, it } from "vitest";
import { emptyHBOM } from "./HbomSummary";
import { draftFromHBOM, hbomFromDraft, newCpuRow } from "./hardwareBomDraft";

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

  it("preserves hbom extraInfo when writing draft back to HBOM", () => {
    const hbom = emptyHBOM();
    hbom.extraInfo = { note: "keep me" };
    const draft = draftFromHBOM(hbom);

    const rebuilt = hbomFromDraft(draft, hbom);
    expect(rebuilt.extraInfo).toEqual({ note: "keep me" });
  });
});
