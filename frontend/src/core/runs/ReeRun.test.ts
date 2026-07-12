import { describe, expect, it } from "vitest";
import type { ReeRun, ReeRunLogChunk } from "./ReeRun";
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
