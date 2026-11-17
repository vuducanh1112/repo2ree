import { describe, expect, it } from "vitest";
import { filesReceipt, type ReeRun, type ReeRunLogChunk } from "./ReeRun";
import type { ReeRunStatus } from "./ReeRunStatus";

describe("execution run vocabulary types", () => {
  it("models an execution run record with canonical statuses", () => {
    const status: ReeRunStatus = "running";
    const run: ReeRun = {
      runId: "run-123",
      status,
      createdAt: "2026-01-01T00:00:00Z",
    };
    expect(run.status).toBe("running");
  });

  it("models execution log chunks", () => {
    const chunk: ReeRunLogChunk = {
      lines: [{ type: "info", msg: "step started" }],
      hasMore: false,
    };
    expect(chunk.lines).toHaveLength(1);
    expect(chunk.hasMore).toBe(false);
  });
});

describe("filesReceipt", () => {
  it("is true for the evidence steps and false for lifecycle runs", () => {
    expect(filesReceipt("build_experiment_environment")).toBe(true);
    expect(filesReceipt("run_experiment")).toBe(true);
    expect(filesReceipt("seal_ree")).toBe(false);
    expect(filesReceipt("load_ree_bundle")).toBe(false);
    expect(filesReceipt("initialize_ree")).toBe(false);
  });
});
