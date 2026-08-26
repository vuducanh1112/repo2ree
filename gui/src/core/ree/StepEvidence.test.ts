import { describe, expect, it } from "vitest";
import { isEvidenceCurrent, isEvidenceStale, mapRawStepEvidence } from "./StepEvidence";

describe("mapRawStepEvidence", () => {
  it("reads each audited step's standing off the wire audit", () => {
    const evidence = mapRawStepEvidence({
      source: { evidence: "current", payload: "present", reasons: [] },
      runtime: { evidence: "stale", payload: "not_applicable", reasons: ["build script changed"] },
      sbom_cross_check: { evidence: "not_applicable", payload: "not_applicable" },
    });

    expect(evidence).toEqual({
      source: "current",
      runtime: "stale",
      sbom_cross_check: "not_applicable",
    });
  });

  it("keeps unknown steps and unknown standings out of the slice", () => {
    expect(mapRawStepEvidence({ deposit: { evidence: "current" } })).toEqual({});
    expect(mapRawStepEvidence({ runtime: { evidence: "probably-fine" } })).toEqual({});
    expect(mapRawStepEvidence({ runtime: "current" })).toEqual({});
  });

  it("reads an absent audit as an REE that has recorded nothing", () => {
    expect(mapRawStepEvidence(undefined)).toEqual({});
    expect(isEvidenceCurrent(mapRawStepEvidence(null), "runtime")).toBe(false);
  });
});

describe("evidence standing", () => {
  // The whole point of the split: a stale receipt is still on the aggregate,
  // so it is not "missing" — but it does not make its step done either.
  it("counts only a current receipt as done, and names a stale one as stale", () => {
    expect(isEvidenceCurrent({ runtime: "current" }, "runtime")).toBe(true);
    expect(isEvidenceCurrent({ runtime: "stale" }, "runtime")).toBe(false);
    expect(isEvidenceStale({ runtime: "stale" }, "runtime")).toBe(true);
    expect(isEvidenceStale({ runtime: "current" }, "runtime")).toBe(false);
    expect(isEvidenceStale({}, "runtime")).toBe(false);
  });
});
