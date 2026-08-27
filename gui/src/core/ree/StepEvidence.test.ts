import { describe, expect, it } from "vitest";
import {
  auditReceiptRunId,
  isEvidenceCurrent,
  isEvidenceStale,
  mapRawReeAudit,
  mapRawStepEvidence,
} from "./StepEvidence";

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

describe("mapRawReeAudit", () => {
  it("retains backend reasons, payload standing, receipt run ids, and experiments", () => {
    const audit = mapRawReeAudit({
      runtime: {
        evidence: "stale",
        payload: "present",
        receipt_run_id: "run-build-1",
        reasons: ["build script changed"],
      },
      experiments: [
        {
          name: "demo",
          run: { evidence: "current", payload: "present", receipt_run_id: "run-exp-1" },
        },
      ],
    });

    expect(audit.runtime).toEqual({
      evidence: "stale",
      payload: "present",
      receiptRunId: "run-build-1",
      reasons: ["build script changed"],
    });
    expect(auditReceiptRunId(audit, "runtime")).toBe("run-build-1");
    expect(audit.experiments?.[0]).toMatchObject({
      name: "demo",
      run: { evidence: "current", receiptRunId: "run-exp-1" },
    });
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
