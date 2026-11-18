import { UnknownWireNames } from "@core/contract/unknownNames";
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
      acquire_source: { evidence: "current", payload: "present", reasons: [] },
      build_experiment_environment: {
        evidence: "stale",
        payload: "not_applicable",
        reasons: ["build script changed"],
      },
      cross_check_sbom: { evidence: "not_applicable", payload: "not_applicable" },
    });

    expect(evidence).toEqual({
      acquire_source: "current",
      build_experiment_environment: "stale",
      cross_check_sbom: "not_applicable",
    });
  });

  it("reads the working environment check's standing", () => {
    expect(
      mapRawStepEvidence({
        check_working_environment: { evidence: "current", payload: "present" },
      }),
    ).toEqual({ check_working_environment: "current" });
  });

  it("keeps unknown standings out of the slice", () => {
    expect(mapRawStepEvidence({ generate_sbom: { evidence: "probably-fine" } })).toEqual({});
    expect(mapRawStepEvidence({ generate_sbom: "current" })).toEqual({});
  });

  it("refuses a step the contract does not name, rather than reading it as missing", () => {
    expect(() => mapRawStepEvidence({ experiment_environment: { evidence: "current" } })).toThrow(
      UnknownWireNames,
    );
    expect(() => mapRawReeAudit({ deposit: { evidence: "current" } })).toThrow(/deposit/);
  });

  it("reads an absent audit as an REE that has recorded nothing", () => {
    expect(mapRawStepEvidence(undefined)).toEqual({});
    expect(isEvidenceCurrent(mapRawStepEvidence(null), "build_experiment_environment")).toBe(false);
  });
});

describe("mapRawReeAudit", () => {
  it("retains backend reasons, payload standing, receipt run ids, and experiments", () => {
    const audit = mapRawReeAudit({
      build_experiment_environment: {
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

    expect(audit.build_experiment_environment).toEqual({
      evidence: "stale",
      payload: "present",
      receiptRunId: "run-build-1",
      reasons: ["build script changed"],
    });
    expect(auditReceiptRunId(audit, "build_experiment_environment")).toBe("run-build-1");
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
    expect(
      isEvidenceCurrent(
        { build_experiment_environment: "current" },
        "build_experiment_environment",
      ),
    ).toBe(true);
    expect(
      isEvidenceCurrent({ build_experiment_environment: "stale" }, "build_experiment_environment"),
    ).toBe(false);
    expect(
      isEvidenceStale({ build_experiment_environment: "stale" }, "build_experiment_environment"),
    ).toBe(true);
    expect(
      isEvidenceStale({ build_experiment_environment: "current" }, "build_experiment_environment"),
    ).toBe(false);
    expect(isEvidenceStale({}, "build_experiment_environment")).toBe(false);
  });
});

describe("auditReceiptRunIds", () => {
  it("names every run that produced a receipt, experiments included", () => {
    const audit = mapRawReeAudit({
      acquire_source: { evidence: "current", payload: "present", receipt_run_id: "source-1" },
      build_experiment_environment: {
        evidence: "stale",
        payload: "present",
        receipt_run_id: "build-1",
      },
      generate_sbom: { evidence: "missing", payload: "missing" },
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
