import { describe, expect, it } from "vitest";
import type { ExecutionRun, ExecutionRunLogChunk } from "./ExecutionRun";
import type { ExecutionRunStatus } from "./ExecutionRunStatus";

describe("execution run vocabulary types", () => {
  it("models an execution run record with canonical statuses", () => {
    const status: ExecutionRunStatus = "running";
    const run: ExecutionRun = {
      runId: "run-123",
      status,
      createdAt: "2026-01-01T00:00:00Z",
    };
    expect(run.status).toBe("running");
  });

  it("models execution log chunks", () => {
    const chunk: ExecutionRunLogChunk = {
      lines: [{ type: "info", msg: "step started" }],
      hasMore: false,
    };
    expect(chunk.lines).toHaveLength(1);
    expect(chunk.hasMore).toBe(false);
  });
});
