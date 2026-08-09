import { describe, expect, it } from "vitest";
import type { ReeRunSummary } from "../runs/ReeRun";
import { latestCrossCheckSummary } from "./crossCheckRun";

function crossCheckRun(
  overrides: Partial<ReeRunSummary> & { matched?: number } = {},
): ReeRunSummary {
  const { matched = 1, ...run } = overrides;
  return {
    runId: "crosscheck-1",
    operation: "crosscheck",
    status: "succeeded",
    createdAt: "2026-01-01T00:00:00Z",
    finishedAt: "2026-01-01T00:00:01Z",
    outputs: {
      cross_check: {
        sbom_digest: "sha256:abc",
        checked_at: "2026-01-01T00:00:01Z",
        declared_direct_total: 1,
        observed_matched: matched,
        version_mismatches: 0,
        undeclared_same_ecosystem: 1,
        observed_total: 12,
        undeclared: [{ ecosystem: "pypi", name: "numpy", version: "2.0.0" }],
      },
    },
    ...run,
  } as ReeRunSummary;
}

describe("latestCrossCheckSummary", () => {
  it("reads aggregates and undeclared packages off the run's outputs", () => {
    const summary = latestCrossCheckSummary([crossCheckRun()]);
    expect(summary).toMatchObject({
      declaredDirectTotal: 1,
      observedMatched: 1,
      observedTotal: 12,
      undeclared: [{ ecosystem: "pypi", name: "numpy", version: "2.0.0" }],
    });
  });

  it("takes the newest succeeded run, whatever order the listing arrives in", () => {
    const summary = latestCrossCheckSummary([
      crossCheckRun({ runId: "old", finishedAt: "2026-01-01T00:00:01Z", matched: 0 }),
      crossCheckRun({ runId: "new", finishedAt: "2026-01-02T00:00:01Z", matched: 1 }),
    ]);
    expect(summary?.observedMatched).toBe(1);
  });

  it("ignores runs that are another operation, unfinished, or failed", () => {
    expect(latestCrossCheckSummary([crossCheckRun({ operation: "sbom" })])).toBeNull();
    expect(latestCrossCheckSummary([crossCheckRun({ status: "running" })])).toBeNull();
    expect(latestCrossCheckSummary([crossCheckRun({ status: "failed" })])).toBeNull();
  });

  it("is null when a succeeded run recorded no cross-check outputs", () => {
    expect(latestCrossCheckSummary([crossCheckRun({ outputs: {} })])).toBeNull();
  });
});
