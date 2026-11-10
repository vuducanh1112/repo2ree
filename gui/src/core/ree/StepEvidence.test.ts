import { describe, expect, it } from "vitest";
import {
  auditReceiptRunId,
  auditReceiptRunIds,
  isEvidenceCurrent,
  isEvidenceStale,
  mapRawReeAudit,
  mapRawStepEvidence,
} from "./StepEvidence";

describe("mapRawStepEvidence", () => {
  it("reads each audited step's standing off the wire audit", () => {
    const evidence = mapRawStepEvidence({
      source: { evidence: "current", payload: "present", reasons: [] },
      experiment_environment: {
        evidence: "stale",
        payload: "not_applicable",
        reasons: ["build script changed"],
      },
      sbom_cross_check: { evidence: "not_applicable", payload: "not_applicable" },
    });

    expect(evidence).toEqual({
      source: "current",
      experiment_environment: "stale",
      sbom_cross_check: "not_applicable",
    });
  });

  it("keeps unknown steps and unknown standings out of the slice", () => {
    expect(mapRawStepEvidence({ deposit: { evidence: "current" } })).toEqual({});
    expect(mapRawStepEvidence({ experiment_environment: { evidence: "probably-fine" } })).toEqual(
      {},
    );
    expect(mapRawStepEvidence({ experiment_environment: "current" })).toEqual({});
  });

  it("reads an absent audit as an REE that has recorded nothing", () => {
    expect(mapRawStepEvidence(undefined)).toEqual({});
    expect(isEvidenceCurrent(mapRawStepEvidence(null), "experiment_environment")).toBe(false);
  });
});

describe("mapRawReeAudit", () => {
  it("retains backend reasons, payload standing, receipt run ids, and experiments", () => {
    const audit = mapRawReeAudit({
      experiment_environment: {
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

    expect(audit.experiment_environment).toEqual({
      evidence: "stale",
      payload: "present",
      receiptRunId: "run-build-1",
      reasons: ["build script changed"],
    });
    expect(auditReceiptRunId(audit, "experiment_environment")).toBe("run-build-1");
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
    expect(isEvidenceCurrent({ experiment_environment: "current" }, "experiment_environment")).toBe(
      true,
    );
    expect(isEvidenceCurrent({ experiment_environment: "stale" }, "experiment_environment")).toBe(
      false,
    );
    expect(isEvidenceStale({ experiment_environment: "stale" }, "experiment_environment")).toBe(
      true,
    );
    expect(isEvidenceStale({ experiment_environment: "current" }, "experiment_environment")).toBe(
      false,
    );
    expect(isEvidenceStale({}, "experiment_environment")).toBe(false);
  });
});

describe("auditReceiptRunIds", () => {
  it("names every run that produced a receipt, experiments included", () => {
    const audit = mapRawReeAudit({
      source: { evidence: "current", payload: "present", receipt_run_id: "source-1" },
      experiment_environment: { evidence: "stale", payload: "present", receipt_run_id: "build-1" },
      sbom: { evidence: "missing", payload: "missing" },
      experiments: [
        {
          name: "hello",
          run: { evidence: "current", payload: "present", receipt_run_id: "exp-1" },
        },
      ],
    });
    expect(auditReceiptRunIds(audit)).toEqual(new Set(["source-1", "build-1", "exp-1"]));
  });
});
